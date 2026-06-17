"""游戏相关 Schema。"""

from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional


class GameCreate(BaseModel):
    name: str
    genre: str = "其他"
    publisher: str = ""
    status: str = "在运营"
    haoyou_id: str = ""
    cover_url: str = ""
    priority_weight: int | None = None
    description: str = ""
    notes: str = ""

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid = {"热门", "在运营", "测试中", "已停运"}
        if v not in valid:
            raise ValueError(f"无效状态: {v}，可选: {valid}")
        return v

    @field_validator("priority_weight")
    @classmethod
    def validate_priority_weight(cls, v: int | None) -> int | None:
        if v is None:
            return v
        if v < 1 or v > 5:
            raise ValueError("游戏权重需在 1-5 之间")
        return v


class GameUpdate(BaseModel):
    name: Optional[str] = None
    genre: Optional[str] = None
    publisher: Optional[str] = None
    status: Optional[str] = None
    haoyou_id: Optional[str] = None
    cover_url: Optional[str] = None
    priority_weight: Optional[int] = None
    description: Optional[str] = None
    notes: Optional[str] = None


class GameOut(BaseModel):
    id: str
    name: str
    genre: str
    publisher: str
    status: str
    haoyou_id: str
    cover_url: str
    priority_weight: int
    description: str
    notes: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
