"""Tap + KuaiBao forum external monitor sync tests."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.external_monitor_cursor import ExternalMonitorCursor
from app.models.external_monitor_record import ExternalMonitorRecord
from app.models.game import Game, GameGenre, GameStatus
from app.models.platform_content import ContentPlatform, PlatformContent
from app.models.platform_search_config import PlatformSearchConfig
from app.services.external_monitor_sync import TapKbApiClient, TapKbExportClient, TapKbForumSyncService

GAME_NAME = "\u4e09\u89d2\u6d32\u884c\u52a8"
KB_FORUM = "\u5feb\u7206\u8bba\u575b"

test_db_path = Path(tempfile.gettempdir()) / "req_gen_external_monitor_test.db"
test_engine = create_async_engine(f"sqlite+aiosqlite:///{test_db_path}", echo=False)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


class FakeTapKbClient(TapKbExportClient):
    def __init__(self, contents: list[dict], configs: list[dict]):
        self.contents = contents
        self.configs = configs

    async def fetch_contents(self, days: int, last_ids: dict[str, int] | None = None):
        return self.contents

    async def fetch_configs(self) -> list[dict]:
        return self.configs


class FakeIncrementalTapKbClient(TapKbExportClient):
    def __init__(self):
        self.requested_last_ids: dict[str, int] = {}

    async def fetch_contents(self, days: int, last_ids: dict[str, int] | None = None):
        self.requested_last_ids = last_ids or {}
        return {
            "records": [
                {
                    "external_id": "tap:50",
                    "platform": "TapTap",
                    "game_name": GAME_NAME,
                    "title": f"{GAME_NAME}\u5361\u6218\u5907\u600e\u4e48\u641e",
                    "url": "https://www.taptap.cn/moment/50",
                },
                {
                    "external_id": "hykb:80",
                    "platform": KB_FORUM,
                    "game_name": GAME_NAME,
                    "title": f"{GAME_NAME}\u5730\u56fe\u8d44\u6e90\u70b9\u6574\u7406",
                    "url": "https://bbs.3839.com/thread-80.htm",
                },
            ],
            "last_ids": {"tap": 100, "hykb": 120},
        }

    async def fetch_configs(self) -> list[dict]:
        return []


class FakeEmptyZeroLastIdTapKbClient(TapKbExportClient):
    async def fetch_contents(self, days: int, last_ids: dict[str, int] | None = None):
        return {"records": [], "last_ids": {"tap": 0, "hykb": 0}}

    async def fetch_configs(self) -> list[dict]:
        return []


async def reset_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def create_game(name: str):
    async with TestSession() as session:
        game = Game(
            name=name,
            genre=GameGenre.fps,
            publisher="4399",
            status=GameStatus.operating,
        )
        session.add(game)
        await session.commit()


class ExternalMonitorSyncTest(unittest.TestCase):
    def setUp(self):
        asyncio.run(reset_tables())
        asyncio.run(create_game(GAME_NAME))

    def test_sync_maps_taptap_and_kuaibao_forum_content(self):
        client = FakeTapKbClient(
            contents=[
                {
                    "external_id": "tap-1",
                    "platform": "TapTap",
                    "game_name": GAME_NAME,
                    "title": f"{GAME_NAME}\u5361\u6218\u5907\u600e\u4e48\u641e",
                    "summary": "\u6218\u5907\u503c\u548c\u914d\u88c5\u5de5\u5177\u6c42\u63a8\u8350",
                    "url": "https://www.taptap.cn/moment/tap-1",
                    "author": "\u73a9\u5bb6A",
                    "like_count": 120,
                    "comment_count": 80,
                    "view_count": 1000,
                    "published_at": "2026-06-20 12:00:00",
                    "keyword_hit": "\u5361\u6218\u5907",
                },
                {
                    "external_id": "kb-1",
                    "platform": KB_FORUM,
                    "game_name": GAME_NAME,
                    "title": f"{GAME_NAME}\u5730\u56fe\u8d44\u6e90\u70b9\u6574\u7406",
                    "summary": "\u5730\u56fe\u5de5\u5177\u548c\u8def\u7ebf\u6807\u70b9\u9700\u6c42\u5f88\u9ad8",
                    "url": "https://bbs.3839.com/thread/kb-1",
                    "author": "\u73a9\u5bb6B",
                    "like_count": 90,
                    "comment_count": 60,
                    "view_count": 800,
                    "published_at": "2026-06-20T13:00:00",
                    "keyword_hit": "\u5730\u56fe",
                },
            ],
            configs=[],
        )

        result = asyncio.run(run_sync(client))

        self.assertEqual(result["contents"]["inserted"], 2)
        self.assertEqual(result["contents"]["unmatched_games"], 0)
        rows = asyncio.run(fetch_contents())
        self.assertEqual({r.source_id for r in rows}, {"tap_kb_forum:tap-1", "tap_kb_forum:kb-1"})
        self.assertEqual({r.platform for r in rows}, {ContentPlatform.taptap, ContentPlatform.kuaibao_forum})

    def test_sync_deduplicates_by_external_id(self):
        item = {
            "external_id": "tap-dup",
            "platform": "TapTap",
            "game_name": GAME_NAME,
            "title": f"{GAME_NAME}\u914d\u88c5\u5de5\u5177",
            "summary": "\u6218\u5907\u548c\u914d\u88c5\u8ba1\u7b97\u5668",
            "like_count": 50,
            "comment_count": 30,
            "published_at": "2026-06-20 12:00:00",
        }
        client = FakeTapKbClient(contents=[item, dict(item)], configs=[])

        result = asyncio.run(run_sync(client))

        self.assertEqual(result["contents"]["inserted"], 1)
        self.assertEqual(result["contents"]["duplicates"], 1)
        self.assertEqual(len(asyncio.run(fetch_contents())), 1)

    def test_sync_stores_raw_records_even_when_game_unmatched(self):
        client = FakeTapKbClient(
            contents=[
                {
                    "external_id": "tap-unmatched",
                    "platform": "TapTap",
                    "title": "\u672a\u77e5\u6e38\u620f\u914d\u88c5\u5de5\u5177",
                    "url": "https://www.taptap.cn/moment/unmatched",
                    "raw_feed_type": "tap",
                    "raw": {"id": "unmatched", "title": "\u672a\u77e5\u6e38\u620f\u914d\u88c5\u5de5\u5177"},
                }
            ],
            configs=[],
        )

        result = asyncio.run(run_sync(client))

        self.assertEqual(result["contents"]["inserted"], 0)
        self.assertEqual(result["contents"]["unmatched_games"], 1)
        self.assertEqual(len(asyncio.run(fetch_contents())), 0)
        raw_rows = asyncio.run(fetch_raw_records())
        self.assertEqual(len(raw_rows), 1)
        self.assertEqual(raw_rows[0].source_key, "tap_kb_forum")
        self.assertEqual(raw_rows[0].feed_type, "tap")
        self.assertEqual(raw_rows[0].external_id, "tap-unmatched")
        self.assertEqual(raw_rows[0].title, "\u672a\u77e5\u6e38\u620f\u914d\u88c5\u5de5\u5177")

    def test_sync_creates_external_game_for_unconfigured_monitor_content(self):
        game_name = "\u65b0\u6e38\u620f"
        client = FakeTapKbClient(
            contents=[
                {
                    "external_id": "hykb-new-game",
                    "platform": KB_FORUM,
                    "game_name": game_name,
                    "title": f"\u300a{game_name}\u300b\u5730\u56fe\u5de5\u5177\u6c42\u63a8\u8350",
                    "url": "https://bbs.3839.com/thread-new-game.htm",
                    "raw_feed_type": "hykb",
                }
            ],
            configs=[],
        )

        result = asyncio.run(run_sync(client))

        self.assertEqual(result["contents"]["inserted"], 1)
        self.assertEqual(result["contents"]["unmatched_games"], 0)
        self.assertEqual(result["contents"]["created_games"], 1)
        games = asyncio.run(fetch_games())
        created = next((g for g in games if g.name == game_name), None)
        self.assertIsNotNone(created)
        self.assertEqual(created.publisher, "\u5916\u90e8\u76d1\u63a7")
        rows = asyncio.run(fetch_contents())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].game_id, created.id)

    def test_sync_infers_external_game_from_quoted_title(self):
        game_name = "\u5f71\u4e4b\u5203"
        client = FakeTapKbClient(
            contents=[
                {
                    "external_id": "tap-quoted-game",
                    "platform": "TapTap",
                    "title": f"\u300a{game_name}\u300b\u62bd\u5361\u8bb0\u5f55\u5de5\u5177\u4e0a\u7ebf",
                    "url": "https://www.taptap.cn/topic/quoted-game",
                    "raw_feed_type": "tap",
                }
            ],
            configs=[],
        )

        result = asyncio.run(run_sync(client))

        self.assertEqual(result["contents"]["inserted"], 1)
        self.assertEqual(result["contents"]["created_games"], 1)
        games = asyncio.run(fetch_games())
        self.assertIn(game_name, {g.name for g in games})

    def test_config_sync_does_not_overwrite_manual_keywords(self):
        async def seed_manual_config():
            async with TestSession() as session:
                session.add(PlatformSearchConfig(
                    platform="taptap",
                    keywords="\u624b\u5de5\u8bcd",
                    enabled=True,
                    crawl_count=50,
                ))
                await session.commit()

        asyncio.run(seed_manual_config())
        client = FakeTapKbClient(
            contents=[],
            configs=[
                {
                    "group_name": "\u653b\u7565\u7ec4",
                    "platform": "TapTap",
                    "keywords": "\u5de5\u5177|\u5730\u56fe|\u5361\u6218\u5907",
                    "enabled": True,
                    "updated_at": "2026-06-20 12:00:00",
                }
            ],
        )

        result = asyncio.run(run_sync(client))

        self.assertEqual(result["configs"]["upserted"], 1)
        configs = asyncio.run(fetch_configs())
        self.assertEqual(len(configs), 2)
        self.assertIn("\u624b\u5de5\u8bcd", {c.keywords for c in configs})
        external = next(c for c in configs if c.source_key == "tap_kb_forum")
        self.assertEqual(external.keywords, "\u5de5\u5177,\u5730\u56fe,\u5361\u6218\u5907")

    def test_sync_persists_returned_scan_last_id_not_matched_data_id(self):
        client = FakeIncrementalTapKbClient()

        result = asyncio.run(run_sync(client))

        self.assertEqual(result["contents"]["inserted"], 2)
        self.assertEqual(result["last_ids"], {"tap": 100, "hykb": 120})
        cursors = asyncio.run(fetch_cursors())
        self.assertEqual({c.feed_type: c.last_id for c in cursors}, {"tap": 100, "hykb": 120})

    def test_sync_uses_saved_last_id_for_incremental_fetch(self):
        asyncio.run(seed_cursor("tap", 100))
        asyncio.run(seed_cursor("hykb", 120))
        client = FakeIncrementalTapKbClient()

        asyncio.run(run_sync(client))

        self.assertEqual(client.requested_last_ids, {"tap": 100, "hykb": 120})

    def test_sync_does_not_overwrite_saved_last_id_with_zero_response(self):
        asyncio.run(seed_cursor("tap", 178394))
        asyncio.run(seed_cursor("hykb", 150390))
        client = FakeEmptyZeroLastIdTapKbClient()

        result = asyncio.run(run_sync(client))

        self.assertEqual(result["last_ids"], {})
        cursors = asyncio.run(fetch_cursors())
        self.assertEqual({c.feed_type: c.last_id for c in cursors}, {"tap": 178394, "hykb": 150390})

    def test_api_client_posts_signed_tap_and_hykb_requests(self):
        calls: list[dict] = []

        async def post_form(url: str, data: dict):
            calls.append({"url": url, "data": data})
            return {"code": 200, "last_id": 100 if data["type"] == "tap" else 120, "data": []}

        client = TapKbApiClient(
            api_url="http://example.test/api.php",
            secret="secret",
            clock=lambda: 1700000000,
            post_form=post_form,
        )

        result = asyncio.run(client.fetch_contents(days=30, last_ids={"tap": 88, "hykb": 99}))

        self.assertEqual(result["last_ids"], {"tap": 100, "hykb": 120})
        self.assertEqual([c["data"]["type"] for c in calls], ["tap", "hykb"])
        self.assertEqual([c["data"]["last_id"] for c in calls], [88, 99])
        self.assertEqual(calls[0]["data"]["time"], 1700000000)
        self.assertEqual(calls[0]["data"]["sign"], "4639dc588670101013c09d854e44d8c6")

    def test_api_client_defaults_to_official_production_url(self):
        client = TapKbApiClient()

        self.assertEqual(client.api_url, "https://news.4399.com/app/comm/tap_version2/api.php")

    def test_api_client_follows_official_host_redirects(self):
        captured_kwargs: dict = {}

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"code": 200, "last_id": 0, "data": []}

        class FakeHttpClient:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def post(self, url: str, data: dict):
                return FakeResponse()

        with patch("app.services.external_monitor_sync.httpx.AsyncClient", FakeHttpClient):
            client = TapKbApiClient(api_url="http://news.4399.com/app/comm/tap_version2/api.php", secret="secret")
            asyncio.run(client._post_form(client.api_url, {"type": "tap"}))

        self.assertIs(captured_kwargs.get("follow_redirects"), True)


async def run_sync(client: TapKbExportClient) -> dict:
    async with TestSession() as session:
        service = TapKbForumSyncService(session, client)
        return await service.sync(days=30)


async def fetch_contents() -> list[PlatformContent]:
    async with TestSession() as session:
        result = await session.execute(select(PlatformContent).order_by(PlatformContent.source_id))
        return list(result.scalars().all())


async def fetch_configs() -> list[PlatformSearchConfig]:
    async with TestSession() as session:
        result = await session.execute(select(PlatformSearchConfig).order_by(PlatformSearchConfig.created_at))
        return list(result.scalars().all())


async def fetch_cursors() -> list[ExternalMonitorCursor]:
    async with TestSession() as session:
        result = await session.execute(select(ExternalMonitorCursor).order_by(ExternalMonitorCursor.feed_type))
        return list(result.scalars().all())


async def fetch_raw_records() -> list[ExternalMonitorRecord]:
    async with TestSession() as session:
        result = await session.execute(select(ExternalMonitorRecord).order_by(ExternalMonitorRecord.external_id))
        return list(result.scalars().all())


async def fetch_games() -> list[Game]:
    async with TestSession() as session:
        result = await session.execute(select(Game).order_by(Game.name))
        return list(result.scalars().all())


async def seed_cursor(feed_type: str, last_id: int):
    async with TestSession() as session:
        session.add(ExternalMonitorCursor(source_key="tap_kb_forum", feed_type=feed_type, last_id=last_id))
        await session.commit()


if __name__ == "__main__":
    unittest.main()
