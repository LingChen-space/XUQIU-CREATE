"""需求相关 API。"""

import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, timedelta

from app.database import get_db
from app.models.game import Game, GameStatus
from app.models.demand import Demand, DemandStatus
from app.models.platform_content import PlatformContent
from app.schemas.demand import (
    DemandCard, DemandDetail, DemandUpdate,
    DemandHistoryCard, HistoryLeaderboardOut,
    SignalSnapshot, LLMAnalysisOut, EvidencePost,
    build_experience_server_insight,
    classify_demand_category,
    compute_demand_level,
    extract_experience_focus,
)

router = APIRouter(prefix="/api/demands", tags=["demands"])


async def _build_demand_card(demand: Demand, db: AsyncSession) -> DemandCard:
    """构建需求卡片（含游戏名等关联信息）。"""
    # 游戏名
    game_stmt = select(Game).where(Game.id == demand.game_id)
    game_result = await db.execute(game_stmt)
    game = game_result.scalar()

    # 解析信号快照
    try:
        signals_dict = json.loads(demand.signal_snapshot)
    except (json.JSONDecodeError, TypeError):
        signals_dict = {}

    # 解析 LLM 分析取 reasoning
    try:
        llm = json.loads(demand.llm_analysis)
        llm_reasoning = llm.get("reasoning", "")
    except (json.JSONDecodeError, TypeError):
        llm_reasoning = ""
    category = classify_demand_category(
        game.name if game else "",
        demand.title,
        demand.tool_type.value,
        demand.description,
        llm_reasoning,
    )
    focus_text = " ".join([demand.title, demand.description or "", llm_reasoning])
    experience_focus = extract_experience_focus(focus_text) if category == "experience_server" else []
    experience_insight = (
        build_experience_server_insight(demand.title, demand.description, llm_reasoning)
        if category == "experience_server"
        else None
    )

    return DemandCard(
        id=demand.id,
        game_id=demand.game_id,
        game_name=game.name if game else "未知游戏",
        game_genre=game.genre.value if game else "",
        tool_type=demand.tool_type.value,
        title=demand.title,
        description=demand.description,
        potential_score=demand.potential_score,
        tool_feasibility=demand.tool_feasibility,
        status=demand.status.value,
        signals=SignalSnapshot(
            repeat_question=signals_dict.get("重复提问密度", 0),
            info_scatter=signals_dict.get("信息分散度", 0),
            grassroots_tool=signals_dict.get("民间工具萌芽", 0),
            scarcity=signals_dict.get("资格稀缺信号", 0),
            mechanism_complexity=signals_dict.get("机制复杂度", 0),
            content_heat=signals_dict.get("内容热度", 0),
            external_platform_tool=signals_dict.get("外部平台工具上线", 0),
        ),
        llm_reasoning=llm_reasoning,
        demand_category=category,
        experience_focus=experience_focus,
        experience_insight=experience_insight,
        demand_date=demand.demand_date,
        demand_level=compute_demand_level(demand.potential_score),
        created_at=demand.created_at,
    )


async def _build_history_card(demand: Demand, db: AsyncSession) -> DemandHistoryCard:
    """构建历史排行榜卡片。"""
    game_stmt = select(Game).where(Game.id == demand.game_id)
    game_result = await db.execute(game_stmt)
    game = game_result.scalar()

    try:
        signals_dict = json.loads(demand.signal_snapshot)
    except (json.JSONDecodeError, TypeError):
        signals_dict = {}

    try:
        llm = json.loads(demand.llm_analysis)
        llm_reasoning = llm.get("reasoning", "")
    except (json.JSONDecodeError, TypeError):
        llm_reasoning = ""
    category = classify_demand_category(
        game.name if game else "",
        demand.title,
        demand.tool_type.value,
        demand.description,
        llm_reasoning,
    )
    focus_text = " ".join([demand.title, demand.description or "", llm_reasoning])
    experience_focus = extract_experience_focus(focus_text) if category == "experience_server" else []
    experience_insight = (
        build_experience_server_insight(demand.title, demand.description, llm_reasoning)
        if category == "experience_server"
        else None
    )

    return DemandHistoryCard(
        id=demand.id,
        game_id=demand.game_id,
        game_name=game.name if game else "未知游戏",
        game_genre=game.genre.value if game else "",
        tool_type=demand.tool_type.value,
        title=demand.title,
        description=demand.description,
        potential_score=demand.potential_score,
        tool_feasibility=demand.tool_feasibility,
        status=demand.status.value,
        demand_level=compute_demand_level(demand.potential_score),
        demand_category=category,
        experience_focus=experience_focus,
        experience_insight=experience_insight,
        demand_date=demand.demand_date,
        created_at=demand.created_at,
        llm_reasoning=llm_reasoning,
        signal_scores=signals_dict,
    )


