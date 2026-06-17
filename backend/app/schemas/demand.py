"""需求相关 Schema。"""

from pydantic import BaseModel, field_validator
from datetime import datetime, date
from typing import Optional


class SignalSnapshot(BaseModel):
    """信号得分快照。"""
    repeat_question: float = 0.0
    info_scatter: float = 0.0
    grassroots_tool: float = 0.0
    scarcity: float = 0.0
    mechanism_complexity: float = 0.0
    content_heat: float = 0.0
    external_platform_tool: float = 0.0


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


EXPERIENCE_SERVER_KEYWORDS = ["体验服", "测试服", "先遣服", "共研服", "内测", "封测"]
EXPERIENCE_FOCUS_KEYWORDS = [
    ("爆料内容", ["爆料", "曝光", "情报", "前瞻", "新角色", "新英雄", "新武器", "新地图", "新玩法"]),
    ("更新内容", ["更新", "版本", "改动", "调整", "补丁", "公告", "平衡", "上线内容"]),
    ("资格招募", ["资格", "招募", "报名", "申请", "抢码", "激活码", "邀请码", "开启", "名额"]),
]


def _join_demand_text(*parts: str) -> str:
    return " ".join(str(part or "") for part in parts)


def extract_experience_focus(text: str) -> list[str]:
    """提取体验服需求关注点。"""
    focus = [
        label
        for label, keywords in EXPERIENCE_FOCUS_KEYWORDS
        if any(keyword in text for keyword in keywords)
    ]
    return focus or ["资格招募"]


def classify_demand_category(
    game_name: str,
    title: str,
    tool_type: str,
    description: str = "",
    reasoning: str = "",
) -> str:
    """区分工具需求和体验服需求。"""
    text = _join_demand_text(game_name, title, tool_type, description, reasoning)
    return "experience_server" if any(keyword in text for keyword in EXPERIENCE_SERVER_KEYWORDS) else "tool"


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
    demand_category: str = "tool"
    experience_focus: list[str] = []
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
    demand_category: str = "tool"
    experience_focus: list[str] = []
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
    demand_category: str = "tool"
    experience_focus: list[str] = []
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
