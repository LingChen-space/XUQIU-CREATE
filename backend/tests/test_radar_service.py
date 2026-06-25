"""雷达模型总结、重试与人工反馈边界测试。"""

import asyncio
import json
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


async def seed_content(title: str, game_name: str = "原神") -> str:
    async with Session() as session:
        game = Game(
            name=game_name,
            genre=GameGenre.rpg,
            status=GameStatus.operating,
            priority_weight=3,
        )
        session.add(game)
        await session.flush()
        content = PlatformContent(
            game_id=game.id,
            platform=ContentPlatform.taptap,
            content_type=ContentType.post,
            source_id=f"source-{title}",
            title=title,
            published_at=datetime.now(),
        )
        session.add(content)
        await session.commit()
        return content.id


class RadarServiceTest(unittest.TestCase):
    def setUp(self):
        asyncio.run(reset_tables())

    def test_nonstandard_concept_does_not_create_clue(self):
        async def scenario():
            content_id = await seed_content("星蚀核心首次曝光")
            async with Session() as session:
                return await RadarService(session).scan_content_rules(content_id)

        self.assertEqual(asyncio.run(scenario()), [])

    def test_model_only_updates_existing_standard_term(self):
        async def scenario():
            content_id = await seed_content("圣遗物打分工具求推荐")
            async with Session() as session:
                service = RadarService(session)
                await service.scan_content_rules(content_id)
                updated = await service.apply_model_findings(content_id, [
                    {
                        "concept": "圣遗物评分器",
                        "summary": "玩家希望快速判断圣遗物价值",
                        "suggested_tool_type": "机制计算器",
                    },
                    {
                        "concept": "模型自由方向",
                        "summary": "不得创建",
                    },
                ])
                clues = (await session.execute(select(RadarClue))).scalars().all()
                return updated, clues

        updated, clues = asyncio.run(scenario())
        self.assertEqual(len(updated), 1)
        self.assertEqual(len(clues), 1)
        self.assertEqual(clues[0].term, "圣遗物评分器")
        self.assertEqual(clues[0].summary, "玩家希望快速判断圣遗物价值")

    def test_model_reviewer_summarizes_multiple_standard_terms(self):
        class FakeCompletions:
            async def create(self, **kwargs):
                content_id = kwargs["messages"][1]["content"].split("内容ID：", 1)[1].split("\n", 1)[0]
                payload = {
                    "findings": [
                        {
                            "content_id": content_id,
                            "concept": "圣遗物评分器",
                            "summary": "总结圣遗物评分需求",
                        },
                        {
                            "content_id": content_id,
                            "concept": "体力规划器",
                            "summary": "总结体力规划需求",
                        },
                    ]
                }
                return SimpleNamespace(
                    choices=[SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps(payload, ensure_ascii=False)
                        )
                    )]
                )

        class FakeClient:
            chat = SimpleNamespace(completions=FakeCompletions())

        async def scenario():
            content_id = await seed_content("圣遗物打分和体力规划器都需要")
            async with Session() as session:
                service = RadarService(session)
                await service.scan_content_rules(content_id)
                content = await session.get(PlatformContent, content_id)
                count = await RadarModelReviewer(
                    session,
                    client=FakeClient(),
                ).review_game(content.game_id)
                clues = (await session.execute(select(RadarClue))).scalars().all()
                state = await session.get(ContentScanState, content_id)
                return count, state.model_status, {clue.term: clue.summary for clue in clues}

        count, status, summaries = asyncio.run(scenario())
        self.assertEqual(count, 1)
        self.assertEqual(status, "completed")
        self.assertEqual(
            summaries,
            {
                "圣遗物评分器": "总结圣遗物评分需求",
                "体力规划器": "总结体力规划需求",
            },
        )

    def test_model_failure_schedules_one_five_fifteen_minute_retries(self):
        class FailingCompletions:
            async def create(self, **kwargs):
                raise RuntimeError("model unavailable")

        class FailingClient:
            chat = SimpleNamespace(completions=FailingCompletions())

        async def scenario():
            content_id = await seed_content("圣遗物评分器")
            async with Session() as session:
                await RadarService(session).scan_content_rules(content_id)
                content = await session.get(PlatformContent, content_id)
                reviewer = RadarModelReviewer(session, client=FailingClient())
                delays = []
                for _ in (1, 2, 3):
                    before = datetime.now()
                    await reviewer.review_game(content.game_id, now=before)
                    state = await session.get(ContentScanState, content_id)
                    delays.append((
                        state.model_attempts,
                        None if state.next_retry_at is None else round(
                            (state.next_retry_at - before).total_seconds() / 60
                        ),
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

    def test_dismissed_level_two_reopens_on_second_independent_evidence(self):
        async def scenario():
            first_id = await seed_content("平民配队分享")
            async with Session() as session:
                first = await session.get(PlatformContent, first_id)
                second = PlatformContent(
                    game_id=first.game_id,
                    platform=ContentPlatform.douyin,
                    content_type=ContentType.video,
                    source_id="second-source",
                    title="零氪配队推荐",
                    published_at=datetime.now(),
                )
                session.add(second)
                await session.commit()
                service = RadarService(session)
                await service.scan_content_rules(first_id)
                clue = (await session.execute(select(RadarClue))).scalar_one()
                clue.status = RadarClueStatus.dismissed
                clue.suppressed_until = datetime.now() + timedelta(days=30)
                await session.commit()
                await service.scan_content_rules(second.id)
                await session.refresh(clue)
                return clue.status, clue.suppressed_until, clue.level

        self.assertEqual(
            asyncio.run(scenario()),
            (RadarClueStatus.pending, None, RadarClueLevel.important),
        )


if __name__ == "__main__":
    unittest.main()
