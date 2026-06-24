"""Dashboard summary tests."""

import asyncio
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.dashboard import get_dashboard_summary
from app.database import Base
from app.models.daily_report import DailyReport
from app.models.demand import Demand, ToolType
from app.models.game import Game, GameGenre, GameStatus

test_db_path = Path(tempfile.gettempdir()) / "req_gen_dashboard_summary_test.db"
test_engine = create_async_engine(f"sqlite+aiosqlite:///{test_db_path}", echo=False)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


async def reset_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed_report(report_date: date):
    async with TestSession() as session:
        session.add(DailyReport(
            report_date=report_date,
            summary="summary",
            top_demand_ids="[]",
            trending_game_ids="[]",
            total_demands=0,
        ))
        await session.commit()


async def seed_demands(demand_dates: list[date]):
    async with TestSession() as session:
        game = Game(
            name="测试游戏",
            genre=GameGenre.rpg,
            status=GameStatus.operating,
        )
        session.add(game)
        await session.flush()

        for index, demand_date in enumerate(demand_dates):
            session.add(Demand(
                game_id=game.id,
                tool_type=ToolType.other,
                title=f"测试需求{index}",
                potential_score=90 - index,
                tool_feasibility=3,
                demand_date=demand_date,
            ))
        await session.commit()


async def fetch_summary():
    async with TestSession() as session:
        return await get_dashboard_summary(session)


class DashboardSummaryTest(unittest.TestCase):
    def setUp(self):
        asyncio.run(reset_tables())

    def test_summary_marks_today_analysis_incomplete_without_today_report(self):
        asyncio.run(seed_report(date.today() - timedelta(days=1)))

        summary = asyncio.run(fetch_summary())

        self.assertFalse(summary.today_analysis_completed)

    def test_summary_marks_today_analysis_completed_when_today_report_exists(self):
        asyncio.run(seed_report(date.today()))

        summary = asyncio.run(fetch_summary())

        self.assertTrue(summary.today_analysis_completed)

    def test_june_24_summary_shows_all_historical_demands_without_top_ten_limit(self):
        display_date = date(2026, 6, 24)
        asyncio.run(seed_demands([display_date - timedelta(days=1)] * 11 + [display_date]))

        with patch("app.api.dashboard.date") as mocked_date:
            mocked_date.today.return_value = display_date
            summary = asyncio.run(fetch_summary())

        self.assertEqual(summary.total_demands_today, 12)
        self.assertEqual(len(summary.top_demands), 12)

    def test_after_june_24_summary_returns_to_today_only(self):
        next_date = date(2026, 6, 25)
        asyncio.run(seed_demands([next_date - timedelta(days=1)] + [next_date] * 11))

        with patch("app.api.dashboard.date") as mocked_date:
            mocked_date.today.return_value = next_date
            summary = asyncio.run(fetch_summary())

        self.assertEqual(summary.total_demands_today, 11)
        self.assertEqual(len(summary.top_demands), 10)


if __name__ == "__main__":
    unittest.main()
