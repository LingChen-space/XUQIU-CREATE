"""早期需求雷达扫描服务测试。"""

import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.game import Game, GameGenre, GameStatus
from app.models.platform_content import ContentPlatform, ContentType, PlatformContent
from app.models.radar import (
    ContentScanState,
    RadarClue,
    RadarClueLevel,
    RadarClueStatus,
    RadarClueType,
)
from app.services.radar import RadarService
from app.services.radar_model import RadarModelReviewer


db_path = Path(tempfile.gettempdir()) / "req_gen_radar_service_test.db"
engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def reset_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed_content(title: str, body: str = "", game_name: str = "测试游戏") -> str:
    async with Session() as session:
        game = Game(
            name=game_name,
            genre=GameGenre.rpg,
            status=GameStatus.testing,
        )
        session.add(game)
        await session.flush()
        content = PlatformContent(
            game_id=game.id,
            platform=ContentPlatform.taptap,
            content_type=ContentType.post,
            source_id=f"source-{title}",
            title=title,
            body=body,
            published_at=datetime.now(),
        )
        session.add(content)
        await session.commit()
        return content.id


class RadarServiceTest(unittest.TestCase):
    def setUp(self):
        asyncio.run(reset_tables())

    def test_single_new_concept_creates_watch_clue(self):
        async def scenario():
            content_id = await seed_content("星蚀核心首次曝光")
            async with Session() as session:
                await RadarService(session).scan_content_rules(content_id)
                return (await session.execute(select(RadarClue))).scalar_one()

        clue = asyncio.run(scenario())
        self.assertEqual(clue.clue_type, RadarClueType.new_term)
        self.assertEqual(clue.level, RadarClueLevel.watch)
        self.assertIn("星蚀核心", clue.term)

    def test_experience_update_and_qualification_create_urgent_clues(self):
        async def scenario():
            content_id = await seed_content(
                "体验服核电站新地图更新",
                "资格招募已开启，6月26日10:00开放报名",
                game_name="三角洲行动体验服",
            )
            async with Session() as session:
                await RadarService(session).scan_content_rules(content_id)
                return (await session.execute(select(RadarClue))).scalars().all()

        clues = asyncio.run(scenario())
        clue_types = {clue.clue_type for clue in clues}
        self.assertIn(RadarClueType.experience_update, clue_types)
        self.assertIn(RadarClueType.qualification_change, clue_types)
        self.assertTrue(all(
            clue.level == RadarClueLevel.urgent
            for clue in clues
            if clue.clue_type in {
                RadarClueType.experience_update,
                RadarClueType.qualification_change,
            }
        ))

    def test_second_content_merges_same_concept_and_upgrades_to_important(self):
        async def scenario():
            first_id = await seed_content("星蚀核心首次曝光")
            async with Session() as session:
                first = await session.get(PlatformContent, first_id)
                game_id = first.game_id
                second = PlatformContent(
                    game_id=game_id,
                    platform=ContentPlatform.douyin,
                    content_type=ContentType.video,
                    source_id="second-source",
                    title="星蚀核心正式上线",
                    body="玩家讨论新机制",
                    published_at=datetime.now(),
                )
                session.add(second)
                await session.commit()

                service = RadarService(session)
                await service.scan_content_rules(first_id)
                await service.scan_content_rules(second.id)
                clues = (
                    await session.execute(
                        select(RadarClue).where(RadarClue.clue_type == RadarClueType.new_term)
                    )
                ).scalars().all()
                return clues

        clues = asyncio.run(scenario())
        self.assertEqual(len(clues), 1)
        self.assertEqual(clues[0].level, RadarClueLevel.important)
        self.assertIn("second-source", clues[0].summary)

    def test_model_finding_can_create_hidden_new_demand_without_tool_keyword(self):
        async def scenario():
            content_id = await seed_content(
                "每次换装备都要自己算半天",
                "希望输入现有装备后直接告诉我怎么搭配",
            )
            async with Session() as session:
                service = RadarService(session)
                await service.apply_model_findings(content_id, [{
                    "type": "new_demand",
                    "concept": "装备自动搭配",
                    "summary": "玩家希望根据现有装备自动生成搭配方案",
                    "demand_intent": 92,
                    "timeliness": 20,
                    "external_validation": 0,
                    "suggested_tool_type": "配装/战备工具",
                }])
                return (await session.execute(select(RadarClue))).scalar_one()

        clue = asyncio.run(scenario())
        self.assertEqual(clue.clue_type, RadarClueType.new_demand)
        self.assertEqual(clue.level, RadarClueLevel.important)
        self.assertEqual(clue.suggested_tool_type, "配装/战备工具")

    def test_model_reviewer_batches_pending_content_and_persists_multiple_findings(self):
        class FakeCompletions:
            async def create(self, **kwargs):
                content_id = kwargs["messages"][1]["content"].split("内容ID：", 1)[1].split("\n", 1)[0]
                payload = {
                    "findings": [
                        {
                            "content_id": content_id,
                            "type": "new_demand",
                            "concept": "装备自动搭配",
                            "summary": "希望系统自动生成搭配",
                            "demand_intent": 90,
                            "timeliness": 10,
                            "external_validation": 0,
                            "suggested_tool_type": "配装/战备工具",
                        },
                        {
                            "content_id": content_id,
                            "type": "new_term",
                            "concept": "星蚀核心",
                            "summary": "首次出现的新机制词",
                            "demand_intent": 20,
                            "timeliness": 20,
                            "external_validation": 0,
                        },
                    ]
                }
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=__import__("json").dumps(payload, ensure_ascii=False)))]
                )

        class FakeClient:
            chat = SimpleNamespace(completions=FakeCompletions())

        async def scenario():
            content_id = await seed_content("每次换装备都要自己算半天", "星蚀核心怎么搭配")
            async with Session() as session:
                session.add(ContentScanState(content_id=content_id))
                await session.commit()
                content = await session.get(PlatformContent, content_id)
                count = await RadarModelReviewer(session, client=FakeClient()).review_game(content.game_id)
                state = await session.get(ContentScanState, content_id)
                clues = (await session.execute(select(RadarClue))).scalars().all()
                return count, state.model_status, len(clues)

        self.assertEqual(asyncio.run(scenario()), (1, "completed", 2))

    def test_model_failure_schedules_one_five_fifteen_minute_retries(self):
        class FailingCompletions:
            async def create(self, **kwargs):
                raise RuntimeError("model unavailable")

        class FailingClient:
            chat = SimpleNamespace(completions=FailingCompletions())

        async def scenario():
            content_id = await seed_content("未知需求")
            async with Session() as session:
                session.add(ContentScanState(content_id=content_id))
                await session.commit()
                content = await session.get(PlatformContent, content_id)
                reviewer = RadarModelReviewer(session, client=FailingClient())
                delays = []
                for expected_attempt in (1, 2, 3):
                    before = datetime.now()
                    await reviewer.review_game(content.game_id, now=before)
                    state = await session.get(ContentScanState, content_id)
                    delays.append((
                        state.model_attempts,
                        None if state.next_retry_at is None else round((state.next_retry_at - before).total_seconds() / 60),
                        state.model_status,
                    ))
                    if state.next_retry_at:
                        state.next_retry_at = datetime.now() - timedelta(seconds=1)
                        await session.commit()
                return delays

        self.assertEqual(asyncio.run(scenario()), [
            (1, 1, "retry_wait"),
            (2, 5, "retry_wait"),
            (3, None, "failed"),
        ])

    def test_dismissed_clue_reopens_when_level_rises(self):
        async def scenario():
            content_id = await seed_content("装备搭配太复杂")
            async with Session() as session:
                service = RadarService(session)
                finding = {
                    "type": "new_demand",
                    "concept": "装备自动搭配",
                    "summary": "希望自动给出搭配方案",
                    "demand_intent": 70,
                }
                await service.apply_model_findings(content_id, [finding])
                clue = (await session.execute(select(RadarClue))).scalar_one()
                clue.status = RadarClueStatus.dismissed
                clue.suppressed_until = datetime.now() + timedelta(days=30)
                await session.commit()

                await service.apply_model_findings(content_id, [{
                    **finding,
                    "force_level": "urgent",
                    "timeliness": 100,
                }])
                await session.refresh(clue)
                return clue.status, clue.suppressed_until, clue.level

        self.assertEqual(
            asyncio.run(scenario()),
            (RadarClueStatus.pending, None, RadarClueLevel.urgent),
        )

    def test_dismissed_surge_reopens_when_velocity_rises_fifty_percent(self):
        async def scenario():
            content_id = await seed_content("热度快速增长")
            async with Session() as session:
                service = RadarService(session)
                base = {
                    "type": "engagement_surge",
                    "concept": "热度快速增长",
                    "summary": "互动正在增长",
                    "engagement_velocity": 60,
                    "engagement_detail": {"velocity": 100},
                }
                await service.apply_system_findings(content_id, [base])
                clue = (await session.execute(select(RadarClue))).scalar_one()
                clue.status = RadarClueStatus.dismissed
                clue.suppressed_until = datetime.now() + timedelta(days=30)
                await session.commit()

                await service.apply_system_findings(content_id, [{
                    **base,
                    "engagement_detail": {"velocity": 150},
                }])
                await session.refresh(clue)
                return clue.status, clue.suppressed_until

        self.assertEqual(asyncio.run(scenario()), (RadarClueStatus.pending, None))


if __name__ == "__main__":
    unittest.main()
