"""Dashboard summary tests."""

import asyncio
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.dashboard import get_dashboard_summary
from app.database import Base
from app.models.daily_report import DailyReport
from app.models.demand import Demand, ToolType
from app.models.game import Game, GameGenre, GameStatus
from app.models.radar import RadarClue, RadarClueLevel, RadarClueStatus, RadarClueType

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


async def seed_radar_clues(display_date: date):
    async with TestSession() as session:
        game = Game(
            name="洛克王国世界",
            genre=GameGenre.rpg,
            status=GameStatus.operating,
            priority_weight=3,
        )
        experience_game = Game(
            name="洛克王国世界体验服",
            genre=GameGenre.rpg,
            status=GameStatus.operating,
            priority_weight=3,
        )
        session.add_all([game, experience_game])
        await session.flush()

        session.add_all([
            RadarClue(
                signature="radar:locke:map",
                game_id=game.id,
                clue_type=RadarClueType.new_demand,
                level=RadarClueLevel.important,
                status=RadarClueStatus.pending,
                title="洛克王国世界互动地图",
                summary="多条内容提到互动地图工具",
                term="互动地图",
                trigger_reason="标准词首次集中命中",
                evidence_content_ids='["a","b"]',
                score_detail=json.dumps({
                    "keyword_priority": "level_1",
                    "keyword_category": "工具箱工具核心词",
                    "independent_evidence_count": 2,
                }, ensure_ascii=False),
                suggested_tool_type="交互地图",
                total_score=83,
                first_seen_at=datetime.combine(display_date, datetime.min.time()),
                last_seen_at=datetime.combine(display_date, datetime.min.time()),
            ),
            RadarClue(
                signature="radar:locke-exp:notice",
                game_id=experience_game.id,
                clue_type=RadarClueType.new_demand,
                level=RadarClueLevel.urgent,
                status=RadarClueStatus.pending,
                title="体验服爆料",
                term="版本爆料",
                total_score=90,
                first_seen_at=datetime.combine(display_date, datetime.min.time()),
                last_seen_at=datetime.combine(display_date, datetime.min.time()),
            ),
            RadarClue(
                signature="radar:locke:old",
                game_id=game.id,
                clue_type=RadarClueType.new_demand,
                level=RadarClueLevel.important,
                status=RadarClueStatus.pending,
                title="旧雷达词",
                term="旧词",
                total_score=70,
                first_seen_at=datetime.combine(display_date - timedelta(days=1), datetime.min.time()),
                last_seen_at=datetime.combine(display_date - timedelta(days=1), datetime.min.time()),
            ),
        ])
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

    def test_summary_returns_today_non_experience_radar_clues(self):
        display_date = date(2026, 6, 26)
        asyncio.run(seed_radar_clues(display_date))

        with patch("app.api.dashboard.date") as mocked_date:
            mocked_date.today.return_value = display_date
            summary = asyncio.run(fetch_summary())

        self.assertEqual(len(summary.radar_clues), 1)
        clue = summary.radar_clues[0]
        self.assertEqual(clue.term, "互动地图")
        self.assertEqual(clue.game_name, "洛克王国世界")
        self.assertEqual(clue.evidence_count, 2)


if __name__ == "__main__":
    unittest.main()
