"""Data adapter collection tests."""

import asyncio
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.crawl_progress import CrawlProgress
from app.models.platform_search_config import PlatformSearchConfig
from app.services.data_adapter import DataAdapter

test_db_path = Path(tempfile.gettempdir()) / "req_gen_data_adapter_collection_test.db"
test_engine = create_async_engine(f"sqlite+aiosqlite:///{test_db_path}", echo=False)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


async def reset_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed_platform_configs():
    async with TestSession() as session:
        session.add_all([
            PlatformSearchConfig(platform="taptap", keywords="Tap关键词", enabled=True, crawl_count=10),
            PlatformSearchConfig(platform="douyin", keywords="抖音关键词", enabled=True, crawl_count=10),
            PlatformSearchConfig(platform="bilibili", keywords="B站关键词", enabled=True, crawl_count=10),
        ])
        await session.commit()


class DataAdapterCollectionTest(unittest.TestCase):
    def setUp(self):
        asyncio.run(reset_tables())

    def test_script_collection_skips_taptap_configs(self):
        asyncio.run(seed_platform_configs())

        async def run_case():
            async with TestSession() as session:
                configs = (
                    await session.execute(
                        select(PlatformSearchConfig).where(PlatformSearchConfig.enabled == True)  # noqa: E712
                    )
                ).scalars().all()
                combos = await DataAdapter(session)._ensure_progress_records(configs)
                progress = (
                    await session.execute(select(CrawlProgress).order_by(CrawlProgress.platform))
                ).scalars().all()
                return combos, progress

        combos, progress = asyncio.run(run_case())

        self.assertEqual([combo[0] for combo in combos], ["douyin", "bilibili"])
        self.assertEqual([record.platform for record in progress], ["bilibili", "douyin"])

    def test_progress_list_hides_disabled_taptap_records(self):
        async def run_case():
            async with TestSession() as session:
                session.add_all([
                    CrawlProgress(
                        platform="taptap",
                        keyword="旧Tap关键词",
                        crawl_count=200,
                        status="failed",
                    ),
                    CrawlProgress(
                        platform="douyin",
                        keyword="抖音关键词",
                        crawl_count=50,
                        status="completed",
                    ),
                ])
                await session.commit()

                return await DataAdapter(session).get_progress()

        progress = asyncio.run(run_case())

        self.assertEqual([record["platform"] for record in progress], ["douyin"])

    def test_bilibili_items_map_to_standard_content(self):
        item = {
            "source_id": "BV123",
            "title": "三角洲行动 配装工具",
            "description": "B站视频简介",
            "url": "https://www.bilibili.com/video/BV123",
            "play_count": 12000,
            "like_count": 900,
            "comment_count": 80,
            "pubdate": "2026-06-30 10:20:30",
        }

        async def run_case():
            async with TestSession() as session:
                return DataAdapter(session)._map_monitor_item(
                    "game-1",
                    "三角洲行动",
                    "bilibili",
                    item,
                    "配装工具",
                )

        mapped = asyncio.run(run_case())

        self.assertEqual(mapped["platform"], "B站")
        self.assertEqual(mapped["source_id"], "BV123")
        self.assertEqual(mapped["view_count"], 12000)
        self.assertEqual(mapped["like_count"], 900)
        self.assertEqual(mapped["comment_count"], 80)
        self.assertEqual(mapped["url"], "https://www.bilibili.com/video/BV123")


if __name__ == "__main__":
    unittest.main()
