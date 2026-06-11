"""日报相关 API。"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date

from app.database import get_db
from app.models.daily_report import DailyReport
from app.models.demand import Demand
from app.services.report_generator import ReportGenerator
from app.api.demands import _build_demand_card
from app.schemas.report import DailyReportOut, DashboardSummary
from app.models.game import Game

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/latest", response_model=DailyReportOut)
async def get_latest_report(db: AsyncSession = Depends(get_db)):
    """获取最新一期日报。"""
    gen = ReportGenerator(db)
    report = await gen.get_latest_report()
    if not report:
        raise HTTPException(status_code=404, detail="暂无日报")

    # 构建 top demands 卡片
    try:
        top_ids = json.loads(report.top_demand_ids)
    except (json.JSONDecodeError, TypeError):
        top_ids = []

    top_cards = []
    if top_ids:
        stmt = select(Demand).where(Demand.id.in_(top_ids)).order_by(Demand.potential_score.desc())
        result = await db.execute(stmt)
        demands = result.scalars().all()
        for d in demands:
            card = await _build_demand_card(d, db)
            top_cards.append(card)

    return DailyReportOut(
        id=report.id,
        report_date=report.report_date,
        summary=report.summary,
        top_demands=top_cards,
        total_demands=report.total_demands,
        created_at=report.created_at,
    )


@router.get("/{report_date}", response_model=DailyReportOut)
async def get_report_by_date(report_date: str, db: AsyncSession = Depends(get_db)):
    """按日期获取日报。"""
    try:
        dt = date.fromisoformat(report_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")

    gen = ReportGenerator(db)
    report = await gen.get_report_by_date(dt)
    if not report:
        raise HTTPException(status_code=404, detail=f"{report_date} 的日报不存在")

    try:
        top_ids = json.loads(report.top_demand_ids)
    except (json.JSONDecodeError, TypeError):
        top_ids = []

    top_cards = []
    if top_ids:
        stmt = select(Demand).where(Demand.id.in_(top_ids)).order_by(Demand.potential_score.desc())
        result = await db.execute(stmt)
        demands = result.scalars().all()
        for d in demands:
            card = await _build_demand_card(d, db)
            top_cards.append(card)

    return DailyReportOut(
        id=report.id,
        report_date=report.report_date,
        summary=report.summary,
        top_demands=top_cards,
        total_demands=report.total_demands,
        created_at=report.created_at,
    )
