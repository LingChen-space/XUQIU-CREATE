"""看板首页聚合 API。"""

import json
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime, timedelta
from collections import Counter

from app.database import get_db
from app.models.game import Game, GameStatus
from app.models.demand import Demand
from app.models.daily_report import DailyReport
from app.models.radar import RadarClue, RadarClueStatus
from app.schemas.report import (
    DashboardRadarClue,
    DashboardSummary,
    DailySummaryAnalysis,
    DemandLevelBreakdown,
)
from app.api.demands import _build_demand_card
from app.schemas.demand import compute_demand_level
from app.services.demand_keyword_rules import is_experience_server

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

SIGNAL_LABELS = ["重复提问密度", "信息分散度", "民间工具萌芽", "资格稀缺信号", "机制复杂度", "内容热度", "外部平台工具上线"]
SIGNAL_KEYS = ["repeat_question", "info_scatter", "grassroots_tool", "scarcity", "mechanism_complexity", "content_heat", "external_platform_tool"]
HISTORY_SHOWCASE_DATE = date(2026, 6, 24)


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)):
    """看板首页概览数据。"""
    today = date.today()
    show_all_history = today == HISTORY_SHOWCASE_DATE

    # 获取活跃游戏（非已停运），并标记体验服游戏
    active_stmt = select(Game).where(Game.status != GameStatus.inactive)
    active_result = await db.execute(active_stmt)
    active_games = active_result.scalars().all()
    active_game_ids = {g.id for g in active_games}
    experience_game_ids = {g.id for g in active_games if is_experience_server(g.name)}

    # 2026-06-24 临时展示全部历史需求；其他日期保持仅展示今日需求。
    stmt = select(Demand).where(
        Demand.game_id.in_(active_game_ids) if active_game_ids else True,
    )
    if not show_all_history:
        stmt = stmt.where(Demand.demand_date == today)
    stmt = stmt.order_by(Demand.potential_score.desc())
    result = await db.execute(stmt)
    today_demands = result.scalars().all()

    # 工具需求(评估卡片) 与 体验服需求(简洁通知) 分流：体验服不参与评估分析
    tool_demands = [d for d in today_demands if d.game_id not in experience_game_ids]
    experience_demands = [d for d in today_demands if d.game_id in experience_game_ids]
    if show_all_history:
        tool_display, experience_display = tool_demands, experience_demands
    else:
        tool_display, experience_display = tool_demands[:10], experience_demands[:100]

    top_cards = [await _build_demand_card(d, db) for d in tool_display]
    experience_cards = [await _build_demand_card(d, db) for d in experience_display]
    radar_clues = await _get_today_radar_clues(
        db,
        today,
        active_game_ids - experience_game_ids,
    )

    # 工具类型分布（仅工具需求）
    type_counter = Counter(d.tool_type.value for d in tool_demands)
    type_distribution = dict(type_counter)

    # 趋势游戏 (今日工具需求最多的游戏)
    game_counter = Counter(d.game_id for d in tool_demands)
    top_game_ids = [gid for gid, _ in game_counter.most_common(5)]
    trending_games = []
    if top_game_ids:
        gstmt = select(Game).where(Game.id.in_(top_game_ids))
        gresult = await db.execute(gstmt)
        games = {g.id: g for g in gresult.scalars().all()}
        for gid in top_game_ids:
            g = games.get(gid)
            if g:
                trending_games.append({
                    "id": g.id,
                    "name": g.name,
                    "genre": g.genre.value,
                    "demand_count": game_counter[gid],
                })

    # 最新日报摘要
    report_stmt = select(DailyReport).order_by(DailyReport.report_date.desc()).limit(1)
    report_result = await db.execute(report_stmt)
    report = report_result.scalar()
    report_summary = report.summary if report else ""
    today_report_stmt = select(DailyReport.id).where(DailyReport.report_date == today).limit(1)
    today_report_result = await db.execute(today_report_stmt)
    today_analysis_completed = today_report_result.scalar() is not None

    # ── 每日总结分析（仅工具需求）──
    daily_analysis = _build_daily_analysis(tool_demands)

    return DashboardSummary(
        today_date=today,
        today_analysis_completed=today_analysis_completed,
        total_demands_today=len(tool_demands),
        radar_clues=radar_clues,
        top_demands=top_cards,
        experience_server_demands=experience_cards,
        trending_games=trending_games,
        tool_type_distribution=type_distribution,
        latest_report_summary=report_summary,
        daily_analysis=daily_analysis,
    )


