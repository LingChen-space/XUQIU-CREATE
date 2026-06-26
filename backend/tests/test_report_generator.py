"""Report generator tests."""

import asyncio
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.daily_report import DailyReport
from app.models.demand import Demand, ToolType
from app.models.game import Game, GameGenre, GameStatus
from app.services.report_generator import ReportGenerator

test_db_path = Path(tempfile.gettempdir()) / "req_gen_report_generator_test.db"
test_engine = create_async_engine(f"sqlite+aiosqlite:///{test_db_path}", echo=False)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


async def reset_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed_daily_context(report_date: date, existing_summary: str | None = None):
    async with TestSession() as session:
        game = Game(
            name="测试游戏",
            genre=GameGenre.rpg,
            status=GameStatus.operating,
        )
        session.add(game)
        await session.flush()
        session.add(Demand(
            game_id=game.id,
            tool_type=ToolType.database_tool,
            title="测试游戏图鉴",
            potential_score=90,
            tool_feasibility=4,
            demand_date=report_date,
        ))
        if existing_summary is not None:
            session.add(DailyReport(
                report_date=report_date,
                summary=existing_summary,
                top_demand_ids="[]",
                trending_game_ids="[]",
                total_demands=1,
            ))
        await session.commit()


class ReportGeneratorTest(unittest.TestCase):
    def setUp(self):
        asyncio.run(reset_tables())

    def test_template_fallback_does_not_overwrite_existing_llm_summary(self):
        report_date = date(2026, 6, 26)
        existing_summary = "今日核心洞察集中在**测试游戏图鉴**，玩家需要结构化数据库能力。"
        asyncio.run(seed_daily_context(report_date, existing_summary))

        async def run_case():
            async with TestSession() as session:
                generator = ReportGenerator(session)
                with patch.object(
                    generator,
                    "_llm_summary",
                    AsyncMock(return_value="今日热点需求：\n测试游戏·数据库：测试游戏图鉴（潜力分90）"),
                ):
                    report = await generator.generate_daily_report(report_date)
                    return report.summary

        summary = asyncio.run(run_case())

        self.assertEqual(summary, existing_summary)

    def test_llm_summary_retries_once_when_first_completion_is_empty(self):
        report_date = date(2026, 6, 26)

        first_response = MagicMock()
        first_response.choices = [MagicMock()]
        first_response.choices[0].message.content = ""
        second_response = MagicMock()
        second_response.choices = [MagicMock()]
        second_response.choices[0].message.content = "今日核心洞察由 LLM 生成。"

        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=[first_response, second_response])

        async def run_case():
            async with TestSession() as session:
                generator = ReportGenerator(session)
                with patch("app.services.report_generator.build_async_client", return_value=client):
                    return await generator._llm_summary(
                        report_date=report_date,
                        demands=[MagicMock(signal_snapshot="{}", potential_score=90, tool_type=ToolType.database_tool)],
                        top_demands=[MagicMock(
                            game_id="game-1",
                            title="测试游戏图鉴",
                            potential_score=90,
                            tool_feasibility=4,
                            tool_type=ToolType.database_tool,
                        )],
                        games_map={"game-1": MagicMock(name="测试游戏")},
                        fallback="今日热点需求：\n测试游戏·数据库：测试游戏图鉴（潜力分90）",
                    )

        summary = asyncio.run(run_case())

        self.assertEqual(summary, "今日核心洞察由 LLM 生成。")
        self.assertEqual(client.chat.completions.create.await_count, 2)


if __name__ == "__main__":
    unittest.main()
