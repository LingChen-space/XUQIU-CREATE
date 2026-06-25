"""早期需求雷达查询与人工反馈接口。"""

import json
import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.demand import Demand, DemandStatus, ToolType
from app.models.game import Game
from app.models.platform_content import PlatformContent
from app.models.platform_search_config import PlatformSearchConfig
from app.models.radar import (
    ContentScanState,
    RadarClue,
    RadarClueLevel,
    RadarClueStatus,
    RadarClueType,
    RadarCollectionState,
)
from app.schemas.radar import (
    RadarClueOut,
    RadarCoverageOut,
    RadarEvidenceOut,
    RadarSummaryOut,
)
from app.services.radar import normalize_concept


router = APIRouter(prefix="/api/radar", tags=["radar"])


def _json_object(value: str) -> dict:
    try:
        data = json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _json_list(value: str) -> list[str]:
    try:
        data = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    return [str(item) for item in data] if isinstance(data, list) else []


async def _clue_out(clue: RadarClue, db: AsyncSession) -> RadarClueOut:
    game = await db.get(Game, clue.game_id)
    evidence_ids = _json_list(clue.evidence_content_ids)
    evidence: list[RadarEvidenceOut] = []
    if evidence_ids:
        contents = (
            await db.execute(
                select(PlatformContent).where(PlatformContent.id.in_(evidence_ids))
            )
        ).scalars().all()
        by_id = {content.id: content for content in contents}
        for content_id in evidence_ids:
            content = by_id.get(content_id)
            if content is None:
                continue
            evidence.append(RadarEvidenceOut(
                id=content.id,
                platform=content.platform.value,
                title=content.title,
                url=content.url,
                published_at=content.published_at.isoformat() if content.published_at else "",
            ))

    return RadarClueOut(
        id=clue.id,
        game_id=clue.game_id,
        game_name=game.name if game else "未知游戏",
        type=clue.clue_type.value,
        level=clue.level.value,
        status=clue.status.value,
        title=clue.title,
        summary=clue.summary,
        term=clue.term,
        trigger_reason=clue.trigger_reason,
        evidence=evidence,
        scores=_json_object(clue.score_detail),
        engagement=_json_object(clue.engagement_detail),
        suggested_tool_type=clue.suggested_tool_type,
        total_score=clue.total_score,
        first_seen_at=clue.first_seen_at.isoformat() if clue.first_seen_at else "",
        last_seen_at=clue.last_seen_at.isoformat() if clue.last_seen_at else "",
        suppressed_until=clue.suppressed_until.isoformat() if clue.suppressed_until else None,
        demand_id=clue.demand_id,
    )