@router.get("", response_model=list[DemandCard])
async def list_demands(
    game_id: str | None = None,
    tool_type: str | None = None,
    status: str | None = None,
    min_score: float = 0,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """获取需求列表，支持多维度筛选。"""
    stmt = select(Demand)
    if game_id:
        stmt = stmt.where(Demand.game_id == game_id)
    if tool_type:
        stmt = stmt.where(Demand.tool_type == tool_type)
    if status:
        stmt = stmt.where(Demand.status == status)
    stmt = stmt.where(Demand.potential_score >= min_score)
    stmt = stmt.order_by(Demand.potential_score.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    demands = result.scalars().all()

    cards = []
    for d in demands:
        card = await _build_demand_card(d, db)
        cards.append(card)
    return cards


@router.get("/history", response_model=HistoryLeaderboardOut)
async def get_history_leaderboard(
    min_score: float = Query(default=0, description="最低潜力分阈值"),
    max_days: int = Query(default=90, description="回溯天数，默认90天"),
    limit: int = Query(default=50, le=200, description="返回条数上限"),
    db: AsyncSession = Depends(get_db),
):
    """获取历史需求排行榜：按潜力分降序排列跨日期的所有需求。"""
    today = date.today()
    start_date = today - timedelta(days=max_days)

    stmt = (
        select(Demand)
        .where(
            and_(
                Demand.demand_date >= start_date,
                Demand.demand_date <= today,
                Demand.potential_score >= min_score,
                Demand.status.notin_(["已上线", "已驳回"]),
            )
        )
        .order_by(Demand.potential_score.desc(), Demand.demand_date.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    demands = result.scalars().all()

    leaderboard = []
    for d in demands:
        card = await _build_history_card(d, db)
        leaderboard.append(card)

    return HistoryLeaderboardOut(
        date_range_start=start_date,
        date_range_end=today,
        total_ranked=len(leaderboard),
        leaderboard=leaderboard,
    )


@router.get("/today", response_model=list[DemandCard])
async def get_today_demands(
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """获取今日需求。"""
    today = date.today()
    stmt = (
        select(Demand)
        .where(Demand.demand_date == today)
        .order_by(Demand.potential_score.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    demands = result.scalars().all()

    cards = []
    for d in demands:
        card = await _build_demand_card(d, db)
        cards.append(card)
    return cards


@router.get("/{demand_id}", response_model=DemandDetail)
async def get_demand_detail(demand_id: str, db: AsyncSession = Depends(get_db)):
    """获取需求详情（含证据链）。"""
    stmt = select(Demand).where(Demand.id == demand_id)
    result = await db.execute(stmt)
    demand = result.scalar()
    if not demand:
        raise HTTPException(status_code=404, detail="需求不存在")

    # 游戏信息
    game_stmt = select(Game).where(Game.id == demand.game_id)
    game_result = await db.execute(game_stmt)
    game = game_result.scalar()

    # 信号快照
    try:
        signals_dict = json.loads(demand.signal_snapshot)
    except (json.JSONDecodeError, TypeError):
        signals_dict = {}

    # LLM 分析
    try:
        llm_dict = json.loads(demand.llm_analysis)
    except (json.JSONDecodeError, TypeError):
        llm_dict = {}
    reasoning = llm_dict.get("reasoning", "")
    category = classify_demand_category(
        game.name if game else "",
        demand.title,
        demand.tool_type.value,
        demand.description,
        reasoning,
    )
    focus_text = " ".join([demand.title, demand.description or "", reasoning])

    # 证据帖
    try:
        evidence_ids = json.loads(demand.evidence_post_ids)
    except (json.JSONDecodeError, TypeError):
        evidence_ids = []

    evidence_posts = []
    if evidence_ids:
        ev_stmt = select(PlatformContent).where(PlatformContent.id.in_(evidence_ids))
        ev_result = await db.execute(ev_stmt)
        contents = ev_result.scalars().all()
        for c in contents:
            evidence_posts.append(EvidencePost(
                id=c.id,
                platform=c.platform.value,
                url=c.url,
                title=c.title,
                relevance="high",
            ))
    evidence_text = " ".join(ep.title for ep in evidence_posts)
    experience_focus = extract_experience_focus(focus_text) if category == "experience_server" else []
    experience_insight = (
        build_experience_server_insight(demand.title, demand.description, reasoning, evidence_text)
        if category == "experience_server"
        else None
    )

    # 相似历史需求
    sim_stmt = (
        select(Demand)
        .where(
            and_(
                Demand.game_id == demand.game_id,
                Demand.id != demand.id,
            )
        )
        .order_by(Demand.demand_date.desc())
        .limit(5)
    )
    sim_result = await db.execute(sim_stmt)
    similar = sim_result.scalars().all()
    similar_list = [
        {"id": s.id, "title": s.title, "demand_date": str(s.demand_date), "potential_score": s.potential_score}
        for s in similar
    ]

    return DemandDetail(
        id=demand.id,
        game_id=demand.game_id,
        game_name=game.name if game else "未知游戏",
        game_genre=game.genre.value if game else "",
        game_publisher=game.publisher if game else "",
        tool_type=demand.tool_type.value,
        title=demand.title,
        description=demand.description,
        potential_score=demand.potential_score,
        tool_feasibility=demand.tool_feasibility,
        status=demand.status.value,
        signals=SignalSnapshot(
            repeat_question=signals_dict.get("重复提问密度", 0),
            info_scatter=signals_dict.get("信息分散度", 0),
            grassroots_tool=signals_dict.get("民间工具萌芽", 0),
            scarcity=signals_dict.get("资格稀缺信号", 0),
            mechanism_complexity=signals_dict.get("机制复杂度", 0),
            content_heat=signals_dict.get("内容热度", 0),
            external_platform_tool=signals_dict.get("外部平台工具上线", 0),
        ),
        llm_analysis=LLMAnalysisOut(
            high_freq_questions=llm_dict.get("high_freq_questions", []),
            info_gap=llm_dict.get("info_gap", ""),
            tool_feasibility=llm_dict.get("tool_feasibility", 0),
            reasoning=llm_dict.get("reasoning", ""),
            tool_type_suggestion=llm_dict.get("tool_type_suggestion", ""),
        ),
        demand_category=category,
        experience_focus=experience_focus,
        experience_insight=experience_insight,
        evidence_posts=evidence_posts,
        similar_past_demands=similar_list,
        notes=demand.notes,
        demand_date=demand.demand_date,
        demand_level=compute_demand_level(demand.potential_score),
        created_at=demand.created_at,
    )


@router.patch("/{demand_id}", response_model=dict)
async def update_demand(
    demand_id: str,
    payload: DemandUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新需求状态和备注。"""
    stmt = select(Demand).where(Demand.id == demand_id)
    result = await db.execute(stmt)
    demand = result.scalar()
    if not demand:
        raise HTTPException(status_code=404, detail="需求不存在")

    if payload.status is not None:
        try:
            demand.status = DemandStatus._value2member_map_[payload.status]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"无效状态: {payload.status}")

    if payload.notes is not None:
        demand.notes = payload.notes

    await db.commit()
    return {"ok": True, "id": demand.id}
