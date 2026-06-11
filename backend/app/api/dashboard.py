"""看板首页聚合 API。"""

import json
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from collections import Counter

from app.database import get_db
from app.models.game import Game, GameStatus
from app.models.demand import Demand
from app.models.daily_report import DailyReport
from app.schemas.report import DashboardSummary
from app.api.demands import _build_demand_card

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)):
    """看板首页概览数据。"""
    today = date.today()

    # 获取活跃游戏ID（非已停运）
    active_stmt = select(Game.id).where(Game.status != GameStatus.inactive)
    active_result = await db.execute(active_stmt)
    active_game_ids = {row[0] for row in active_result.all()}

    # 今日需求（仅活跃游戏）
    stmt = (
        select(Demand)
        .where(
            Demand.demand_date == today,
            Demand.game_id.in_(active_game_ids) if active_game_ids else True,
        )
        .order_by(Demand.potential_score.desc())
    )
    result = await db.execute(stmt)
    today_demands = result.scalars().all()

    top_cards = []
    for d in today_demands[:10]:
        card = await _build_demand_card(d, db)
        top_cards.append(card)

    # 工具类型分布
    type_counter = Counter(d.tool_type.value for d in today_demands)
    type_distribution = dict(type_counter)

    # 趋势游戏 (今日需求最多的游戏)
    game_counter = Counter(d.game_id for d in today_demands)
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

    return DashboardSummary(
        today_date=today,
        total_demands_today=len(today_demands),
        top_demands=top_cards,
        trending_games=trending_games,
        tool_type_distribution=type_distribution,
        latest_report_summary=report_summary,
    )
