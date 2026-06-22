"""Raw records fetched from external monitor sources."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExternalMonitorRecord(Base):
    __tablename__ = "external_monitor_records"
    __table_args__ = (
        UniqueConstraint("source_key", "external_id", name="uq_external_monitor_record_source_external"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    feed_type: Mapped[str] = mapped_column(String(32), nullable=False, default="", server_default="", index=True)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="", server_default="")
    url: Mapped[str] = mapped_column(String(1024), nullable=False, default="", server_default="")
    raw_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", server_default="{}")
    scan_last_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
