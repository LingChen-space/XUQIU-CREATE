"""需求表 — LLM 分析后产出的结构化需求卡片。"""

import uuid
from datetime import datetime, date
from sqlalchemy import String, DateTime, Integer, Float, ForeignKey, Enum as SAEnum, Date, Text, func
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.database import Base


class ToolType(str, enum.Enum):
    build_calc = "配装/战备工具"
    interactive_map = "交互地图"
    gacha_analysis = "抽卡/概率分析"
    qualification = "资格/福利聚合"
    mechanism_calc = "机制计算器"
    leaderboard = "排行榜/对战数据"
    progress_tracker = "剧情/收集进度"
    guide_system = "攻略辅助"
    simulator = "模拟器"
    database_tool = "数据库"
    other = "其他"


class DemandStatus(str, enum.Enum):
    new = "待评估"
    confirmed = "已采纳"
    developing = "开发中"
    launched = "已上线"
    dismissed = "已驳回"


class Demand(Base):
    __tablename__ = "demands"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    game_id: Mapped[str] = mapped_column(String(36), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联游戏")
    tool_type: Mapped[ToolType] = mapped_column(SAEnum(ToolType), nullable=False, default=ToolType.other, comment="工具类型")
    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="需求标题")
    description: Mapped[str] = mapped_column(Text, default="", comment="需求描述")
    potential_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="爆款潜力分(0-100)")
    tool_feasibility: Mapped[int] = mapped_column(Integer, default=0, comment="工具化可行度(1-5)")
    status: Mapped[DemandStatus] = mapped_column(SAEnum(DemandStatus), nullable=False, default=DemandStatus.new, comment="需求状态")

    # 信号快照 JSON
    signal_snapshot: Mapped[str] = mapped_column(Text, default="{}", comment="信号分快照JSON")
    # LLM 分析全文 JSON
    llm_analysis: Mapped[str] = mapped_column(Text, default="{}", comment="LLM分析JSON")
    # 证据帖 ID 列表 JSON
    evidence_post_ids: Mapped[str] = mapped_column(Text, default="[]", comment="证据帖ID列表JSON")
    # 跟进备注
    notes: Mapped[str] = mapped_column(Text, default="", comment="跟进备注")

    demand_date: Mapped[date] = mapped_column(Date, nullable=False, comment="需求生成日期")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Demand {self.title} score={self.potential_score}>"
