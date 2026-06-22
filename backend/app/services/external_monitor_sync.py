# -*- coding: utf-8 -*-
"""Tap + KuaiBao forum external monitor sync."""

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.external_monitor_cursor import ExternalMonitorCursor
from app.models.external_monitor_record import ExternalMonitorRecord
from app.models.game import Game
from app.models.platform_content import ContentPlatform, ContentType, PlatformContent
from app.models.platform_search_config import PlatformSearchConfig
from app.utils.engagement import compute_content_hot_score

logger = logging.getLogger(__name__)

SOURCE_KEY = "tap_kb_forum"
SOURCE_LABEL = "Tap + 快爆论坛"
FEED_TYPES = ("tap", "hykb")

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
    "last_ids": {},
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
    """Base client used by tests and protocol implementations."""

    @property
    def configured(self) -> bool:
        return True

    async def fetch_contents(self, days: int, last_ids: dict[str, int] | None = None):
        del days, last_ids
        return []

    async def fetch_configs(self) -> list[dict]:
        return []


class TapKbApiClient(TapKbExportClient):
    """Client for the signed tap_version2 api.php protocol."""

    def __init__(
        self,
        api_url: str | None = None,
        secret: str | None = None,
        clock: Callable[[], int] | None = None,
        post_form: Callable[[str, dict], Awaitable[dict]] | None = None,
    ):
        self.api_url = api_url if api_url is not None else settings.tap_kb_api_url
        self.secret = secret if secret is not None else settings.tap_kb_api_secret
        self.clock = clock or (lambda: int(time.time()))
        self.post_form = post_form

    @property
    def configured(self) -> bool:
        return bool(self.api_url and self.secret)

    async def _post_form(self, url: str, data: dict) -> dict:
        if self.post_form:
            return await self.post_form(url, data)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            payload = resp.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Tap+快爆接口返回格式不是 JSON 对象")
        return payload

    async def fetch_contents(self, days: int, last_ids: dict[str, int] | None = None) -> dict:
        del days
        last_ids = last_ids or {}
        records: list[dict] = []
        next_last_ids: dict[str, int] = {}

        for feed_type, platform_label in (("tap", "TapTap"), ("hykb", "快爆论坛")):
            current_time = int(self.clock())
            data = {
                "type": feed_type,
                "time": current_time,
                "sign": hashlib.md5(f"{current_time}{self.secret}".encode("utf-8")).hexdigest(),
            }
            previous_last_id = int(last_ids.get(feed_type, 0) or 0)
            if previous_last_id > 0:
                data["last_id"] = previous_last_id

            payload = await self._post_form(self.api_url, data)
            if int(payload.get("code", 0) or 0) != 200:
                raise RuntimeError(f"Tap+快爆接口 {feed_type} 请求失败: {payload.get('msg') or payload}")

            next_last_ids[feed_type] = _first_int(payload.get("last_id"))
            for item in _extract_records(payload, "data", "items", "list", "rows"):
                raw_id = _first_text(item.get("id"), item.get("external_id"))
                if not raw_id:
                    continue
                records.append({
                    "external_id": f"{feed_type}:{raw_id}",
                    "platform": platform_label,
                    "title": _first_text(item.get("title")),
                    "url": _first_text(item.get("url")),
                    "raw_feed_type": feed_type,
                    "raw": item,
                })

        return {"records": records, "last_ids": next_last_ids}


