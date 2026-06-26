"""雷达大模型批量语义审阅。"""

import json
import re
from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.game import Game
from app.models.platform_content import PlatformContent
from app.models.radar import ContentScanState
from app.services.demand_keyword_rules import is_experience_server
from app.services.experience_server_extractor import ExperienceServerExtractor
from app.services.llm_client import build_async_client
from app.services.radar import RadarService


RETRY_DELAYS_MINUTES = (1, 5, 15)

RADAR_REVIEW_PROMPT = """你是好游快爆需求雷达总结助手。
每条内容已经由确定性词库命中一个或多个“标准需求词”。
你只能总结这些标准需求词对应的具体玩家问题，不能新增、改名或扩展需求方向。

只输出 JSON：
{{"findings":[{{"content_id":"...","concept":"必须原样使用给出的标准需求词","summary":"玩家具体问题摘要","suggested_tool_type":"可为空"}}]}}

内容：
{contents}
"""


class RadarModelReviewer:
    def __init__(self, session: AsyncSession, client=None):
        self.session = session
        self.client = client if client is not None else build_async_client()
        self.radar = RadarService(session)

    async def review_game(self, game_id: str, now: datetime | None = None) -> int:
        current_time = now or datetime.now()
        stmt = (
            select(ContentScanState, PlatformContent)
            .join(PlatformContent, PlatformContent.id == ContentScanState.content_id)
            .where(
                PlatformContent.game_id == game_id,
                or_(
                    ContentScanState.model_status == "pending",
                    and_(
                        ContentScanState.model_status == "retry_wait",
                        ContentScanState.next_retry_at <= current_time,
                    ),
                ),
            )
            .order_by(PlatformContent.collected_at)
            .limit(20)
        )
        rows = (await self.session.execute(stmt)).all()
        if not rows:
            return 0

        game = await self.session.get(Game, game_id)
        if game is not None and is_experience_server(game.name):
            return await self._review_experience_server(rows, current_time)

        review_rows = []
        for state, content in rows:
            terms = await self.radar.standard_terms_for_content(content.id)
            if not terms:
                state.model_status = "completed"
                state.model_scanned_at = current_time
                continue
            review_rows.append((state, content, terms))
        if not review_rows:
            await self.session.commit()
            return 0

        states = [row[0] for row in review_rows]
        contents = [row[1] for row in review_rows]
        prompt_contents = "\n\n".join(
            f"内容ID：{content.id}\n标题：{content.title}\n正文：{content.body[:1000]}\n"
            f"标准需求词：{'、'.join(terms)}\n"
            f"互动：浏览{content.view_count} 点赞{content.like_count} 评论{content.comment_count} 分享{content.share_count}"
            for _, content, terms in review_rows
        )

        try:
            response = await self.client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": "只输出合法JSON，不要解释。"},
                    {"role": "user", "content": RADAR_REVIEW_PROMPT.format(contents=prompt_contents)},
                ],
                temperature=0.2,
                max_tokens=2500,
            )
            raw = response.choices[0].message.content or ""
            findings = self._parse_findings(raw)
            findings_by_content: dict[str, list[dict]] = {}
            for finding in findings:
                content_id = str(finding.get("content_id") or "")
                findings_by_content.setdefault(content_id, []).append(finding)

            for state, content, _ in review_rows:
                await self.radar.apply_model_findings(
                    content.id,
                    findings_by_content.get(content.id, []),
                )
                state.model_status = "completed"
                state.model_scanned_at = current_time
                state.next_retry_at = None
                state.last_error = ""
            await self.session.commit()
            return len(contents)
        except Exception as exc:
            for state in states:
                state.model_attempts = int(state.model_attempts or 0) + 1
                state.last_error = str(exc)[:1000]
                if state.model_attempts >= 3:
                    state.model_status = "failed"
                    state.next_retry_at = None
                else:
                    state.model_status = "retry_wait"
                    state.next_retry_at = current_time + timedelta(
                        minutes=RETRY_DELAYS_MINUTES[state.model_attempts - 1]
                    )
            await self.session.commit()
            return 0

    async def _review_experience_server(
        self,
        rows: list,
        current_time: datetime,
    ) -> int:
        """体验服游戏：用 LLM 批量提取版本/爆料需求词并写入线索。"""
        states = [state for state, _ in rows]
        contents = [content for _, content in rows]
        try:
            extractor = ExperienceServerExtractor(self.client)
            findings_by_content = await extractor.extract_batch(contents)
        except Exception as exc:
            for state in states:
                state.model_attempts = int(state.model_attempts or 0) + 1
                state.last_error = str(exc)[:1000]
                if state.model_attempts >= 3:
                    state.model_status = "failed"
                    state.next_retry_at = None
                else:
                    state.model_status = "retry_wait"
                    state.next_retry_at = current_time + timedelta(
                        minutes=RETRY_DELAYS_MINUTES[state.model_attempts - 1]
                    )
            await self.session.commit()
            return 0

        for state, content in rows:
            await self.radar.apply_experience_findings(
                content.id,
                findings_by_content.get(content.id, []),
            )
            state.model_status = "completed"
            state.model_scanned_at = current_time
            state.next_retry_at = None
            state.last_error = ""
        await self.session.commit()
        return len(contents)

    @staticmethod
    def _parse_findings(raw: str) -> list[dict]:
        block = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
        if block:
            raw = block.group(1)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("模型未返回JSON对象")
        data = json.loads(match.group())
        findings = data.get("findings", [])
        if not isinstance(findings, list):
            raise ValueError("findings必须为数组")
        return [item for item in findings if isinstance(item, dict)]
