"""External monitor incremental cursor."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExternalMonitorCursor(Base):
    __tablename__ = "external_monitor_cursors"
    __table_args__ = (
        UniqueConstraint("source_key", "feed_type", name="uq_external_monitor_cursor_source_feed"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    feed_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    last_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