class TapKbForumSyncService:
    """Sync Tap + KuaiBao monitor data into local contents/configs."""

    def __init__(self, session: AsyncSession, client: TapKbExportClient | None = None):
        self.session = session
        self.client = client or TapKbApiClient()

    async def sync(self, days: int = 30, force: bool = False) -> dict:
        if not self.client.configured:
            return self._set_status(
                "not_configured",
                "Tap + 快爆论坛接口未配置，已跳过外部同步。",
                self._empty_content_stats(),
                self._empty_config_stats(),
                {},
            )

        try:
            saved_last_ids = {} if force else await self._get_last_ids()
            content_result = await self.client.fetch_contents(days, last_ids=saved_last_ids)
            raw_contents, returned_last_ids = self._split_content_result(content_result)
            raw_configs = await self.client.fetch_configs()
            await self._store_raw_records(raw_contents, returned_last_ids)
            content_stats = await self._sync_contents(raw_contents, force=force)
            config_stats = await self._sync_configs(raw_configs)
            if returned_last_ids:
                await self._save_last_ids(returned_last_ids)
            return self._set_status(
                "completed",
                f"Tap + 快爆论坛同步完成：内容入库 {content_stats['inserted']} 条，配置同步 {config_stats['upserted']} 条。",
                content_stats,
                config_stats,
                returned_last_ids,
            )
        except Exception as exc:
            logger.exception("[TapKbSync] sync failed")
            return self._set_status(
                "failed",
                str(exc)[:500],
                self._empty_content_stats(),
                self._empty_config_stats(),
                {},
            )

    @staticmethod
    def _split_content_result(content_result: Any) -> tuple[list[dict], dict[str, int]]:
        if isinstance(content_result, dict):
            records = _extract_records(content_result, "records", "contents", "items", "data", "list", "rows")
            raw_last_ids = content_result.get("last_ids") or {}
            last_ids = {
                str(feed_type): _first_int(last_id)
                for feed_type, last_id in raw_last_ids.items()
                if str(feed_type) in FEED_TYPES
            } if isinstance(raw_last_ids, dict) else {}
            return records, last_ids
        return _extract_records(content_result, "records", "contents", "items", "data", "list", "rows"), {}

    async def _get_last_ids(self) -> dict[str, int]:
        result = await self.session.execute(
            select(ExternalMonitorCursor).where(ExternalMonitorCursor.source_key == SOURCE_KEY)
        )
        return {cursor.feed_type: cursor.last_id for cursor in result.scalars().all()}

    async def _save_last_ids(self, last_ids: dict[str, int]):
        for feed_type, last_id in last_ids.items():
            if feed_type not in FEED_TYPES:
                continue
            result = await self.session.execute(
                select(ExternalMonitorCursor).where(
                    ExternalMonitorCursor.source_key == SOURCE_KEY,
                    ExternalMonitorCursor.feed_type == feed_type,
                )
            )
            cursor = result.scalar()
            if cursor is None:
                cursor = ExternalMonitorCursor(source_key=SOURCE_KEY, feed_type=feed_type, last_id=last_id)
                self.session.add(cursor)
            else:
                cursor.last_id = last_id
                cursor.updated_at = datetime.now()
        await self.session.commit()

    async def _store_raw_records(self, records: list[dict], last_ids: dict[str, int]):
        if not records:
            return

        raw_ids = [
            _first_text(item.get("external_id"), item.get("id"))
            for item in records
            if _first_text(item.get("external_id"), item.get("id"))
        ]
        existing_by_external_id: dict[str, ExternalMonitorRecord] = {}
        if raw_ids:
            result = await self.session.execute(
                select(ExternalMonitorRecord).where(
                    ExternalMonitorRecord.source_key == SOURCE_KEY,
                    ExternalMonitorRecord.external_id.in_(raw_ids),
                )
            )
            existing_by_external_id = {row.external_id: row for row in result.scalars().all()}

        now = datetime.now()
        touched: set[str] = set()
        for item in records:
            external_id = _first_text(item.get("external_id"), item.get("id"))
            if not external_id:
                continue
            feed_type = _first_text(item.get("raw_feed_type"))
            if not feed_type and ":" in external_id:
                feed_type = external_id.split(":", 1)[0]
            scan_last_id = _first_int(last_ids.get(feed_type)) if feed_type else 0
            raw_json = json.dumps(item.get("raw") if isinstance(item.get("raw"), dict) else item, ensure_ascii=False)

            existing = existing_by_external_id.get(external_id)
            if existing is None and external_id not in touched:
                touched.add(external_id)
                self.session.add(ExternalMonitorRecord(
                    source_key=SOURCE_KEY,
                    feed_type=feed_type,
                    external_id=external_id,
                    platform=_first_text(item.get("platform")),
                    title=_first_text(item.get("title")),
                    url=_first_text(item.get("url"), item.get("link")),
                    raw_json=raw_json,
                    scan_last_id=scan_last_id,
                    fetched_at=now,
                    updated_at=now,
                ))
            else:
                if existing is None:
                    continue
                existing.feed_type = feed_type
                existing.platform = _first_text(item.get("platform"))
                existing.title = _first_text(item.get("title"))
                existing.url = _first_text(item.get("url"), item.get("link"))
                existing.raw_json = raw_json
                existing.scan_last_id = scan_last_id
                existing.updated_at = now

        await self.session.commit()

    async def _sync_contents(self, records: list[dict], force: bool = False) -> dict:
        stats = self._empty_content_stats()
        stats["fetched"] = len(records)
        if not records:
            return stats

        result = await self.session.execute(select(Game))
        games = list(result.scalars().all())
        games_by_name = {g.name.strip(): g for g in games if g.name}

        source_ids = {
            f"{SOURCE_KEY}:{_first_text(item.get('external_id'), item.get('id'))}"
            for item in records
            if _first_text(item.get("external_id"), item.get("id"))
        }
        existing_source_ids: set[str] = set()
        if source_ids:
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

            title = _first_text(item.get("title"))
            body = _first_text(item.get("summary"), item.get("body"), item.get("description"))
            game = self._match_game(_first_text(item.get("game_name"), item.get("game")), title, body, games_by_name, games)
            if game is None:
                stats["unmatched_games"] += 1
                continue

            platform_key, platform = _normalize_platform(item.get("platform"))
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
                    "raw_feed_type": _first_text(item.get("raw_feed_type")),
                    "raw": item.get("raw") if isinstance(item.get("raw"), dict) else item,
                }, ensure_ascii=False),
            ))
            stats["inserted"] += 1

        await self.session.commit()
        return stats

    @staticmethod
    def _match_game(game_name: str, title: str, body: str, games_by_name: dict[str, Game], games: list[Game]) -> Game | None:
        if game_name and game_name in games_by_name:
            return games_by_name[game_name]
        text = f"{title} {body}"
        matches = [game for game in games if game.name and game.name in text]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return max(matches, key=lambda game: len(game.name))
        return None

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

    def _set_status(
        self,
        status: str,
        message: str,
        content_stats: dict,
        config_stats: dict,
        last_ids: dict[str, int],
    ) -> dict:
        global LAST_SYNC_STATUS
        LAST_SYNC_STATUS = {
            "source_key": SOURCE_KEY,
            "status": status,
            "message": message,
            "contents": content_stats,
            "configs": config_stats,
            "last_ids": last_ids,
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
