"""TapTap 代理 API 同步：走自建代理(1.117.17.251)拉 `/taptap/feed/by-group`。

区别于 Tap+快爆后台同步(`external_monitor_sync.TapKbApiClient`)：
- Tap+快爆同步：从快爆后台导出 API 拉 tap/hykb 内容（MD5 签名 POST）。
- 本模块：直连 TapTap 代理（HMAC-SHA256 签名 GET），按后台 `platform_search_configs`
  里 platform=taptap 的配置(keywords=group_id, game_id=游戏) 拉分组 Feed。

不经过本地爬虫(本地 IP 不直接采集 TapTap)，由代理服务器代抓。
"""

import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.platform_content import ContentPlatform, ContentType, PlatformContent
from app.models.platform_search_config import PlatformSearchConfig
from app.models.radar import ContentMetricSnapshot, ContentScanState
from app.utils.engagement import compute_content_hot_score

logger = logging.getLogger(__name__)

SOURCE_KEY = "tap_proxy"
SOURCE_LABEL = "TapTap代理"
TAP_PLATFORM = "taptap"


class TapProxyClient:
    """TapTap 代理 API 客户端（HMAC-SHA256 签名 GET）。"""

    def __init__(self, api_url: str | None = None, secret: str | None = None, timeout: float = 30.0):
        self.api_url = (api_url or settings.tap_proxy_api_url).rstrip("/")
        self.secret = secret or settings.tap_proxy_api_secret
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_url and self.secret)

    def _sign_headers(self) -> dict[str, str]:
        ts = str(int(time.time()))
        sign = hmac.new(self.secret.encode("utf-8"), ts.encode("utf-8"), hashlib.sha256).hexdigest()
        return {"X-Timestamp": ts, "X-Sign": sign}

    async def fetch_feed_by_group(self, group_id: str, limit: int = 10, max_pages: int = 2) -> list[dict]:
        """拉取分组 Feed，翻 max_pages 页，返回 moment 原始 list。"""
        moments: list[dict] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for page in range(max(1, int(max_pages or 1))):
                params = {
                    "group_id": group_id,
                    "sort": "created",
                    "type": "feed",
                    "from": page * limit,
                    "limit": limit,
                }
                try:
                    resp = await client.get(
                        f"{self.api_url}/taptap/feed/by-group",
                        params=params,
                        headers=self._sign_headers(),
                    )
                    resp.raise_for_status()
                    payload = resp.json()
                except Exception as exc:
                    logger.warning(f"[TapProxy] group={group_id} page={page} 请求失败: {exc}")
                    break
                inner = payload.get("data") if isinstance(payload, dict) else None
                if not isinstance(inner, dict) or inner.get("success") not in (True, "true"):
                    logger.warning(f"[TapProxy] group={group_id} page={page} success 非 true: {str(payload)[:200]}")
                    break
                ddata = inner.get("data") if isinstance(inner, dict) else None
                if not isinstance(ddata, dict):
                    break
                lst = ddata.get("list") or []
                if not lst:
                    break
                moments.extend(lst)
                if not ddata.get("next_page"):
                    break
        return moments


