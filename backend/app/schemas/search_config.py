"""搜索词配置 Schema。"""

from pydantic import BaseModel, field_validator
from datetime import datetime


class SearchConfigCreate(BaseModel):
    """创建搜索词配置。"""
    platform: str  # douyin / taptap / xiaoheihe / bilibili
    keywords: str  # comma-separated
    enabled: bool = True
    crawl_count: int = 50

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = ["douyin", "taptap", "xiaoheihe", "bilibili", "nga", "weibo", "tieba"]
        if v not in allowed:
            raise ValueError(f"不支持的平台: {v}")
        return v

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v: str) -> str:
        cleaned = ",".join(kw.strip() for kw in v.split(",") if kw.strip())
        if not cleaned:
            raise ValueError("至少需要一个搜索关键词")
        return cleaned

    @field_validator("crawl_count")
    @classmethod
    def validate_crawl_count(cls, v: int) -> int:
        if v < 10:
            raise ValueError("抓取条数不能少于10条")
        if v > 1000:
            raise ValueError("抓取条数不能超过1000条")
        return v


class SearchConfigUpdate(BaseModel):
    """更新搜索词配置。"""
    keywords: str | None = None
    enabled: bool | None = None
    crawl_count: int | None = None


class SearchConfigOut(BaseModel):
    """搜索词配置输出。"""
    id: str
    game_id: str | None = None
    platform: str
    keywords: str
    enabled: bool
    crawl_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
