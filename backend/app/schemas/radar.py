"""早期需求雷达 API Schema。"""

from pydantic import BaseModel


class RadarEvidenceOut(BaseModel):
    id: str
    platform: str
    title: str
    url: str
    published_at: str


class RadarCoverageOut(BaseModel):
    total_contents: int = 0
    new_contents: int = 0
    rule_completed: int = 0
    model_completed: int = 0
    pending: int = 0
    failed: int = 0
    collection_success: int = 0
    collection_failed: int = 0


class RadarClueOut(BaseModel):
    id: str
    game_id: str
    game_name: str
    type: str
    level: str
    status: str
    title: str
    summary: str
    term: str
    trigger_reason: str
    evidence: list[RadarEvidenceOut]
    scores: dict
    engagement: dict
    suggested_tool_type: str
    total_score: float
    first_seen_at: str
    last_seen_at: str
    suppressed_until: str | None = None
    demand_id: str | None = None


class RadarSummaryOut(BaseModel):
    urgent_count: int = 0
    important_count: int = 0
    watch_count: int = 0
    surge_count: int = 0
    confirmed_today: int = 0
    coverage: RadarCoverageOut
    clues: list[RadarClueOut]
