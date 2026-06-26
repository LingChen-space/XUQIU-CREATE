"""每日分析内容窗口测试。"""

import asyncio
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.game import Game, GameGenre, GameStatus
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


if __name__ == "__main__":
    unittest.main()
