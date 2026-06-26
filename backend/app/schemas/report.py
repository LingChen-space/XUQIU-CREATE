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


class DashboardRadarClue(BaseModel):
    id: str
    game_id: str
    game_name: str
    title: str
    term: str = ""
    summary: str = ""
    level: str
    status: str
    clue_type: str
    suggested_tool_type: str = ""
    total_score: float = 0.0
    keyword_priority: str = ""
    keyword_category: str = ""
    evidence_count: int = 0
    first_seen_at: datetime
    last_seen_at: datetime


class DashboardSummary(BaseModel):
    """看板首页概览。"""
    today_date: date
    today_analysis_completed: bool = False
    total_demands_today: int
    radar_clues: list[DashboardRadarClue] = []
    top_demands: list[DemandCard]
    experience_server_demands: list[DemandCard] = []
    trending_games: list[dict]
    tool_type_distribution: dict[str, int]
    latest_report_summary: str = ""
    daily_analysis: DailySummaryAnalysis = DailySummaryAnalysis()
