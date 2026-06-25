"""雷达大模型批量语义审阅。"""

import json
import re
from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.platform_content import PlatformContent
from app.models.radar import ContentScanState
from app.services.llm_client import build_async_client
from app.services.radar import RadarService


RETRY_DELAYS_MINUTES = (1, 5, 15)

RADAR_REVIEW_PROMPT = """你是好游快爆早期需求雷达分析师。
请审阅以下同一游戏的新内容，找出所有新的用户需求、工具机会、游戏新词/新机制、
体验服更新/爆料/资格变化、用户自制或外部解决方案。

不要因为只出现一次而丢弃；不要要求内容必须出现“工具”字样。
只输出 JSON：
{{"findings":[{{"content_id":"...","type":"new_term|new_demand|experience_update|experience_leak|qualification_change|external_solution","concept":"2-30字","summary":"判断依据","demand_intent":0-100,"timeliness":0-100,"external_validation":0-100,"suggested_tool_type":"可为空"}}]}}

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

        states = [row[0] for row in rows]
        contents = [row[1] for row in rows]
        prompt_contents = "\n\n".join(
            f"内容ID：{content.id}\n标题：{content.title}\n正文：{content.body[:1000]}\n"
            f"互动：浏览{content.view_count} 点赞{content.like_count} 评论{content.comment_count} 分享{content.share_count}"
            for content in contents
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

            for state, content in rows:
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
