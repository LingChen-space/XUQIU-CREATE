"""采集进度追踪表 —— 记录每对 (平台, 关键词) 的采集状态。"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CrawlProgress(Base):
    __tablename__ = "crawl_progress"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    platform: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="平台标识: xiaoheihe/taptap/douyin..."
    )
    keyword: Mapped[str] = mapped_column(
        String(256), nullable=False, index=True, comment="搜索关键词"
    )
    crawl_count: Mapped[int] = mapped_column(
        Integer, default=50, comment="抓取条数"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending",
        comment="状态: pending/running/completed/failed"
    )
    items_fetched: Mapped[int] = mapped_column(
        Integer, default=0, comment="从监控服务获取的原始条数"
    )
    items_ingested: Mapped[int] = mapped_column(
        Integer, default=0, comment="实际入库条数（去重后）"
    )
    error_msg: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None, comment="失败时的错误信息"
    )
    result_detail: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None, comment="采集结果明细JSON，包含少入库原因"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None, comment="开始时间"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None, comment="完成时间"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
