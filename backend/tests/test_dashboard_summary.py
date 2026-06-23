"""Dashboard summary tests."""

import asyncio
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.dashboard import get_dashboard_summary
from app.database import Base
from app.models.daily_report import DailyReport

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


if __name__ == "__main__":
    unittest.main()
