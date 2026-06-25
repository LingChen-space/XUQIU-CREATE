"""早期需求雷达：规则扫描、概念索引与线索合并。"""

import hashlib
import json
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_content import PlatformContent
from app.models.radar import (
    ContentConcept,
    ContentScanState,
    RadarClue,
    RadarClueLevel,
    RadarClueStatus,
    RadarClueType,
)


EXPERIENCE_UPDATE_WORDS = (
    "更新", "版本", "改动", "调整", "补丁", "新增", "新地图", "新角色",
    "新英雄", "新武器", "新玩法", "优化", "修复",
)
EXPERIENCE_LEAK_WORDS = ("爆料", "曝光", "情报", "前瞻", "偷跑", "泄露")
QUALIFICATION_WORDS = (
    "资格", "招募", "报名", "申请", "抢码", "激活码", "邀请码", "名额",
    "开放报名", "资格发放",
)
EXTERNAL_SOLUTION_WORDS = (
    "做了个", "写了个", "自制", "表格", "在线文档", "小程序", "网页版",
    "计算器", "模拟器", "github.com", "docs.qq.com", "kdocs.cn", "feishu.cn",
)

CONCEPT_PATTERNS = (
    re.compile(r"[「『“《]([^」』”》]{2,24})[」』”》]"),
    re.compile(
        r"([\u4e00-\u9fffA-Za-z0-9·：:_-]{2,18}?)"
        r"(?:首次曝光|正式上线|即将上线|首次登场|正式登场|曝光|上线|登场)"
    ),
)
CONCEPT_STOP_WORDS = {
    "体验服", "测试服", "首次", "正式", "全新", "内容", "工具", "攻略",
    "更新", "爆料", "资格", "报名", "申请",
}


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
        text = f"{content.title or ''} {content.body or ''}".strip()
        findings: list[dict] = []

        for concept in self._extract_concepts(content):
            findings.append({
                "type": RadarClueType.new_term.value,
                "concept": concept,
                "summary": f"该概念首次与当前游戏结合出现：[来源:{content.source_id or content.id}]",
                "novelty": 100,
                "demand_intent": 0,
                "timeliness": 0,
                "external_validation": 0,
            })

        if any(word in text for word in EXPERIENCE_UPDATE_WORDS) and self._has_experience_context(text):
            findings.append({
                "type": RadarClueType.experience_update.value,
                "concept": content.title or "体验服更新",
                "summary": text[:240],
                "novelty": 100,
                "demand_intent": 60,
                "timeliness": 100,
                "external_validation": 0,
                "force_level": RadarClueLevel.urgent.value,
            })
        if any(word in text for word in EXPERIENCE_LEAK_WORDS) and self._has_experience_context(text):
            findings.append({
                "type": RadarClueType.experience_leak.value,
                "concept": content.title or "体验服爆料",
                "summary": text[:240],
                "novelty": 100,
                "demand_intent": 50,
                "timeliness": 100,
                "external_validation": 0,
                "force_level": RadarClueLevel.urgent.value,
            })
        if any(word in text for word in QUALIFICATION_WORDS) and self._has_experience_context(text):
            findings.append({
                "type": RadarClueType.qualification_change.value,
                "concept": content.title or "体验服资格变化",
                "summary": text[:240],
                "novelty": 100,
                "demand_intent": 90,
                "timeliness": 100,
                "external_validation": 0,
                "force_level": RadarClueLevel.urgent.value,
            })
        if any(word.lower() in text.lower() for word in EXTERNAL_SOLUTION_WORDS):
            findings.append({
                "type": RadarClueType.external_solution.value,
                "concept": content.title or "外部解决方案",
                "summary": text[:240],
                "novelty": 80,
                "demand_intent": 80,
                "timeliness": 30,
                "external_validation": 100,
            })

        clues = await self._apply_findings(content, findings)
        state.rule_status = "completed"
        state.rule_scanned_at = datetime.now()
        await self.session.commit()
        return clues

    async def apply_model_findings(self, content_id: str, findings: list[dict]) -> list[RadarClue]:
        content = await self.session.get(PlatformContent, content_id)
        if content is None:
            return []
        state = await self._ensure_scan_state(content.id)
        clues = await self._apply_findings(content, findings)
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
        clues = await self._apply_findings(content, findings)
        await self.session.commit()
        return clues

    async def _apply_findings(self, content: PlatformContent, findings: list[dict]) -> list[RadarClue]:
        clues: list[RadarClue] = []
        for finding in findings:
            try:
                clue_type = RadarClueType(finding.get("type", RadarClueType.new_term.value))
            except ValueError:
                clue_type = RadarClueType.new_term
            concept = str(finding.get("concept") or content.title or "").strip()
            normalized = normalize_concept(concept)
            if len(normalized) < 2:
                continue

            concept_row = (
                await self.session.execute(
                    select(ContentConcept).where(
                        ContentConcept.game_id == content.game_id,
                        ContentConcept.concept_type == clue_type.value,
                        ContentConcept.normalized_value == normalized,
                    )
                )
            ).scalar()
            is_new = concept_row is None
            if concept_row is None:
                concept_row = ContentConcept(
                    game_id=content.game_id,
                    content_id=content.id,
                    concept_type=clue_type.value,
                    value=concept,
                    normalized_value=normalized,
                    occurrence_count=1,
                )
                self.session.add(concept_row)
            else:
                concept_row.last_seen_at = datetime.now()
                concept_row.occurrence_count += 1

            scores = {
                "novelty": float(finding.get("novelty", 100 if is_new else 40)),
                "demand_intent": float(finding.get("demand_intent", 0)),
                "timeliness": float(finding.get("timeliness", 0)),
                "engagement_velocity": float(finding.get("engagement_velocity", 0)),
                "external_validation": float(finding.get("external_validation", 0)),
            }
            total_score = round(
                scores["novelty"] * 0.25
                + scores["demand_intent"] * 0.25
                + scores["timeliness"] * 0.20
                + scores["engagement_velocity"] * 0.20
                + scores["external_validation"] * 0.10,
                1,
            )
            forced_level = finding.get("force_level")
            if (
                not forced_level
                and clue_type == RadarClueType.new_demand
                and scores["demand_intent"] >= 70
            ):
                forced_level = RadarClueLevel.important.value
            level = self._level_for_finding(
                total_score,
                forced_level,
                concept_row.occurrence_count,
            )
            signature = clue_signature(content.game_id, clue_type, concept)
            clue = (
                await self.session.execute(
                    select(RadarClue).where(RadarClue.signature == signature)
                )
            ).scalar()
            evidence_ids = [content.id]
            if clue is None:
                clue = RadarClue(
                    signature=signature,
                    game_id=content.game_id,
                    clue_type=clue_type,
                    level=level,
                    title=self._title_for(clue_type, concept),
                    summary=str(finding.get("summary") or "")[:1000],
                    term=concept[:256],
                    trigger_reason=str(finding.get("trigger_reason") or self._reason_for(clue_type)),
                    evidence_content_ids=json.dumps(evidence_ids, ensure_ascii=False),
                    score_detail=json.dumps(scores, ensure_ascii=False),
                    engagement_detail=json.dumps(finding.get("engagement_detail") or {}, ensure_ascii=False),
                    suggested_tool_type=str(finding.get("suggested_tool_type") or ""),
                    total_score=total_score,
                )
                self.session.add(clue)
            else:
                existing_evidence = self._json_list(clue.evidence_content_ids)
                if content.id not in existing_evidence:
                    existing_evidence.append(content.id)
                clue.evidence_content_ids = json.dumps(existing_evidence, ensure_ascii=False)
                clue.last_seen_at = datetime.now()
                clue.level = self._max_level(clue.level, level)
                clue.total_score = max(clue.total_score, total_score)
                source_label = content.source_id or content.id
                if source_label not in clue.summary:
                    clue.summary = f"{clue.summary} [来源:{source_label}]".strip()
                if finding.get("suggested_tool_type"):
                    clue.suggested_tool_type = str(finding["suggested_tool_type"])
                if clue.status == RadarClueStatus.dismissed and clue.level == RadarClueLevel.urgent:
                    clue.status = RadarClueStatus.pending
                    clue.suppressed_until = None
            clues.append(clue)

        await self.session.flush()
        return clues

    async def _ensure_scan_state(self, content_id: str) -> ContentScanState:
        state = await self.session.get(ContentScanState, content_id)
        if state is None:
            state = ContentScanState(content_id=content_id)
            self.session.add(state)
            await self.session.flush()
        return state

    def _extract_concepts(self, content: PlatformContent) -> list[str]:
        text = f"{content.title or ''} {content.body or ''}"
        concepts: list[str] = []
        for pattern in CONCEPT_PATTERNS:
            concepts.extend(match.strip(" ，。！？:：") for match in pattern.findall(text))
        try:
            extra = json.loads(content.extra_data or "{}")
        except (TypeError, ValueError):
            extra = {}
        keyword_hit = str(extra.get("keyword_hit") or extra.get("search_keyword") or "").strip()
        if keyword_hit and keyword_hit not in {"工具", "体验服"}:
            concepts.append(keyword_hit)

        deduped = []
        seen = set()
        for concept in concepts:
            normalized = normalize_concept(concept)
            if len(normalized) < 2 or concept in CONCEPT_STOP_WORDS or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(concept)
        return deduped

    @staticmethod
    def _has_experience_context(text: str) -> bool:
        return any(word in text for word in ("体验服", "测试服", "先遣服", "共研服", "内测", "封测"))

    @staticmethod
    def _level_for_finding(total_score: float, forced: str | None, occurrences: int) -> RadarClueLevel:
        if forced:
            return RadarClueLevel(forced)
        if total_score >= 80:
            return RadarClueLevel.urgent
        if total_score >= 55 or occurrences >= 2:
            return RadarClueLevel.important
        return RadarClueLevel.watch

    @staticmethod
    def _max_level(current: RadarClueLevel, candidate: RadarClueLevel) -> RadarClueLevel:
        rank = {
            RadarClueLevel.watch: 1,
            RadarClueLevel.important: 2,
            RadarClueLevel.urgent: 3,
        }
        return current if rank[current] >= rank[candidate] else candidate

    @staticmethod
    def _title_for(clue_type: RadarClueType, concept: str) -> str:
        labels = {
            RadarClueType.new_term: "首次发现",
            RadarClueType.new_demand: "疑似新需求",
            RadarClueType.experience_update: "体验服更新",
            RadarClueType.experience_leak: "体验服爆料",
            RadarClueType.qualification_change: "资格变化",
            RadarClueType.engagement_surge: "互动突增",
            RadarClueType.external_solution: "外部解决方案",
        }
        return f"{labels[clue_type]}：{concept}"[:512]

    @staticmethod
    def _reason_for(clue_type: RadarClueType) -> str:
        return {
            RadarClueType.new_term: "该概念首次与当前游戏结合出现",
            RadarClueType.new_demand: "内容表达了新的用户目标或未满足问题",
            RadarClueType.experience_update: "检测到体验服更新信息",
            RadarClueType.experience_leak: "检测到体验服爆料信息",
            RadarClueType.qualification_change: "检测到资格或招募节点变化",
            RadarClueType.engagement_surge: "内容互动指标短时间快速增长",
            RadarClueType.external_solution: "检测到用户自制或外部解决方案",
        }[clue_type]

    @staticmethod
    def _json_list(value: str) -> list[str]:
        try:
            data = json.loads(value or "[]")
        except (TypeError, ValueError):
            return []
        return [str(item) for item in data] if isinstance(data, list) else []