class TapProxySyncService:
    """按 taptap 接口配置拉取分组 Feed 入库。

    配置来源：`platform_search_configs` 中 platform=taptap、enabled=True 的记录，
    keywords=group_id（逗号分隔多个），game_id=归属游戏。即"Tap接口配置"，非本地IP采集。
    """

    def __init__(self, session: AsyncSession, client: TapProxyClient | None = None):
        self.session = session
        self.client = client or TapProxyClient()

    async def sync(self) -> dict:
        stats = {"fetched": 0, "inserted": 0, "duplicates": 0, "invalid": 0, "groups": 0, "ok": True, "message": ""}
        if not self.client.configured:
            stats["ok"] = False
            stats["message"] = "TapTap代理接口未配置"
            return stats

        configs = (
            await self.session.execute(
                select(PlatformSearchConfig).where(
                    PlatformSearchConfig.platform == TAP_PLATFORM,
                    PlatformSearchConfig.source_key == SOURCE_KEY,
                    PlatformSearchConfig.game_id.is_not(None),
                    PlatformSearchConfig.enabled == True,  # noqa: E712
                )
            )
        ).scalars().all()
        if not configs:
            stats["message"] = "无 taptap 接口配置(platform_search_configs platform=taptap)"
            return stats
        stats["groups"] = len(configs)

        for cfg in configs:
            group_ids = [g.strip() for g in (cfg.keywords or "").split(",") if g.strip()]
            for gid in group_ids:
                moments = await self.client.fetch_feed_by_group(
                    gid, limit=10, max_pages=settings.tap_proxy_max_pages
                )
                stats["fetched"] += len(moments)
                await self._store(cfg.game_id, gid, moments, stats)

        await self.session.commit()
        stats["message"] = (
            f"配置 {stats['groups']} 组，拉取 {stats['fetched']} 条，"
            f"新增 {stats['inserted']}，重复 {stats['duplicates']}，无效 {stats['invalid']}"
        )
        return stats

    async def _store(self, game_id: str | None, group_id: str, moments: list[dict], stats: dict) -> None:
        if not game_id:
            stats["invalid"] += len(moments)
            return

        parsed: list[tuple[str, str, dict, dict]] = []  # (source_id, url, moment, topic)
        for item in moments:
            m = item.get("moment") if isinstance(item, dict) else None
            if not isinstance(m, dict):
                stats["invalid"] += 1
                continue
            topic = m.get("topic") if isinstance(m.get("topic"), dict) else {}
            id_str = str(topic.get("id_str") or m.get("id_str") or "").strip()
            if not id_str:
                stats["invalid"] += 1
                continue
            source_id = f"{SOURCE_KEY}:{id_str}"
            url = f"https://www.taptap.com/topic/{id_str}"
            parsed.append((source_id, url, m, topic))

        if not parsed:
            return

        source_ids = [p[0] for p in parsed]
        urls = [p[1] for p in parsed]
        existing_rows = (
            await self.session.execute(
                select(PlatformContent).where(
                    or_(PlatformContent.source_id.in_(source_ids), PlatformContent.url.in_(urls))
                )
            )
        ).scalars().all()
        existing_keys: set[str] = set()
        for c in existing_rows:
            if c.source_id:
                existing_keys.add(c.source_id)
            if c.url:
                existing_keys.add(c.url)

        seen: set[str] = set()
        for source_id, url, m, topic in parsed:
            if source_id in existing_keys or url in existing_keys or source_id in seen:
                stats["duplicates"] += 1
                continue
            seen.add(source_id)

            title = str(topic.get("title") or "").strip()
            body = str(topic.get("summary") or "").strip()
            if not title and not body:
                stats["invalid"] += 1
                continue

            stat = m.get("stat") if isinstance(m.get("stat"), dict) else {}
            view_count = _to_int(stat.get("pv_total"))
            like_count = _to_int(stat.get("ups"))
            comment_count = 0
            share_count = 0

            author = ""
            author_obj = m.get("author") if isinstance(m.get("author"), dict) else {}
            user = author_obj.get("user") if isinstance(author_obj.get("user"), dict) else {}
            if isinstance(user, dict):
                author = str(user.get("name") or "").strip()

            published_ts = _to_int(m.get("created_time")) or _to_int(m.get("publish_time")) or int(time.time())
            published_at = datetime.fromtimestamp(published_ts)

            content = PlatformContent(
                id=str(uuid.uuid4()),
                game_id=game_id,
                platform=ContentPlatform.taptap,
                content_type=ContentType.post,
                source_id=source_id,
                url=url,
                title=title[:512],
                body=body,
                author=author[:128],
                view_count=view_count,
                like_count=like_count,
                comment_count=comment_count,
                share_count=share_count,
                hot_score=compute_content_hot_score(view_count, like_count, comment_count, share_count),
                published_at=published_at,
                extra_data=json.dumps(
                    {
                        "source_key": SOURCE_KEY,
                        "source_label": SOURCE_LABEL,
                        "group_id": group_id,
                        "moment_id": str(m.get("id_str") or ""),
                        "topic_id": str(topic.get("id_str") or ""),
                        "raw": m,
                    },
                    ensure_ascii=False,
                ),
            )
            self.session.add(content)
            await self.session.flush()
            self.session.add(ContentMetricSnapshot(
                content_id=content.id,
                platform=ContentPlatform.taptap,
                view_count=view_count,
                like_count=like_count,
                comment_count=comment_count,
                share_count=share_count,
            ))
            self.session.add(ContentScanState(content_id=content.id))
            stats["inserted"] += 1


def _to_int(value) -> int:
    if value is None or isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
