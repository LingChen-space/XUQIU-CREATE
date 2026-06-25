"""雷达采集与互动快照测试。"""

import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.game import Game, GameGenre, GameStatus
from app.models.platform_content import ContentPlatform, ContentType, PlatformContent
from app.models.radar import (
    ContentConcept,
    ContentMetricHourly,
    ContentMetricSnapshot,
    ContentScanState,
    RadarClue,
    RadarClueLevel,
)
from app.services.data_adapter import DataAdapter, exploration_keywords_for_game
from app.services.radar_runner import (
    backfill_radar_history,
    compact_metric_snapshots,
    exploration_interval_minutes,
)


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

    def test_exploration_uses_game_name_aliases_and_experience_names(self):
        keywords = exploration_keywords_for_game("和平精英")
        self.assertIn("和平精英", keywords)
        self.assertIn("和平精英体验服", keywords)
        self.assertIn("地铁逃生", keywords)
        self.assertEqual(len(keywords), len(set(keywords)))

    def test_history_backfill_creates_completed_scan_and_initial_snapshot_without_clue(self):
        async def scenario():
            game_id = await seed_game()
            async with Session() as session:
                content = PlatformContent(
                    game_id=game_id,
                    platform=ContentPlatform.taptap,
                    content_type=ContentType.post,
                    source_id="history-source",
                    title="战绩查询工具",
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
                concepts = (
                    await session.execute(select(func.count()).select_from(ContentConcept))
                ).scalar_one()
                clues = (
                    await session.execute(select(func.count()).select_from(RadarClue))
                ).scalar_one()
                return result, state.rule_status, state.model_status, snapshots, concepts, clues

        self.assertEqual(asyncio.run(scenario()), (1, "completed", "completed", 1, 1, 0))

    def test_history_backfill_only_alerts_recent_level_three_keyword(self):
        async def scenario():
            game_id = await seed_game()
            async with Session() as session:
                recent = PlatformContent(
                    game_id=game_id,
                    platform=ContentPlatform.taptap,
                    content_type=ContentType.post,
                    source_id="recent-hot",
                    title="2.0版本更新内容将在6月28日上线",
                    published_at=datetime.now(),
                )
                old = PlatformContent(
                    game_id=game_id,
                    platform=ContentPlatform.taptap,
                    content_type=ContentType.post,
                    source_id="old-hot",
                    title="1.0版本更新内容与BUG修复",
                    published_at=datetime.now() - timedelta(days=8),
                )
                session.add_all([recent, old])
                await session.commit()
                await backfill_radar_history(session)
                clues = (await session.execute(select(RadarClue))).scalars().all()
                return [(clue.term, clue.level) for clue in clues]

        self.assertEqual(
            asyncio.run(scenario()),
            [("版本更新内容", RadarClueLevel.urgent)],
        )

    def test_metric_snapshots_older_than_thirty_days_are_compacted_hourly(self):
        async def scenario():
            game_id = await seed_game()
            now = datetime.now()
            archive_hour = (now - timedelta(days=31)).replace(
                minute=0,
                second=0,
                microsecond=0,
            )
            async with Session() as session:
                content = PlatformContent(
                    game_id=game_id,
                    platform=ContentPlatform.taptap,
                    content_type=ContentType.post,
                    source_id="archive-source",
                    title="归档内容",
                    published_at=now - timedelta(days=40),
                )
                session.add(content)
                await session.flush()
                session.add_all([
                    ContentMetricSnapshot(
                        content_id=content.id,
                        platform=ContentPlatform.taptap,
                        view_count=100,
                        like_count=10,
                        comment_count=2,
                        share_count=1,
                        captured_at=archive_hour + timedelta(minutes=5),
                    ),
                    ContentMetricSnapshot(
                        content_id=content.id,
                        platform=ContentPlatform.taptap,
                        view_count=180,
                        like_count=15,
                        comment_count=4,
                        share_count=2,
                        captured_at=archive_hour + timedelta(minutes=20),
                    ),
                    ContentMetricSnapshot(
                        content_id=content.id,
                        platform=ContentPlatform.taptap,
                        view_count=220,
                        captured_at=now - timedelta(days=29),
                    ),
                ])
                await session.commit()

                result = await compact_metric_snapshots(session, now=now)
                raw_count = (
                    await session.execute(select(func.count()).select_from(ContentMetricSnapshot))
                ).scalar_one()
                hourly = (await session.execute(select(ContentMetricHourly))).scalar_one()
                return result, raw_count, hourly.view_count, hourly.like_count

        self.assertEqual(asyncio.run(scenario()), ((2, 1), 1, 180, 15))


if __name__ == "__main__":
    unittest.main()
