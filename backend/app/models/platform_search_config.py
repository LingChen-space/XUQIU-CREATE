"""平台搜索词配置表 — 每款游戏在每个平台上可配置多个搜索关键词。"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, ForeignKey, func, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.sqlite import TEXT

from app.database import Base


class PlatformSearchConfig(Base):
    __tablename__ = "platform_search_configs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    game_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("games.id", ondelete="CASCADE"),
        nullable=True, default=None, index=True, comment="关联游戏(全局配置时为NULL)"
    )
    platform: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="平台标识: douyin/taptap/xiaoheihe/bilibili..."
    )
    keywords: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="搜索关键词，逗号分隔"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否启用"
    )
    crawl_count: Mapped[int] = mapped_column(
        Integer, default=50, server_default="50", comment="每次抓取条数"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
