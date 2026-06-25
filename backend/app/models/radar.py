"""早期需求雷达相关数据模型。"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.platform_content import ContentPlatform


class RadarClueType(str, enum.Enum):
    new_term = "new_term"
    new_demand = "new_demand"
    experience_update = "experience_update"
    experience_leak = "experience_leak"
    qualification_change = "qualification_change"
    engagement_surge = "engagement_surge"
    external_solution = "external_solution"


class RadarClueLevel(str, enum.Enum):
    urgent = "urgent"
    important = "important"
    watch = "watch"


class RadarClueStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    dismissed = "dismissed"
    promoted = "promoted"


class ContentScanState(Base):
    __tablename__ = "content_scan_states"

    content_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("platform_contents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    rule_status: Mapped[str] = mapped_column(String(24), default="pending", server_default="pending")
    model_status: Mapped[str] = mapped_column(String(24), default="pending", server_default="pending")
    model_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str] = mapped_column(Text, default="", server_default="")
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rule_scanned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    model_scanned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ContentConcept(Base):
    __tablename__ = "content_concepts"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "concept_type",
            "normalized_value",
            name="uq_content_concepts_game_type_value",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    game_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("platform_contents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept_type: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str] = mapped_column(String(256), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(256), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ContentMetricSnapshot(Base):
    __tablename__ = "content_metric_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    content_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("platform_contents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[ContentPlatform] = mapped_column(SAEnum(ContentPlatform), nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    share_count: Mapped[int] = mapped_column(Integer, default=0)
    captured_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class RadarClue(Base):
    __tablename__ = "radar_clues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    signature: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    game_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clue_type: Mapped[RadarClueType] = mapped_column(SAEnum(RadarClueType), nullable=False)
    level: Mapped[RadarClueLevel] = mapped_column(SAEnum(RadarClueLevel), nullable=False)
    status: Mapped[RadarClueStatus] = mapped_column(
        SAEnum(RadarClueStatus),
        default=RadarClueStatus.pending,
        server_default=RadarClueStatus.pending.value,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", server_default="")
    term: Mapped[str] = mapped_column(String(256), default="", server_default="")
    trigger_reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    evidence_content_ids: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    score_detail: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    engagement_detail: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    suggested_tool_type: Mapped[str] = mapped_column(String(64), default="", server_default="")
    total_score: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    suppressed_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    demand_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("demands.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class RadarCollectionState(Base):
    __tablename__ = "radar_collection_states"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "platform",
            "mode",
            name="uq_radar_collection_game_platform_mode",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    game_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    mode: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="idle", server_default="idle")
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="", server_default="")
    new_content_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
