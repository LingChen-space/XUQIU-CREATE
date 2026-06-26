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

        self.assertEqual([combo[0] for combo in combos], ["douyin"])
        self.assertEqual([record.platform for record in progress], ["douyin"])


if __name__ == "__main__":
    unittest.main()
