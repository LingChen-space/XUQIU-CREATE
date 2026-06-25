"""标准需求词驱动的雷达分级测试。"""

import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.game import Game, GameGenre, GameStatus
from app.models.platform_content import ContentPlatform, ContentType, PlatformContent
from app.models.radar import RadarClue, RadarClueLevel, RadarClueType
from app.services.radar import RadarService


db_path = Path(tempfile.gettempdir()) / "req_gen_keyword_radar_test.db"
engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def reset_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed_game(name: str = "原神") -> str:
    async with Session() as session:
        game = Game(
            name=name,
            genre=GameGenre.rpg,
            status=GameStatus.operating,
            priority_weight=3,
        )
        session.add(game)
        await session.commit()
        return game.id


async def add_content(
    game_id: str,
    title: str,
    *,
    source_id: str,
    published_at: datetime | None = None,
) -> str:
    async with Session() as session:
        content = PlatformContent(
            game_id=game_id,
            platform=ContentPlatform.taptap,
            content_type=ContentType.post,
            source_id=source_id,
            url=f"https://example.com/{source_id}",
            title=title,
            body="",
            published_at=published_at or datetime.now(),
        )
        session.add(content)
        await session.commit()
        return content.id


class KeywordRadarTest(unittest.TestCase):
    def setUp(self):
        asyncio.run(reset_tables())

    def test_level_one_first_hit_creates_important_clue(self):
        async def scenario():
            game_id = await seed_game()
            content_id = await add_content(
                game_id,
                "求一个圣遗物打分工具",
                source_id="level-one",
            )
            async with Session() as session:
                clues = await RadarService(session).scan_content_rules(content_id)
                return clues[0]

        clue = asyncio.run(scenario())
        details = json.loads(clue.score_detail)
        self.assertEqual(clue.term, "圣遗物评分器")
        self.assertEqual(clue.clue_type, RadarClueType.new_demand)
        self.assertEqual(clue.level, RadarClueLevel.important)
        self.assertEqual(details["keyword_priority"], "level_1")
        self.assertEqual(details["matched_alias"], "圣遗物打分")

    def test_level_two_second_independent_content_upgrades_to_important(self):
        async def scenario():
            game_id = await seed_game()
            first_id = await add_content(game_id, "原神平民配队分享", source_id="level-two-1")
            second_id = await add_content(game_id, "零氪配队怎么选", source_id="level-two-2")
            async with Session() as session:
                service = RadarService(session)
                await service.scan_content_rules(first_id)
                first = (await session.execute(select(RadarClue))).scalar_one()
                first_level = first.level
                await service.scan_content_rules(second_id)
                await session.refresh(first)
                return first_level, first.level, json.loads(first.score_detail)

        first_level, second_level, details = asyncio.run(scenario())
        self.assertEqual(first_level, RadarClueLevel.watch)
        self.assertEqual(second_level, RadarClueLevel.important)
        self.assertEqual(details["independent_evidence_count"], 2)

    def test_rescanning_same_content_does_not_upgrade_level_two(self):
        async def scenario():
            game_id = await seed_game()
            content_id = await add_content(game_id, "平民配队方案", source_id="same-content")
            async with Session() as session:
                service = RadarService(session)
                await service.scan_content_rules(content_id)
                await service.scan_content_rules(content_id)
                clue = (await session.execute(select(RadarClue))).scalar_one()
                return clue.level, json.loads(clue.score_detail)

        level, details = asyncio.run(scenario())
        self.assertEqual(level, RadarClueLevel.watch)
        self.assertEqual(details["independent_evidence_count"], 1)

    def test_recent_level_three_is_important_and_explicit_node_is_urgent(self):
        async def scenario():
            game_id = await seed_game()
            important_id = await add_content(
                game_id,
                "原神版本更新内容汇总",
                source_id="hot-important",
            )
            urgent_id = await add_content(
                game_id,
                "5.8版本更新内容：角色削弱，6月28日上线",
                source_id="hot-urgent",
            )
            async with Session() as session:
                service = RadarService(session)
                important = await service.scan_content_rules(important_id)
                important_levels = {
                    clue.term: clue.level
                    for clue in important
                }
                urgent = await service.scan_content_rules(urgent_id)
                return important_levels, urgent

        important_levels, urgent = asyncio.run(scenario())
        by_term_urgent = {clue.term: clue for clue in urgent}
        self.assertEqual(
            important_levels["版本更新内容"],
            RadarClueLevel.important,
        )
        self.assertEqual(
            by_term_urgent["版本更新内容"].level,
            RadarClueLevel.urgent,
        )
        self.assertEqual(
            by_term_urgent["角色削弱"].level,
            RadarClueLevel.urgent,
        )

    def test_old_level_three_content_does_not_create_clue(self):
        async def scenario():
            game_id = await seed_game()
            content_id = await add_content(
                game_id,
                "旧版本更新内容与BUG修复记录",
                source_id="old-hot",
                published_at=datetime.now() - timedelta(days=8),
            )
            async with Session() as session:
                return await RadarService(session).scan_content_rules(content_id)

        self.assertEqual(asyncio.run(scenario()), [])

    def test_one_content_can_create_multiple_standard_demand_clues(self):
        async def scenario():
            game_id = await seed_game()
            content_id = await add_content(
                game_id,
                "圣遗物打分、体力规划器和神瞳位置都想查",
                source_id="multi",
            )
            async with Session() as session:
                clues = await RadarService(session).scan_content_rules(content_id)
                return {clue.term for clue in clues}

        self.assertEqual(
            asyncio.run(scenario()),
            {"圣遗物评分器", "体力规划器", "神瞳位置"},
        )

    def test_model_cannot_create_nonstandard_demand(self):
        async def scenario():
            game_id = await seed_game()
            content_id = await add_content(
                game_id,
                "我想要一个完全自创方向",
                source_id="model-free",
            )
            async with Session() as session:
                return await RadarService(session).apply_model_findings(content_id, [{
                    "type": "new_demand",
                    "concept": "模型自由发明需求",
                    "summary": "不在标准词库中",
                    "demand_intent": 100,
                }])

        self.assertEqual(asyncio.run(scenario()), [])

    def test_other_game_specific_term_does_not_cross_match(self):
        async def scenario():
            game_id = await seed_game("鸣潮")
            content_id = await add_content(
                game_id,
                "想找原神圣遗物评分器",
                source_id="cross-game",
            )
            async with Session() as session:
                return await RadarService(session).scan_content_rules(content_id)

        self.assertEqual(asyncio.run(scenario()), [])


if __name__ == "__main__":
    unittest.main()
