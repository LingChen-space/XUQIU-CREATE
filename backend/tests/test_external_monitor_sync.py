"""Tap + KuaiBao forum external monitor sync tests."""

import asyncio
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.game import Game, GameGenre, GameStatus
from app.models.platform_content import ContentPlatform, PlatformContent
from app.models.platform_search_config import PlatformSearchConfig
from app.services.external_monitor_sync import TapKbExportClient, TapKbForumSyncService

test_db_path = Path(tempfile.gettempdir()) / "req_gen_external_monitor_test.db"
test_engine = create_async_engine(f"sqlite+aiosqlite:///{test_db_path}", echo=False)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


class FakeTapKbClient(TapKbExportClient):
    def __init__(self, contents: list[dict], configs: list[dict]):
        self.contents = contents
        self.configs = configs

    async def fetch_contents(self, days: int) -> list[dict]:
        return self.contents

    async def fetch_configs(self) -> list[dict]:
        return self.configs


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
        asyncio.run(create_game("三角洲行动"))

    def test_sync_maps_taptap_and_kuaibao_forum_content(self):
        client = FakeTapKbClient(
            contents=[
                {
                    "external_id": "tap-1",
                    "platform": "TapTap",
                    "game_name": "三角洲行动",
                    "title": "三角洲行动卡战备怎么搞",
                    "summary": "战备值和配装工具求推荐",
                    "url": "https://www.taptap.cn/moment/tap-1",
                    "author": "玩家A",
                    "like_count": 120,
                    "comment_count": 80,
                    "view_count": 1000,
                    "published_at": "2026-06-20 12:00:00",
                    "keyword_hit": "卡战备",
                },
                {
                    "external_id": "kb-1",
                    "platform": "快爆论坛",
                    "game_name": "三角洲行动",
                    "title": "三角洲行动地图资源点整理",
                    "summary": "地图工具和路线标点需求很高",
                    "url": "https://bbs.3839.com/thread/kb-1",
                    "author": "玩家B",
                    "like_count": 90,
                    "comment_count": 60,
                    "view_count": 800,
                    "published_at": "2026-06-20T13:00:00",
                    "keyword_hit": "地图",
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
            "game_name": "三角洲行动",
            "title": "三角洲行动配装工具",
            "summary": "战备和配装计算器",
            "like_count": 50,
            "comment_count": 30,
            "published_at": "2026-06-20 12:00:00",
        }
        client = FakeTapKbClient(contents=[item, dict(item)], configs=[])

        result = asyncio.run(run_sync(client))

        self.assertEqual(result["contents"]["inserted"], 1)
        self.assertEqual(result["contents"]["duplicates"], 1)
        self.assertEqual(len(asyncio.run(fetch_contents())), 1)

    def test_config_sync_does_not_overwrite_manual_keywords(self):
        async def seed_manual_config():
            async with TestSession() as session:
                session.add(PlatformSearchConfig(
                    platform="taptap",
                    keywords="手工词",
                    enabled=True,
                    crawl_count=50,
                ))
                await session.commit()

        asyncio.run(seed_manual_config())
        client = FakeTapKbClient(
            contents=[],
            configs=[
                {
                    "group_name": "攻略组",
                    "platform": "TapTap",
                    "keywords": "工具|地图|卡战备",
                    "enabled": True,
                    "updated_at": "2026-06-20 12:00:00",
                }
            ],
        )

        result = asyncio.run(run_sync(client))

        self.assertEqual(result["configs"]["upserted"], 1)
        configs = asyncio.run(fetch_configs())
        self.assertEqual(len(configs), 2)
        self.assertIn("手工词", {c.keywords for c in configs})
        external = next(c for c in configs if c.source_key == "tap_kb_forum")
        self.assertEqual(external.keywords, "工具,地图,卡战备")


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


if __name__ == "__main__":
    unittest.main()
