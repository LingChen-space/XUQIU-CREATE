# -*- coding: utf-8 -*-
"""Tap + 快爆论坛外部监控后台同步。"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.game import Game
from app.models.platform_content import ContentPlatform, ContentType, PlatformContent
from app.models.platform_search_config import PlatformSearchConfig
from app.utils.engagement import compute_content_hot_score

logger = logging.getLogger(__name__)

SOURCE_KEY = "tap_kb_forum"
SOURCE_LABEL = "Tap + 快爆论坛"
LAST_SYNC_STATUS: dict[str, Any] = {
    "source_key": SOURCE_KEY,
    "status": "idle",
    "message": "尚未同步",
    "contents": {
        "fetched": 0,
        "inserted": 0,
        "duplicates": 0,
        "unmatched_games": 0,
        "invalid": 0,
    },
    "configs": {
        "fetched": 0,
        "upserted": 0,
        "skipped": 0,
    },
    "synced_at": None,
}


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _first_int(*values: Any) -> int:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return max(0, int(value))
        if isinstance(value, str) and value.strip():
            try:
                return max(0, int(float(value.strip())))
            except ValueError:
                continue
    return 0


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    text = str(value or "").strip()
    if not text:
        return datetime.now()
    normalized = text.replace("Z", "+00:00")
    for parser in (
        lambda v: datetime.fromisoformat(v),
        lambda v: datetime.strptime(v, "%Y-%m-%d %H:%M:%S"),
        lambda v: datetime.strptime(v, "%Y-%m-%d"),
    ):
        try:
            parsed = parser(normalized)
            return parsed.replace(tzinfo=None)
        except ValueError:
            continue
    return datetime.now()


def _normalize_platform(value: Any) -> tuple[str, ContentPlatform]:
    text = str(value or "").strip().lower()
    if text in {"taptap", "tap", "tap tap"} or "taptap" in text:
        return "taptap", ContentPlatform.taptap
    if text in {"快爆论坛", "好游快爆", "kuaibao", "kb", "hykb"} or "快爆" in text:
        return "kuaibao_forum", ContentPlatform.kuaibao_forum
    return "other", ContentPlatform.other


def _normalize_keywords(value: Any) -> str:
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
    else:
        raw = str(value or "")
        for sep in ("|", "，", "\n", "\t", " "):
            raw = raw.replace(sep, ",")
        parts = [item.strip() for item in raw.split(",") if item.strip()]

    seen: set[str] = set()
    clean: list[str] = []
    for item in parts:
        if item not in seen:
            seen.add(item)
            clean.append(item)
    return ",".join(clean)


def _extract_records(payload: Any, *keys: str) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_records(value, *keys)
            if nested:
                return nested
    return []


class TapKbExportClient:
    """标准导出客户端。真实接口地址由环境变量配置。"""

    def __init__(
        self,
        content_url: str | None = None,
        config_url: str | None = None,
        api_key: str | None = None,
    ):
        self.content_url = content_url if content_url is not None else settings.tap_kb_content_export_url
        self.config_url = config_url if config_url is not None else settings.tap_kb_config_export_url
        self.api_key = api_key if api_key is not None else settings.tap_kb_api_key

    @property
    def configured(self) -> bool:
        if not hasattr(self, "content_url") and not hasattr(self, "config_url"):
            return True
        return bool(getattr(self, "content_url", "") or getattr(self, "config_url", ""))

    async def _get_json(self, url: str, params: dict | None = None) -> Any:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, params=params or {}, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def fetch_contents(self, days: int) -> list[dict]:
        if not self.content_url:
            return []
        payload = await self._get_json(self.content_url, {"days": days})
        return _extract_records(payload, "contents", "items", "data", "list", "rows")

    async def fetch_configs(self) -> list[dict]:
        if not self.config_url:
            return []
        payload = await self._get_json(self.config_url)
        return _extract_records(payload, "configs", "items", "data", "list", "rows")


class TapKbForumSyncService:
    """把 Tap + 快爆论坛标准导出同步到现有内容和配置表。"""

    def __init__(self, session: AsyncSession, client: TapKbExportClient | None = None):
        self.session = session
        self.client = client or TapKbExportClient()

    async def sync(self, days: int = 30, force: bool = False) -> dict:
        if not self.client.configured:
            return self._set_status(
                "not_configured",
                "Tap + 快爆论坛导出接口未配置，已跳过外部同步。",
                self._empty_content_stats(),
                self._empty_config_stats(),
            )

        try:
            raw_contents = await self.client.fetch_contents(days)
            raw_configs = await self.client.fetch_configs()
            content_stats = await self._sync_contents(raw_contents, force=force)
            config_stats = await self._sync_configs(raw_configs)
            return self._set_status(
                "completed",
                f"Tap + 快爆论坛同步完成：内容入库 {content_stats['inserted']} 条，配置同步 {config_stats['upserted']} 条。",
                content_stats,
                config_stats,
            )
        except Exception as exc:
            logger.exception("[TapKbSync] 同步失败")
            return self._set_status(
                "failed",
                str(exc)[:500],
                self._empty_content_stats(),
                self._empty_config_stats(),
            )

    async def _sync_contents(self, records: list[dict], force: bool = False) -> dict:
        stats = self._empty_content_stats()
        stats["fetched"] = len(records)
        if not records:
            return stats

        result = await self.session.execute(select(Game))
        games_by_name = {g.name.strip(): g for g in result.scalars().all() if g.name}

        source_ids = {
            f"{SOURCE_KEY}:{_first_text(item.get('external_id'), item.get('id'))}"
            for item in records
            if _first_text(item.get("external_id"), item.get("id"))
        }
        existing_source_ids: set[str] = set()
        if source_ids and not force:
            existing = await self.session.execute(
                select(PlatformContent.source_id).where(PlatformContent.source_id.in_(source_ids))
            )
            existing_source_ids = set(existing.scalars().all())

        seen: set[str] = set()
        for item in records:
            external_id = _first_text(item.get("external_id"), item.get("id"))
            if not external_id:
                stats["invalid"] += 1
                continue
            source_id = f"{SOURCE_KEY}:{external_id}"
            if source_id in seen or source_id in existing_source_ids:
                stats["duplicates"] += 1
                continue
            seen.add(source_id)

            game_name = _first_text(item.get("game_name"), item.get("game"))
            game = games_by_name.get(game_name)
            if game is None:
                stats["unmatched_games"] += 1
                continue

            platform_key, platform = _normalize_platform(item.get("platform"))
            title = _first_text(item.get("title"))
            body = _first_text(item.get("summary"), item.get("body"), item.get("description"))
            if not title and not body:
                stats["invalid"] += 1
                continue

            view_count = _first_int(item.get("view_count"), item.get("views"), item.get("read_count"))
            like_count = _first_int(item.get("like_count"), item.get("likes"), item.get("thumbs"))
            comment_count = _first_int(item.get("comment_count"), item.get("comments"), item.get("reply_count"))
            share_count = _first_int(item.get("share_count"), item.get("shares"))

            self.session.add(PlatformContent(
                id=str(uuid.uuid4()),
                game_id=game.id,
                platform=platform,
                content_type=ContentType.post,
                source_id=source_id,
                url=_first_text(item.get("url"), item.get("link")),
                title=title,
                body=body,
                author=_first_text(item.get("author"), item.get("nickname"), item.get("user_name")),
                view_count=view_count,
                like_count=like_count,
                comment_count=comment_count,
                share_count=share_count,
                hot_score=compute_content_hot_score(view_count, like_count, comment_count, share_count),
                published_at=_parse_datetime(item.get("published_at") or item.get("created_at")),
                extra_data=json.dumps({
                    "source_key": SOURCE_KEY,
                    "source_label": SOURCE_LABEL,
                    "platform_key": platform_key,
                    "external_id": external_id,
                    "keyword_hit": _first_text(item.get("keyword_hit"), item.get("keyword")),
                    "raw": item,
                }, ensure_ascii=False),
            ))
            stats["inserted"] += 1

        await self.session.commit()
        return stats

    async def _sync_configs(self, records: list[dict]) -> dict:
        stats = self._empty_config_stats()
        stats["fetched"] = len(records)
        if not records:
            return stats

        for item in records:
            platform_key, _platform = _normalize_platform(item.get("platform"))
            if platform_key == "other":
                stats["skipped"] += 1
                continue
            keywords = _normalize_keywords(item.get("keywords"))
            if not keywords:
                stats["skipped"] += 1
                continue

            group_name = _first_text(item.get("group_name"), item.get("group"), "默认")
            external_id = _first_text(item.get("external_id"), item.get("id"), f"{platform_key}:{group_name}")

            existing = await self.session.execute(
                select(PlatformSearchConfig).where(
                    PlatformSearchConfig.source_key == SOURCE_KEY,
                    PlatformSearchConfig.external_id == external_id,
                )
            )
            cfg = existing.scalar()
            if cfg is None:
                cfg = PlatformSearchConfig(
                    platform=platform_key,
                    keywords=keywords,
                    enabled=bool(item.get("enabled", True)),
                    crawl_count=50,
                    source_key=SOURCE_KEY,
                    external_group=group_name,
                    external_id=external_id,
                    last_synced_at=datetime.now(),
                )
                self.session.add(cfg)
            else:
                cfg.platform = platform_key
                cfg.keywords = keywords
                cfg.enabled = bool(item.get("enabled", True))
                cfg.external_group = group_name
                cfg.last_synced_at = datetime.now()
            stats["upserted"] += 1

        await self.session.commit()
        return stats

    def _set_status(self, status: str, message: str, content_stats: dict, config_stats: dict) -> dict:
        global LAST_SYNC_STATUS
        LAST_SYNC_STATUS = {
            "source_key": SOURCE_KEY,
            "status": status,
            "message": message,
            "contents": content_stats,
            "configs": config_stats,
            "synced_at": datetime.now().isoformat(),
        }
        return LAST_SYNC_STATUS

    @staticmethod
    def _empty_content_stats() -> dict:
        return {
            "fetched": 0,
            "inserted": 0,
            "duplicates": 0,
            "unmatched_games": 0,
            "invalid": 0,
        }

    @staticmethod
    def _empty_config_stats() -> dict:
        return {
            "fetched": 0,
            "upserted": 0,
            "skipped": 0,
        }


def get_tap_kb_sync_status() -> dict:
    return LAST_SYNC_STATUS
