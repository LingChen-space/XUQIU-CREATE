"""日报表 — 每日分析汇总。"""

import uuid
from datetime import datetime, date
from sqlalchemy import String, DateTime, Date, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, comment="报告日期")
    summary: Mapped[str] = mapped_column(Text, default="", comment="LLM生成的日报摘要")
    top_demand_ids: Mapped[str] = mapped_column(Text, default="[]", comment="TOP需求ID列表JSON")
    trending_game_ids: Mapped[str] = mapped_column(Text, default="[]", comment="趋势游戏ID列表JSON")
    total_demands: Mapped[int] = mapped_column(default=0, comment="当日需求总数")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<DailyReport {self.report_date}>"
