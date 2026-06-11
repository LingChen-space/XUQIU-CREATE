"""日报相关 Schema。"""

from pydantic import BaseModel
from datetime import datetime, date

from app.schemas.demand import DemandCard


class DailyReportOut(BaseModel):
    id: str
    report_date: date
    summary: str
    top_demands: list[DemandCard] = []
    total_demands: int
    created_at: datetime

    class Config:
        from_attributes = True


class DashboardSummary(BaseModel):
    """看板首页概览。"""
    today_date: date
    total_demands_today: int
    top_demands: list[DemandCard]
    trending_games: list[dict]
    tool_type_distribution: dict[str, int]
    latest_report_summary: str = ""
