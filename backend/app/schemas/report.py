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


class DemandLevelBreakdown(BaseModel):
    s_count: int = 0
    a_count: int = 0
    b_count: int = 0
    c_count: int = 0


class DailySummaryAnalysis(BaseModel):
    """每日总结分析 - 自动生成的需求洞察。"""
    total_demands: int = 0
    avg_potential_score: float = 0.0
    level_breakdown: DemandLevelBreakdown = DemandLevelBreakdown()
    hot_tool_types: list[dict] = []       # [{type: "配装/战备工具", count: 5}, ...]
    hot_genres: list[dict] = []           # [{genre: "FPS", count: 3}, ...]
    signal_summary: dict[str, float] = {} # avg of each signal dimension
    top_recommendations: list[str] = []   # top 3 demand titles
    summary_text: str = ""                # auto-generated paragraph


class DashboardSummary(BaseModel):
    """看板首页概览。"""
    today_date: date
    total_demands_today: int
    top_demands: list[DemandCard]
    trending_games: list[dict]
    tool_type_distribution: dict[str, int]
    latest_report_summary: str = ""
    daily_analysis: DailySummaryAnalysis = DailySummaryAnalysis()