@router.get("/clues", response_model=list[RadarClueOut])
async def list_radar_clues(
    status: str = "pending",
    level: str | None = None,
    type: str | None = None,
    game_id: str | None = None,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(RadarClue)
    if status:
        stmt = stmt.where(RadarClue.status == RadarClueStatus(status))
    if level:
        stmt = stmt.where(RadarClue.level == RadarClueLevel(level))
    if type:
        stmt = stmt.where(RadarClue.clue_type == RadarClueType(type))
    if game_id:
        stmt = stmt.where(RadarClue.game_id == game_id)
    stmt = stmt.order_by(
        RadarClue.level,
        RadarClue.total_score.desc(),
        RadarClue.last_seen_at.desc(),
    ).limit(min(max(limit, 1), 500))
    clues = (await db.execute(stmt)).scalars().all()
    return [await _clue_out(clue, db) for clue in clues]


_LEVEL_RANK = {
    RadarClueLevel.urgent: 0,
    RadarClueLevel.important: 1,
    RadarClueLevel.watch: 2,
}


@router.get("/clues/grouped")
async def list_radar_clues_grouped(
    days: int | None = None,
    min_score: float = 0,
    per_game: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """按游戏聚合的需求词视图：跨 clue_type、按 normalize(term) 去重合并。

    范围 status in (pending, confirmed)。支持 days(最近N天,按 last_seen_at)、
    min_score(总分下限)、per_game(每游戏最多返回前N个) 过滤，供 tab 页精简展示。
    """
    stmt = select(RadarClue).where(
        RadarClue.status.in_(
            [RadarClueStatus.pending, RadarClueStatus.confirmed]
        )
    )
    if days and days > 0:
        stmt = stmt.where(RadarClue.last_seen_at >= datetime.now() - timedelta(days=days))
    if min_score and min_score > 0:
        stmt = stmt.where(RadarClue.total_score >= min_score)
    clues = (await db.execute(stmt)).scalars().all()
    if not clues:
        return []

    games = (
        await db.execute(
            select(Game).where(Game.id.in_({c.game_id for c in clues}))
        )
    ).scalars().all()
    game_map = {g.id: g for g in games}

    # game_id -> {"game": Game, "terms": {normalized_term: 代表词}}
    groups: dict[str, dict] = {}
    for clue in clues:
        game = game_map.get(clue.game_id)
        if game is None:
            continue  # 跳过游戏已被删除的残留线索，避免出现"未知游戏"分组
        norm = normalize_concept(clue.term)
        if not norm:
            continue
        group = groups.setdefault(
            clue.game_id, {"game": game, "terms": {}}
        )
        cur = group["terms"].get(norm)
        if cur is None:
            group["terms"][norm] = {
                "id": clue.id,
                "term": clue.term,
                "level": clue.level.value,
                "total_score": clue.total_score or 0,
                "clue_type": clue.clue_type.value,
                "demand_id": clue.demand_id,
                "status": clue.status.value,
                "merged_count": 1,
            }
        else:
            cur["merged_count"] += 1
            # 代表词取 total_score 最高者
            if (clue.total_score or 0) > cur["total_score"]:
                cur["total_score"] = clue.total_score or 0
                cur["id"] = clue.id
                cur["term"] = clue.term
                cur["clue_type"] = clue.clue_type.value
                cur["demand_id"] = clue.demand_id
                cur["status"] = clue.status.value
            # 等级取组内最高（urgent > important > watch）
            if _LEVEL_RANK.get(clue.level, 9) < _LEVEL_RANK.get(
                RadarClueLevel(cur["level"]), 9
            ):
                cur["level"] = clue.level.value

    result = []
    for game_id, group in groups.items():
        game = group["game"]
        terms = list(group["terms"].values())
        terms.sort(
            key=lambda t: (
                -t["total_score"],
                _LEVEL_RANK.get(RadarClueLevel(t["level"]), 9),
            )
        )
        if per_game and per_game > 0:
            terms = terms[:per_game]
        result.append({
            "game_id": game_id,
            "game_name": game.name if game else "未知游戏",
            "priority_weight": game.priority_weight if game else 0,
            "count": len(terms),
            "clues": terms,
        })
    result.sort(key=lambda x: (-(x["priority_weight"] or 0), -x["count"]))
    return result


@router.get("/summary", response_model=RadarSummaryOut)
async def get_radar_summary(db: AsyncSession = Depends(get_db)):
    pending_clues = (
        await db.execute(
            select(RadarClue)
            .where(RadarClue.status == RadarClueStatus.pending)
            .order_by(RadarClue.total_score.desc(), RadarClue.last_seen_at.desc())
        )
    ).scalars().all()

    total_contents = (await db.execute(select(func.count()).select_from(ContentScanState))).scalar_one()
    rule_completed = (
        await db.execute(
            select(func.count()).select_from(ContentScanState)
            .where(ContentScanState.rule_status == "completed")
        )
    ).scalar_one()
    model_completed = (
        await db.execute(
            select(func.count()).select_from(ContentScanState)
            .where(ContentScanState.model_status == "completed")
        )
    ).scalar_one()
    pending = (
        await db.execute(
            select(func.count()).select_from(ContentScanState)
            .where(ContentScanState.model_status.in_(["pending", "retry_wait"]))
        )
    ).scalar_one()
    failed = (
        await db.execute(
            select(func.count()).select_from(ContentScanState)
            .where(ContentScanState.model_status == "failed")
        )
    ).scalar_one()
    today_start = datetime.combine(date.today(), datetime.min.time())
    new_contents = (
        await db.execute(
            select(func.count()).select_from(PlatformContent)
            .where(PlatformContent.collected_at >= today_start)
        )
    ).scalar_one()
    confirmed_today = (
        await db.execute(
            select(func.count()).select_from(RadarClue)
            .where(
                RadarClue.status.in_([RadarClueStatus.confirmed, RadarClueStatus.promoted]),
                RadarClue.updated_at >= today_start,
            )
        )
    ).scalar_one()
    collection_success = (
        await db.execute(
            select(func.count()).select_from(RadarCollectionState)
            .where(RadarCollectionState.status == "completed")
        )
    ).scalar_one()
    collection_failed = (
        await db.execute(
            select(func.count()).select_from(RadarCollectionState)
            .where(RadarCollectionState.status == "failed")
        )
    ).scalar_one()

    visible = pending_clues[:200]
    return RadarSummaryOut(
        urgent_count=sum(clue.level == RadarClueLevel.urgent for clue in pending_clues),
        important_count=sum(clue.level == RadarClueLevel.important for clue in pending_clues),
        watch_count=sum(clue.level == RadarClueLevel.watch for clue in pending_clues),
        surge_count=sum(clue.clue_type == RadarClueType.engagement_surge for clue in pending_clues),
        confirmed_today=confirmed_today,
        coverage=RadarCoverageOut(
            total_contents=total_contents,
            new_contents=new_contents,
            rule_completed=rule_completed,
            model_completed=model_completed,
            pending=pending,
            failed=failed,
            collection_success=collection_success,
            collection_failed=collection_failed,
        ),
        clues=[await _clue_out(clue, db) for clue in visible],
    )


@router.post("/clues/{clue_id}/confirm", response_model=RadarClueOut)
async def confirm_radar_clue(clue_id: str, db: AsyncSession = Depends(get_db)):
    clue = await db.get(RadarClue, clue_id)
    if clue is None:
        raise HTTPException(status_code=404, detail="雷达线索不存在")
    clue.status = RadarClueStatus.confirmed
    clue.suppressed_until = None

    term = clue.term.strip()
    if term:
        enabled_configs = (
            await db.execute(
                select(PlatformSearchConfig)
                .where(PlatformSearchConfig.enabled == True)  # noqa: E712
            )
        ).scalars().all()
        for platform in sorted({config.platform for config in enabled_configs}):
            existing = (
                await db.execute(
                    select(PlatformSearchConfig).where(
                        PlatformSearchConfig.game_id == clue.game_id,
                        PlatformSearchConfig.platform == platform,
                        PlatformSearchConfig.source_key == "radar_confirmed",
                    )
                )
            ).scalar()
            if existing is None:
                db.add(PlatformSearchConfig(
                    game_id=clue.game_id,
                    platform=platform,
                    keywords=term,
                    enabled=True,
                    crawl_count=50,
                    source_key="radar_confirmed",
                ))
            else:
                keywords = [item.strip() for item in existing.keywords.split(",") if item.strip()]
                if term not in keywords:
                    keywords.append(term)
                    existing.keywords = ",".join(keywords)
    await db.commit()
    return await _clue_out(clue, db)


@router.post("/clues/{clue_id}/dismiss", response_model=RadarClueOut)
async def dismiss_radar_clue(clue_id: str, db: AsyncSession = Depends(get_db)):
    clue = await db.get(RadarClue, clue_id)
    if clue is None:
        raise HTTPException(status_code=404, detail="雷达线索不存在")
    clue.status = RadarClueStatus.dismissed
    clue.suppressed_until = datetime.now() + timedelta(days=30)
    await db.commit()
    return await _clue_out(clue, db)


@router.post("/clues/{clue_id}/promote", response_model=RadarClueOut)
async def promote_radar_clue(clue_id: str, db: AsyncSession = Depends(get_db)):
    clue = await db.get(RadarClue, clue_id)
    if clue is None:
        raise HTTPException(status_code=404, detail="雷达线索不存在")
    demand = await db.get(Demand, clue.demand_id) if clue.demand_id else None
    if demand is None:
        tool_type = ToolType._value2member_map_.get(clue.suggested_tool_type, ToolType.other)
        demand = Demand(
            id=str(uuid.uuid4()),
            game_id=clue.game_id,
            tool_type=tool_type,
            title=clue.title,
            description=clue.summary,
            potential_score=max(clue.total_score, 35),
            tool_feasibility=3,
            status=DemandStatus.new,
            signal_snapshot=json.dumps({}, ensure_ascii=False),
            llm_analysis=json.dumps({
                "reasoning": clue.trigger_reason,
                "radar_scores": _json_object(clue.score_detail),
                "radar_clue_id": clue.id,
            }, ensure_ascii=False),
            evidence_post_ids=clue.evidence_content_ids,
            demand_date=date.today(),
        )
        db.add(demand)
        clue.demand_id = demand.id
    clue.status = RadarClueStatus.promoted
    clue.suppressed_until = None
    await db.commit()
    return await _clue_out(clue, db)
