"""内容互动突增检测测试。"""

import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.game import Game, GameGenre, GameStatus
from app.models.platform_content import ContentPlatform, ContentType, PlatformContent
from app.models.radar import ContentMetricSnapshot, RadarClue, RadarClueLevel, RadarClueType
from app.services.engagement_surge import EngagementSurgeDetector, classify_surge
from app.services.radar import RadarService


db_path = Path(tempfile.gettempdir()) / "req_gen_engagement_surge_test.db"
engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def reset_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


class EngagementSurgeTest(unittest.TestCase):
    def setUp(self):
        asyncio.run(reset_tables())

    def test_p95_and_p99_baselines_classify_important_and_urgent(self):
        baseline = [float(i) for i in range(1, 101)]
        important = classify_surge(
            delta={"views": 1000, "likes": 50, "comments": 20, "shares": 5},
            elapsed_minutes=5,
            baseline_scores=baseline,
            weighted_velocity=96,
        )
        urgent = classify_surge(
            delta={"views": 2000, "likes": 100, "comments": 40, "shares": 10},
            elapsed_minutes=5,
            baseline_scores=baseline,
            weighted_velocity=120,
        )

        self.assertEqual(important["level"], RadarClueLevel.important)
        self.assertGreaterEqual(important["percentile"], 95)
        self.assertEqual(urgent["level"], RadarClueLevel.urgent)
        self.assertGreaterEqual(urgent["percentile"], 99)

    def test_minimum_increment_is_required_even_above_small_baseline(self):
        result = classify_surge(
            delta={"views": 10, "likes": 1, "comments": 0, "shares": 0},
            elapsed_minutes=5,
            baseline_scores=[0.1] * 30,
            weighted_velocity=10,
        )
        self.assertIsNone(result)

    def test_content_snapshots_create_traceable_surge_clue(self):
        async def scenario():
            async with Session() as session:
                game = Game(
                    name="三角洲行动",
                    genre=GameGenre.fps,
                    status=GameStatus.operating,
                )
                session.add(game)
                await session.flush()
                content = PlatformContent(
                    game_id=game.id,
                    platform=ContentPlatform.taptap,
                    content_type=ContentType.post,
                    source_id="surge-source",
                    title="卡战备技巧讨论突然升温",
                    published_at=datetime.now() - timedelta(hours=1),
                )
                session.add(content)
                await session.flush()
                start = datetime.now() - timedelta(minutes=5)
                session.add_all([
                    ContentMetricSnapshot(
                        content_id=content.id,
                        platform=content.platform,
                        view_count=100,
                        like_count=10,
                        comment_count=2,
                        share_count=0,
                        captured_at=start,
                    ),
                    ContentMetricSnapshot(
                        content_id=content.id,
                        platform=content.platform,
                        view_count=1300,
                        like_count=90,
                        comment_count=100,
                        share_count=8,
                        captured_at=start + timedelta(minutes=5),
                    ),
                ])
                await session.commit()
                await RadarService(session).scan_content_rules(content.id)

                detector = EngagementSurgeDetector(session)

                async def fake_baseline(*args, **kwargs):
                    return [float(i) for i in range(1, 101)]

                detector._baseline_scores = fake_baseline
                clue = await detector.evaluate_content(content.id)
                stored = (await session.execute(select(RadarClue))).scalar_one()
                return clue, stored

        clue, stored = asyncio.run(scenario())
        self.assertIsNotNone(clue)
        self.assertEqual(stored.clue_type, RadarClueType.new_demand)
        self.assertEqual(stored.term, "卡战备技巧")
        self.assertEqual(stored.level, RadarClueLevel.urgent)
        self.assertIn("delta_5m", stored.engagement_detail)


if __name__ == "__main__":
    unittest.main()
