"""TapTap proxy group sync tests."""

import asyncio
import tempfile
import unittest
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.game import Game, GameGenre, GameStatus
from app.models.platform_search_config import PlatformSearchConfig
from app.services.tap_proxy_sync import TapProxySyncService


test_db_path = Path(tempfile.gettempdir()) / "req_gen_tap_proxy_sync_test.db"
test_engine = create_async_engine(f"sqlite+aiosqlite:///{test_db_path}", echo=False)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


class FakeTapProxyClient:
    def __init__(self):
        self.group_ids: list[str] = []

    @property
    def configured(self) -> bool:
        return True

    async def fetch_feed_by_group(self, group_id: str, limit: int = 10, max_pages: int = 2):
        self.group_ids.append(group_id)
        return []


async def reset_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def run_sync_with_mixed_taptap_configs():
    async with TestSession() as session:
        game = Game(
            name="三角洲行动",
            genre=GameGenre.fps,
            publisher="腾讯",
            status=GameStatus.operating,
        )
        session.add(game)
        await session.flush()
        session.add_all([
            PlatformSearchConfig(
                game_id=None,
                platform="taptap",
                keywords="工具,体验服",
                enabled=True,
                crawl_count=200,
                source_key="manual",
            ),
            PlatformSearchConfig(
                game_id=game.id,
                platform="taptap",
                keywords="531928",
                enabled=True,
                crawl_count=10,
                source_key="tap_proxy",
            ),
        ])
        await session.commit()

        client = FakeTapProxyClient()
        result = await TapProxySyncService(session, client=client).sync()
        return result, client.group_ids


class TapProxySyncTest(unittest.TestCase):
    def setUp(self):
        asyncio.run(reset_tables())

    def test_sync_uses_only_bound_tap_proxy_group_configs(self):
        result, group_ids = asyncio.run(run_sync_with_mixed_taptap_configs())

        self.assertEqual(result["groups"], 1)
        self.assertEqual(group_ids, ["531928"])


if __name__ == "__main__":
    unittest.main()
