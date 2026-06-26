"""早期需求雷达：规则扫描、概念索引与线索合并。"""

import hashlib
import json
import re
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game
from app.models.platform_content import PlatformContent
from app.models.radar import (
    ContentConcept,
    ContentScanState,
    RadarClue,
    RadarClueLevel,
    RadarClueStatus,
    RadarClueType,
)
from app.services.demand_keyword_rules import (
    DemandKeywordMatch,
    canonical_game_name,
    is_experience_server,
    match_demand_keywords,
)


HOT_NODE_PATTERN = re.compile(
    r"(?:v?\d+(?:\.\d+)+|版本\s*\d+|\d{1,2}月\d{1,2}日|"
    r"\d{1,2}[:：]\d{2}|上线|下线|开启|结束|加强|削弱|bug|修复)",
    re.IGNORECASE,
)


def normalize_concept(value: str) -> str:
    return re.sub(r"[\s\W_]+", "", (value or "").lower(), flags=re.UNICODE)


def clue_signature(game_id: str, clue_type: RadarClueType, concept: str) -> str:
    normalized = normalize_concept(concept)
    raw = f"{game_id}:{clue_type.value}:{normalized}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return f"{game_id}:{clue_type.value}:{digest}"


class RadarService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def scan_content_rules(self, content_id: str) -> list[RadarClue]:
        content = await self.session.get(PlatformContent, content_id)
        if content is None:
            return []

        state = await self._ensure_scan_state(content.id)
        game = await self.session.get(Game, content.game_id)
        text = self._content_text(content)
        clues: list[RadarClue] = []
        if game is not None:
            for match in match_demand_keywords(game.name, text):
                clue = await self._apply_keyword_match(content, game, match, text)
                if clue is not None:
                    clues.append(clue)
        state.rule_status = "completed"
        state.rule_scanned_at = datetime.now()
        # 体验服无标准词命中时保持 model_status=pending，交模型审阅阶段做版本/爆料提取
        if not clues and not is_experience_server(game.name if game else ""):
            state.model_status = "completed"
            state.model_scanned_at = datetime.now()
        await self.session.commit()
        return clues

    async def apply_model_findings(self, content_id: str, findings: list[dict]) -> list[RadarClue]:
        content = await self.session.get(PlatformContent, content_id)
        if content is None:
            return []
        state = await self._ensure_scan_state(content.id)
        clues: list[RadarClue] = []
        for finding in findings:
            concept = str(finding.get("concept") or "").strip()
            if not concept:
                continue
            signature = clue_signature(
                content.game_id,
                RadarClueType.new_demand,
                concept,
            )
            clue = (
                await self.session.execute(
                    select(RadarClue).where(RadarClue.signature == signature)
                )
            ).scalar()
            if clue is None or content.id not in self._json_list(clue.evidence_content_ids):
                continue
            summary = str(finding.get("summary") or "").strip()
            if summary:
                clue.summary = summary[:1000]
            if finding.get("suggested_tool_type"):
                clue.suggested_tool_type = str(finding["suggested_tool_type"])
            clues.append(clue)
        state.model_status = "completed"
        state.model_scanned_at = datetime.now()
        state.last_error = ""
        await self.session.commit()
        return clues

    async def apply_system_findings(self, content_id: str, findings: list[dict]) -> list[RadarClue]:
        """写入非模型产生的线索，如互动突增。"""
        content = await self.session.get(PlatformContent, content_id)
        if content is None:
            return []
        existing = (
            await self.session.execute(
                select(RadarClue).where(
                    RadarClue.game_id == content.game_id,
                    RadarClue.clue_type == RadarClueType.new_demand,
                )
            )
        ).scalars().all()
        clues = [
            clue
            for clue in existing
            if content.id in self._json_list(clue.evidence_content_ids)
        ]
        if not clues:
            return []
        engagement_finding = next(
            (
                finding for finding in findings
                if finding.get("type") == RadarClueType.engagement_surge.value
            ),
            None,
        )
        if engagement_finding:
            boost = min(
                10.0,
                float(engagement_finding.get("engagement_velocity") or 0) / 10,
            )
            for clue in clues:
                clue.total_score = min(100.0, float(clue.total_score or 0) + boost)
                clue.engagement_detail = json.dumps(
                    engagement_finding.get("engagement_detail") or {},
                    ensure_ascii=False,
                )
                if engagement_finding.get("force_level") == RadarClueLevel.urgent.value:
                    clue.level = RadarClueLevel.urgent
                elif engagement_finding.get("force_level") == RadarClueLevel.important.value:
                    clue.level = self._max_level(clue.level, RadarClueLevel.important)
                elif clue.total_score >= 80:
                    clue.level = RadarClueLevel.urgent
        await self.session.commit()
        return clues

    async def apply_experience_findings(
        self,
        content_id: str,
        findings: list[dict],
    ) -> list[RadarClue]:
        """体验服版本/爆料提取结果写入：用提取的 term 创建/合并 new_demand 线索。"""
        content = await self.session.get(PlatformContent, content_id)
        if content is None:
            return []
        await self._ensure_scan_state(content.id)
        text = self._content_text(content)
        has_hot_node = bool(HOT_NODE_PATTERN.search(text))
        clues: list[RadarClue] = []
        for finding in findings:
            term = str(finding.get("term") or "").strip()
            if not term:
                continue
            signature = clue_signature(content.game_id, RadarClueType.new_demand, term)
            clue = (
                await self.session.execute(
                    select(RadarClue).where(RadarClue.signature == signature)
                )
            ).scalar()
            evidence_ids = self._json_list(clue.evidence_content_ids) if clue else []
            if content.id not in evidence_ids:
                evidence_ids.append(content.id)
            evidence_count = len(evidence_ids)
            level = RadarClueLevel.urgent if has_hot_node else RadarClueLevel.important
            total_score = float(
                min(100, (82 if has_hot_node else 66) + min(8, max(0, evidence_count - 1) * 3))
            )
            score_detail = {
                "source": "experience_server_llm",
                "independent_evidence_count": evidence_count,
                "hot_node": has_hot_node,
            }
            reason = f"体验服版本/爆料提取：{term}，独立证据 {evidence_count} 条"
            summary = str(finding.get("summary") or content.title or reason)[:1000]
            if clue is None:
                clue = RadarClue(
                    signature=signature,
                    game_id=content.game_id,
                    clue_type=RadarClueType.new_demand,
                    level=level,
                    title=f"版本/爆料：{term}",
                    summary=summary,
                    term=term,
                    trigger_reason=reason,
                    evidence_content_ids=json.dumps(evidence_ids, ensure_ascii=False),
                    score_detail=json.dumps(score_detail, ensure_ascii=False),
                    engagement_detail="{}",
                    suggested_tool_type="版本更新追踪",
                    total_score=total_score,
                )
                self.session.add(clue)
            else:
                previous_level = clue.level
                clue.evidence_content_ids = json.dumps(evidence_ids, ensure_ascii=False)
                clue.level = self._max_level(clue.level, level)
                clue.total_score = max(float(clue.total_score or 0), total_score)
                clue.score_detail = json.dumps(score_detail, ensure_ascii=False)
                clue.trigger_reason = reason
                clue.last_seen_at = datetime.now()
                if summary:
                    clue.summary = summary
                if (
                    clue.status == RadarClueStatus.dismissed
                    and self._max_level(previous_level, level) != previous_level
                ):
                    clue.status = RadarClueStatus.pending
                    clue.suppressed_until = None
            clues.append(clue)
        await self.session.flush()
        return clues

    async def standard_terms_for_content(self, content_id: str) -> list[str]:
        content = await self.session.get(PlatformContent, content_id)
        if content is None:
            return []
        clues = (
            await self.session.execute(
                select(RadarClue).where(
                    RadarClue.game_id == content.game_id,
                    RadarClue.clue_type == RadarClueType.new_demand,
                )
            )
        ).scalars().all()
        return [
            clue.term
            for clue in clues
            if content.id in self._json_list(clue.evidence_content_ids)
        ]

    async def _apply_keyword_match(
        self,
        content: PlatformContent,
        game: Game,
        match: DemandKeywordMatch,
        text: str,
    ) -> RadarClue | None:
        rule = match.rule
        if (
            rule.priority == "level_3"
            and content.published_at < datetime.now() - timedelta(days=7)
        ):
            return None

        signature = clue_signature(
            content.game_id,
            RadarClueType.new_demand,
            rule.canonical_term,
        )
        clue = (
            await self.session.execute(
                select(RadarClue).where(RadarClue.signature == signature)
            )
        ).scalar()
        evidence_ids = self._json_list(clue.evidence_content_ids) if clue else []
        if content.id not in evidence_ids:
            evidence_ids.append(content.id)
        evidence_count = len(evidence_ids)
        has_hot_node = bool(HOT_NODE_PATTERN.search(text))
        level, total_score = self._keyword_level_and_score(
            priority=rule.priority,
            evidence_count=evidence_count,
            priority_game=canonical_game_name(game.name) is not None,
            has_hot_node=has_hot_node,
        )
        score_detail = {
            "keyword_priority": rule.priority,
            "keyword_category": rule.category,
            "matched_alias": match.matched_alias,
            "canonical_term": rule.canonical_term,
            "independent_evidence_count": evidence_count,
            "priority_game": canonical_game_name(game.name) is not None,
            "hot_node": has_hot_node,
        }
        reason = (
            f"{self._priority_label(rule.priority)}命中「{match.matched_alias}」"
            f"，归一为「{rule.canonical_term}」，独立证据 {evidence_count} 条"
        )

        concept_row = (
            await self.session.execute(
                select(ContentConcept).where(
                    ContentConcept.game_id == content.game_id,
                    ContentConcept.concept_type == "standard_keyword",
                    ContentConcept.normalized_value == normalize_concept(rule.canonical_term),
                )
            )
        ).scalar()
        if concept_row is None:
            self.session.add(ContentConcept(
                game_id=content.game_id,
                content_id=content.id,
                concept_type="standard_keyword",
                value=rule.canonical_term,
                normalized_value=normalize_concept(rule.canonical_term),
                occurrence_count=evidence_count,
            ))
        else:
            concept_row.last_seen_at = datetime.now()
            concept_row.occurrence_count = evidence_count

        if clue is None:
            clue = RadarClue(
                signature=signature,
                game_id=content.game_id,
                clue_type=RadarClueType.new_demand,
                level=level,
                title=f"标准需求：{rule.canonical_term}",
                summary=(content.title or content.body or reason)[:1000],
                term=rule.canonical_term,
                trigger_reason=reason,
                evidence_content_ids=json.dumps(evidence_ids, ensure_ascii=False),
                score_detail=json.dumps(score_detail, ensure_ascii=False),
                engagement_detail="{}",
                suggested_tool_type=rule.suggested_tool_type,
                total_score=total_score,
            )
            self.session.add(clue)
        else:
            previous_level = clue.level
            clue.evidence_content_ids = json.dumps(evidence_ids, ensure_ascii=False)
            clue.level = self._max_level(clue.level, level)
            clue.total_score = max(float(clue.total_score or 0), total_score)
            clue.score_detail = json.dumps(score_detail, ensure_ascii=False)
            clue.trigger_reason = reason
            clue.last_seen_at = datetime.now()
            if (
                clue.status == RadarClueStatus.dismissed
                and self._max_level(previous_level, level) != previous_level
            ):
                clue.status = RadarClueStatus.pending
                clue.suppressed_until = None
        await self.session.flush()
        return clue

    @staticmethod
    def _keyword_level_and_score(
        *,
        priority: str,
        evidence_count: int,
        priority_game: bool,
        has_hot_node: bool,
    ) -> tuple[RadarClueLevel, float]:
        if priority == "level_1":
            level = RadarClueLevel.important
            base = 70
        elif priority == "level_2":
            level = (
                RadarClueLevel.important
                if evidence_count >= 2
                else RadarClueLevel.watch
            )
            base = 60 if evidence_count >= 2 else 40
        else:
            level = RadarClueLevel.urgent if has_hot_node else RadarClueLevel.important
            base = 85 if has_hot_node else 65
        source_bonus = 8 if evidence_count >= 2 else 0
        source_bonus += min(7, max(0, evidence_count - 2) * 3)
        return level, float(min(100, base + source_bonus + (5 if priority_game else 0)))

    @staticmethod
    def _priority_label(priority: str) -> str:
        return {
            "level_1": "一级核心词",
            "level_2": "二级长尾词",
            "level_3": "三级热点词",
        }[priority]

    @staticmethod
    def _content_text(content: PlatformContent) -> str:
        sections = [content.title or "", content.body or ""]
        try:
            extra = json.loads(content.extra_data or "{}")
        except (TypeError, ValueError):
            extra = {}
        comments = extra.get("high_liked_comments") or extra.get("comments") or []
        if isinstance(comments, list):
            sections.extend(
                str(item.get("content") if isinstance(item, dict) else item)
                for item in comments[:20]
            )
        return " ".join(section for section in sections if section).strip()

    async def _ensure_scan_state(self, content_id: str) -> ContentScanState:
        state = await self.session.get(ContentScanState, content_id)
        if state is None:
            state = ContentScanState(content_id=content_id)
            self.session.add(state)
            await self.session.flush()
        return state

    @staticmethod
    def _max_level(current: RadarClueLevel, candidate: RadarClueLevel) -> RadarClueLevel:
        rank = {
            RadarClueLevel.watch: 1,
            RadarClueLevel.important: 2,
            RadarClueLevel.urgent: 3,
        }
        return current if rank[current] >= rank[candidate] else candidate

    @staticmethod
    def _json_list(value: str) -> list[str]:
        try:
            data = json.loads(value or "[]")
        except (TypeError, ValueError):
            return []
        return [str(item) for item in data] if isinstance(data, list) else []

