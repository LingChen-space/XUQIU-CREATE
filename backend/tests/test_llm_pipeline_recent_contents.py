"""每日分析内容窗口测试。"""

import asyncio
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.game import Game, GameGenre, GameStatus
from app.models.demand import Demand, ToolType
from app.models.platform_content import ContentPlatform, ContentType, PlatformContent
from app.services.llm_pipeline import LLMPipeline


db_path = Path(tempfile.gettempdir()) / "req_gen_llm_recent_contents_test.db"
engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def reset_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


class LLMPipelineRecentContentsTest(unittest.TestCase):
    def setUp(self):
        asyncio.run(reset_tables())

    def test_today_collected_content_is_included_even_if_published_earlier(self):
        async def scenario():
            window_date = date(2026, 6, 26)
            async with Session() as session:
                game = Game(
                    name="洛克王国世界",
                    genre=GameGenre.rpg,
                    status=GameStatus.operating,
                )
                session.add(game)
                await session.flush()
                session.add(PlatformContent(
                    game_id=game.id,
                    platform=ContentPlatform.douyin,
                    content_type=ContentType.video,
                    source_id="old-published-today-collected",
                    url="https://example.com/video",
                    title="洛克王国世界互动地图工具",
                    body="今天新采集到，但视频发布时间较早",
                    published_at=datetime(2026, 6, 19, 10, 0),
                    collected_at=datetime(2026, 6, 26, 9, 0),
                ))
                await session.commit()

                contents = await LLMPipeline(session)._get_recent_contents(game.id, window_date)
                return [content.source_id for content in contents]

        self.assertEqual(
            asyncio.run(scenario()),
            ["old-published-today-collected"],
        )

    def test_pipeline_reuses_existing_standard_demand_across_dates(self):
        async def scenario():
            async with Session() as session:
                game = Game(
                    name="三角洲行动",
                    genre=GameGenre.fps,
                    status=GameStatus.operating,
                    priority_weight=3,
                )
                session.add(game)
                await session.flush()
                session.add(Demand(
                    game_id=game.id,
                    tool_type=ToolType.build_calc,
                    title="三角洲行动卡战备战备/改枪工具",
                    demand_date=date(2026, 6, 26),
                    llm_analysis='{"reasoning": "内容集中提到卡战备和战备值配装需求。"}',
                ))
                session.add(PlatformContent(
                    game_id=game.id,
                    platform=ContentPlatform.taptap,
                    content_type=ContentType.post,
                    source_id="delta-loadout-new",
                    url="https://example.com/delta-loadout-new",
                    title="三角洲行动卡战备怎么搞",
                    body="卡战备工具和战备值配装需求很高",
                    published_at=datetime(2026, 6, 29, 9, 0),
                    collected_at=datetime(2026, 6, 29, 9, 0),
                    hot_score=80,
                ))
                session.add(PlatformContent(
                    game_id=game.id,
                    platform=ContentPlatform.taptap,
                    content_type=ContentType.post,
                    source_id="delta-loadout-new-2",
                    url="https://example.com/delta-loadout-new-2",
                    title="三角洲行动战备值配装推荐",
                    body="卡战备和改枪参数需要整理",
                    published_at=datetime(2026, 6, 29, 10, 0),
                    collected_at=datetime(2026, 6, 29, 10, 0),
                    hot_score=75,
                ))
                await session.commit()

                demands = await LLMPipeline(session).run_pipeline([game.id], date(2026, 6, 29))
                rows = (await session.execute(select(Demand))).scalars().all()
                return demands, rows

        demands, rows = asyncio.run(scenario())

        self.assertEqual(len(rows), 1)
        self.assertEqual(len(demands), 1)
        self.assertEqual(rows[0].demand_date, date(2026, 6, 29))


if __name__ == "__main__":
    unittest.main()
