"""早期需求雷达数据模型测试。"""

import asyncio
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.game import Game, GameGenre, GameStatus
from app.models.platform_content import ContentPlatform, ContentType, PlatformContent
from app.models.radar import (
    ContentConcept,
    ContentMetricSnapshot,
    ContentScanState,
    RadarClue,
    RadarClueLevel,
    RadarClueStatus,
    RadarClueType,
    RadarCollectionState,
)


db_path = Path(tempfile.gettempdir()) / "req_gen_radar_models_test.db"
engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def reset_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed_game_and_content():
    async with Session() as session:
        game = Game(
            name="三角洲行动体验服",
            genre=GameGenre.fps,
            status=GameStatus.testing,
        )
        session.add(game)
        await session.flush()
        content = PlatformContent(
            game_id=game.id,
            platform=ContentPlatform.taptap,
            content_type=ContentType.post,
            source_id="radar-content-1",
            title="核电站新地图曝光",
            body="体验服新增撤离路线",
            published_at=datetime.now(),
        )
        session.add(content)
        await session.commit()
        return game.id, content.id


class RadarModelsTest(unittest.TestCase):
    def setUp(self):
        asyncio.run(reset_tables())

    def test_radar_models_persist_scan_concept_snapshot_clue_and_collection_state(self):
        async def scenario():
            game_id, content_id = await seed_game_and_content()
            async with Session() as session:
                session.add(ContentScanState(content_id=content_id))
                session.add(ContentConcept(
                    game_id=game_id,
                    content_id=content_id,
                    concept_type="entity",
                    value="核电站",
                    normalized_value="核电站",
                ))
                session.add(ContentMetricSnapshot(
                    content_id=content_id,
                    platform=ContentPlatform.taptap,
                    view_count=100,
                    like_count=20,
                    comment_count=8,
                    share_count=2,
                ))
                session.add(RadarClue(
                    signature=f"{game_id}:new_term:核电站",
                    game_id=game_id,
                    clue_type=RadarClueType.new_term,
                    level=RadarClueLevel.watch,
                    status=RadarClueStatus.pending,
                    title="首次发现：核电站",
                    term="核电站",
                    evidence_content_ids=f'["{content_id}"]',
                ))
                session.add(RadarCollectionState(
                    game_id=game_id,
                    platform="taptap",
                    mode="exploration",
                    status="completed",
                ))
                await session.commit()

                return (
                    len((await session.execute(select(ContentScanState))).scalars().all()),
                    len((await session.execute(select(ContentConcept))).scalars().all()),
                    len((await session.execute(select(ContentMetricSnapshot))).scalars().all()),
                    len((await session.execute(select(RadarClue))).scalars().all()),
                    len((await session.execute(select(RadarCollectionState))).scalars().all()),
                )

        self.assertEqual(asyncio.run(scenario()), (1, 1, 1, 1, 1))

    def test_same_game_concept_is_unique(self):
        async def scenario():
            game_id, content_id = await seed_game_and_content()
            async with Session() as session:
                session.add_all([
                    ContentConcept(
                        game_id=game_id,
                        content_id=content_id,
                        concept_type="entity",
                        value="核电站",
                        normalized_value="核电站",
                    ),
                    ContentConcept(
                        game_id=game_id,
                        content_id=content_id,
                        concept_type="entity",
                        value="核 电 站",
                        normalized_value="核电站",
                    ),
                ])
                with self.assertRaises(IntegrityError):
                    await session.commit()

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
