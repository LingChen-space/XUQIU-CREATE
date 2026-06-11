"""需求相关 Schema。"""

from pydantic import BaseModel, field_validator
from datetime import datetime, date
from typing import Optional


class SignalSnapshot(BaseModel):
    """六维信号得分快照。"""
    repeat_question: float = 0.0
    info_scatter: float = 0.0
    grassroots_tool: float = 0.0
    scarcity: float = 0.0
    mechanism_complexity: float = 0.0
    content_heat: float = 0.0


class LLMAnalysisOut(BaseModel):
    high_freq_questions: list[str] = []
    info_gap: str = ""
    tool_feasibility: int = 0
    reasoning: str = ""
    tool_type_suggestion: str = ""


class EvidencePost(BaseModel):
    id: str
    platform: str
    url: str
    title: str
    relevance: str = "high"


def compute_demand_level(score: float) -> str:
    """根据潜力分计算需求等级。"""
    if score >= 85:
        return "S级"
    elif score >= 70:
        return "A级"
    elif score >= 50:
        return "B级"
    else:
        return "C级"


class DemandCard(BaseModel):
    """需求列表卡片。"""
    id: str
    game_id: str
    game_name: str = ""
    game_genre: str = ""
    tool_type: str
    title: str
    description: str = ""
    potential_score: float
    tool_feasibility: int
    status: str
    signals: SignalSnapshot
    llm_reasoning: str = ""
    demand_date: date
    demand_level: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class DemandHistoryCard(BaseModel):
    """历史排行榜卡片 — 精简但含关键字段。"""
    id: str
    game_id: str
    game_name: str = ""
    game_genre: str = ""
    tool_type: str
    title: str
    description: str = ""
    potential_score: float
    tool_feasibility: int
    status: str
    demand_level: str = ""
    demand_date: date
    created_at: datetime
    llm_reasoning: str = ""
    signal_scores: dict[str, float] = {}

    class Config:
        from_attributes = True


class DemandDetail(BaseModel):
    """需求详情（含证据链）。"""
    id: str
    game_id: str
    game_name: str = ""
    game_genre: str = ""
    game_publisher: str = ""
    tool_type: str
    title: str
    description: str = ""
    potential_score: float
    tool_feasibility: int
    status: str
    signals: SignalSnapshot
    llm_analysis: LLMAnalysisOut
    evidence_posts: list[EvidencePost] = []
    similar_past_demands: list[dict] = []
    notes: str = ""
    demand_date: date
    demand_level: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class DemandUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class HistoryLeaderboardOut(BaseModel):
    """历史排行榜输出。"""
    date_range_start: date
    date_range_end: date
    total_ranked: int
    leaderboard: list[DemandHistoryCard]
