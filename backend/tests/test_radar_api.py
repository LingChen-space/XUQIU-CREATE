"""雷达查询与人工操作测试。"""

import asyncio
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.radar import (
    confirm_radar_clue,
    dismiss_radar_clue,
    get_radar_summary,
    list_radar_clues,
    promote_radar_clue,
)
from app.database import Base
from app.models.demand import Demand
from app.models.game import Game, GameGenre, GameStatus
from app.models.platform_content import ContentPlatform, ContentType, PlatformContent
from app.models.platform_search_config import PlatformSearchConfig
from app.models.radar import (
    ContentScanState,
    RadarClue,
    RadarClueLevel,
    RadarClueStatus,
    RadarClueType,
)


db_path = Path(tempfile.gettempdir()) / "req_gen_radar_api_test.db"
engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def reset_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed_clue() -> str:
    async with Session() as session:
        game = Game(
            name="测试游戏",
            genre=GameGenre.rpg,
            status=GameStatus.operating,
        )
        session.add(game)
        await session.flush()
        content = PlatformContent(
            game_id=game.id,
            platform=ContentPlatform.taptap,
            content_type=ContentType.post,
            source_id="evidence-source",
            url="https://example.com/evidence",
            title="星蚀核心怎么搭配",
            body="希望自动计算",
            published_at=datetime.now(),
        )
        session.add(content)
        await session.flush()
        session.add(ContentScanState(
            content_id=content.id,
            rule_status="completed",
            model_status="completed",
        ))
        session.add_all([
            PlatformSearchConfig(
                platform="taptap",
                keywords="工具",
                enabled=True,
                source_key="manual",
            ),
            PlatformSearchConfig(
                platform="douyin",
                keywords="工具",
                enabled=True,
                source_key="manual",
            ),
        ])
        clue = RadarClue(
            signature=f"{game.id}:new_demand:star",
            game_id=game.id,
            clue_type=RadarClueType.new_demand,
            level=RadarClueLevel.important,
            status=RadarClueStatus.pending,
            title="疑似新需求：星蚀核心搭配",
            summary="玩家希望自动生成搭配",
            term="星蚀核心",
            trigger_reason="首次出现且需求意图明确",
            evidence_content_ids=json.dumps([content.id]),
            score_detail=json.dumps({"novelty": 100, "demand_intent": 90}),
            suggested_tool_type="配装/战备工具",
            total_score=70,
        )
        session.add(clue)
        await session.commit()
        return clue.id


class RadarApiTest(unittest.TestCase):
    def setUp(self):
        asyncio.run(reset_tables())

    def test_confirm_adds_game_scoped_terms_for_enabled_platforms(self):
        async def scenario():
            clue_id = await seed_clue()
            async with Session() as session:
                result = await confirm_radar_clue(clue_id, db=session)
                configs = (
                    await session.execute(
                        select(PlatformSearchConfig)
                        .where(PlatformSearchConfig.source_key == "radar_confirmed")
                    )
                ).scalars().all()
                return result, configs

        result, configs = asyncio.run(scenario())
        self.assertEqual(result.status, "confirmed")
        self.assertEqual({cfg.platform for cfg in configs}, {"taptap", "douyin"})
        self.assertTrue(all(cfg.game_id == result.game_id for cfg in configs))
        self.assertTrue(all("星蚀核心" in cfg.keywords for cfg in configs))

    def test_dismiss_suppresses_for_thirty_days(self):
        async def scenario():
            clue_id = await seed_clue()
            async with Session() as session:
                before = datetime.now()
                result = await dismiss_radar_clue(clue_id, db=session)
                return result, before

        result, before = asyncio.run(scenario())
        self.assertEqual(result.status, "dismissed")
        suppressed = datetime.fromisoformat(result.suppressed_until)
        self.assertGreaterEqual(suppressed, before + timedelta(days=29, hours=23))

    def test_promote_is_idempotent_and_keeps_evidence(self):
        async def scenario():
            clue_id = await seed_clue()
            async with Session() as session:
                first = await promote_radar_clue(clue_id, db=session)
                second = await promote_radar_clue(clue_id, db=session)
                count = (await session.execute(select(func.count()).select_from(Demand))).scalar_one()
                demand = await session.get(Demand, first.demand_id)
                return first, second, count, demand

        first, second, count, demand = asyncio.run(scenario())
        self.assertEqual(first.demand_id, second.demand_id)
        self.assertEqual(count, 1)
        self.assertEqual(len(json.loads(demand.evidence_post_ids)), 1)

    def test_summary_and_list_expose_counts_coverage_and_evidence(self):
        async def scenario():
            await seed_clue()
            async with Session() as session:
                summary = await get_radar_summary(db=session)
                clues = await list_radar_clues(db=session)
                return summary, clues

        summary, clues = asyncio.run(scenario())
        self.assertEqual(summary.important_count, 1)
        self.assertEqual(summary.coverage.rule_completed, 1)
        self.assertEqual(summary.coverage.model_completed, 1)
        self.assertEqual(len(clues), 1)
        self.assertEqual(clues[0].evidence[0].url, "https://example.com/evidence")


if __name__ == "__main__":
    unittest.main()
