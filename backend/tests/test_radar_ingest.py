"""雷达采集与互动快照测试。"""

import asyncio
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.game import Game, GameGenre, GameStatus
from app.models.platform_content import ContentPlatform, ContentType, PlatformContent
from app.models.radar import ContentMetricSnapshot, ContentScanState
from app.services.data_adapter import DataAdapter
from app.services.radar_runner import backfill_radar_history, exploration_interval_minutes


db_path = Path(tempfile.gettempdir()) / "req_gen_radar_ingest_test.db"
engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def reset_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed_game() -> str:
    async with Session() as session:
        game = Game(
            name="测试游戏",
            genre=GameGenre.rpg,
            status=GameStatus.operating,
        )
        session.add(game)
        await session.commit()
        return game.id


def mapped_item(game_id: str, *, views: int, title: str = "已知工具需求") -> dict:
    return {
        "game_id": game_id,
        "platform": ContentPlatform.taptap,
        "content_type": ContentType.post,
        "source_id": "same-source",
        "url": "https://example.com/same-source",
        "title": title,
        "body": "正文",
        "author": "用户",
        "view_count": views,
        "like_count": views // 10,
        "comment_count": views // 20,
        "share_count": views // 50,
        "hot_score": 20,
        "published_at": datetime.now(),
        "extra_data": "{}",
    }


class RadarIngestTest(unittest.TestCase):
    def setUp(self):
        asyncio.run(reset_tables())

    def test_duplicate_source_updates_content_and_writes_metric_snapshot(self):
        async def scenario():
            game_id = await seed_game()
            async with Session() as session:
                adapter = DataAdapter(session)
                inserted, _ = await adapter._dedup_and_insert([mapped_item(game_id, views=100)])
                updated, stats = await adapter._dedup_and_insert([mapped_item(game_id, views=500)])

                content = (await session.execute(select(PlatformContent))).scalar_one()
                snapshot_count = (
                    await session.execute(select(func.count()).select_from(ContentMetricSnapshot))
                ).scalar_one()
                scan_count = (
                    await session.execute(select(func.count()).select_from(ContentScanState))
                ).scalar_one()
                return inserted, updated, stats, content.view_count, snapshot_count, scan_count

        inserted, updated, stats, views, snapshots, scans = asyncio.run(scenario())
        self.assertEqual(inserted, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(stats["updated_existing"], 1)
        self.assertEqual(views, 500)
        self.assertEqual(snapshots, 2)
        self.assertEqual(scans, 1)

    def test_exploration_mode_keeps_unknown_content_without_tool_keyword(self):
        async def scenario():
            game_id = await seed_game()
            async with Session() as session:
                adapter = DataAdapter(session)
                inserted, stats = await adapter._dedup_and_insert(
                    [mapped_item(game_id, views=10, title="星蚀核心首次曝光")],
                    allow_unrelated=True,
                )
                return inserted, stats["filtered_unrelated"]

        self.assertEqual(asyncio.run(scenario()), (1, 0))

    def test_exploration_cadence_depends_on_game_priority(self):
        self.assertEqual(exploration_interval_minutes(3), 5)
        self.assertEqual(exploration_interval_minutes(5), 5)
        self.assertEqual(exploration_interval_minutes(1), 30)
        self.assertEqual(exploration_interval_minutes(2), 30)

    def test_history_backfill_creates_completed_scan_and_initial_snapshot_without_clue(self):
        async def scenario():
            game_id = await seed_game()
            async with Session() as session:
                content = PlatformContent(
                    game_id=game_id,
                    platform=ContentPlatform.taptap,
                    content_type=ContentType.post,
                    source_id="history-source",
                    title="「星蚀核心」首次曝光",
                    view_count=100,
                    like_count=10,
                    comment_count=3,
                    share_count=1,
                    published_at=datetime.now(),
                )
                session.add(content)
                await session.commit()
                result = await backfill_radar_history(session)
                state = await session.get(ContentScanState, content.id)
                snapshots = (
                    await session.execute(select(func.count()).select_from(ContentMetricSnapshot))
                ).scalar_one()
                return result, state.rule_status, state.model_status, snapshots

        self.assertEqual(asyncio.run(scenario()), (1, "completed", "completed", 1))


if __name__ == "__main__":
    unittest.main()
