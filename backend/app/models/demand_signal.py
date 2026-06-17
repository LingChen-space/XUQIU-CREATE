"""需求信号表 — 需求评分每维一条记录。"""

import uuid
from datetime import datetime, date
from sqlalchemy import String, DateTime, Float, ForeignKey, Enum as SAEnum, Date, func
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.database import Base


class SignalType(str, enum.Enum):
    repeat_question = "重复提问密度"
    info_scatter = "信息分散度"
    grassroots_tool = "民间工具萌芽"
    scarcity = "资格稀缺信号"
    mechanism_complexity = "机制复杂度"
    content_heat = "内容热度"
    external_platform_tool = "外部平台工具上线"


class DemandSignal(Base):
    __tablename__ = "demand_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    game_id: Mapped[str] = mapped_column(String(36), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联游戏")
    signal_type: Mapped[SignalType] = mapped_column(SAEnum(SignalType), nullable=False, comment="信号类型")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="信号分(0-100)")
    detail: Mapped[str] = mapped_column(String(2048), default="", comment="计算详情/证据摘要")
    window_date: Mapped[date] = mapped_column(Date, nullable=False, comment="信号计算日期窗口")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<DemandSignal {self.signal_type.value} {self.score}>"