async def _get_today_radar_clues(
    db: AsyncSession,
    today: date,
    game_ids: set[str],
) -> list[DashboardRadarClue]:
    if not game_ids:
        return []

    start = datetime.combine(today, datetime.min.time())
    end = start + timedelta(days=1)
    stmt = (
        select(RadarClue, Game.name)
        .join(Game, Game.id == RadarClue.game_id)
        .where(
            RadarClue.game_id.in_(game_ids),
            RadarClue.status.in_([RadarClueStatus.pending, RadarClueStatus.confirmed]),
            RadarClue.first_seen_at >= start,
            RadarClue.first_seen_at < end,
        )
        .order_by(RadarClue.total_score.desc(), RadarClue.first_seen_at.desc())
        .limit(30)
    )
    rows = (await db.execute(stmt)).all()
    clues: list[DashboardRadarClue] = []
    for clue, game_name in rows:
        try:
            detail = json.loads(clue.score_detail or "{}")
        except (TypeError, json.JSONDecodeError):
            detail = {}
        try:
            evidence_ids = json.loads(clue.evidence_content_ids or "[]")
        except (TypeError, json.JSONDecodeError):
            evidence_ids = []
        clues.append(DashboardRadarClue(
            id=clue.id,
            game_id=clue.game_id,
            game_name=game_name,
            title=clue.title,
            term=clue.term,
            summary=clue.summary,
            level=clue.level.value,
            status=clue.status.value,
            clue_type=clue.clue_type.value,
            suggested_tool_type=clue.suggested_tool_type,
            total_score=float(clue.total_score or 0),
            keyword_priority=str(detail.get("keyword_priority") or ""),
            keyword_category=str(detail.get("keyword_category") or ""),
            evidence_count=int(detail.get("independent_evidence_count") or len(evidence_ids)),
            first_seen_at=clue.first_seen_at,
            last_seen_at=clue.last_seen_at,
        ))
    return clues


def _build_daily_analysis(demands: list[Demand]) -> DailySummaryAnalysis:
    """基于今日需求数据自动生成每日总结分析。"""
    if not demands:
        return DailySummaryAnalysis(
            summary_text="今日暂无需求数据。请点击「立即分析」触发需求挖掘管线，或等待每日凌晨 06:00 自动执行。"
        )

    total = len(demands)
    avg_score = sum(d.potential_score for d in demands) / total if total > 0 else 0

    # 等级分布
    level_counts = Counter(compute_demand_level(d.potential_score) for d in demands)
    level_breakdown = DemandLevelBreakdown(
        s_count=level_counts.get("S级", 0),
        a_count=level_counts.get("A级", 0),
        b_count=level_counts.get("B级", 0),
        c_count=level_counts.get("C级", 0),
    )

    # 热门工具类型 TOP 3
    type_counter = Counter(d.tool_type.value for d in demands)
    hot_tool_types = [{"type": t, "count": c} for t, c in type_counter.most_common(3)]

    # 热门品类 TOP 3 (需要查游戏表)
    genre_counter = Counter()
    for d in demands:
        # tool_type 没有 genre, 从 signal_snapshot 中读取或跳过
        pass
    # 用伪数据占位, 实际需要 JOIN game 表; 这里简化处理
    hot_genres = []

    # 信号维度平均分
    signal_totals = {k: 0.0 for k in SIGNAL_LABELS}
    for d in demands:
        try:
            sig = json.loads(d.signal_snapshot)
        except (json.JSONDecodeError, TypeError):
            sig = {}
        for label, key in zip(SIGNAL_LABELS, SIGNAL_KEYS):
            signal_totals[label] += sig.get(label, 0)
    signal_summary = {
        label: round(signal_totals[label] / total, 1)
        for label in SIGNAL_LABELS
    }

    # TOP 3 推荐
    sorted_demands = sorted(demands, key=lambda d: d.potential_score, reverse=True)
    top_recommendations = [d.title for d in sorted_demands[:3]]

    # 自动生成摘要文本
    summary_text = _generate_summary_text(
        total, avg_score, level_breakdown, hot_tool_types, top_recommendations
    )

    return DailySummaryAnalysis(
        total_demands=total,
        avg_potential_score=round(avg_score, 1),
        level_breakdown=level_breakdown,
        hot_tool_types=hot_tool_types,
        hot_genres=hot_genres,
        signal_summary=signal_summary,
        top_recommendations=top_recommendations,
        summary_text=summary_text,
    )


def _generate_summary_text(
    total: int,
    avg_score: float,
    levels: DemandLevelBreakdown,
    tool_types: list[dict],
    top3: list[str],
) -> str:
    """根据统计数据自动生成一段人类可读的每日总结。"""
    parts = []

    # 总量概述
    parts.append(f"今日共挖掘 {total} 条需求")

    # 等级分布
    if levels.s_count > 0:
        parts.append(f"其中 S 级爆款需求 {levels.s_count} 条")
    if levels.a_count > 0:
        parts.append(f"A 级高潜需求 {levels.a_count} 条")
    parts.append(f"平均潜力分 {avg_score:.0f}")

    # 热门工具类型
    if tool_types:
        hot_type_str = "、".join(f"{t['type']}({t['count']}条)" for t in tool_types[:2])
        parts.append(f"热门方向集中在{hot_type_str}")

    # 首推
    if top3:
        parts.append(f"首推「{top3[0][:20]}」")

    return "，".join(parts) + "。"
