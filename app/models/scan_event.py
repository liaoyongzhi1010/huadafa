from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class ScanEvent(Base):
    __tablename__ = "scan_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    anti_code_id: Mapped[int] = mapped_column(ForeignKey("anti_codes.id"), nullable=False, index=True)

    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    visitor_id: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    ip_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    ua_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)

    anti_code = relationship("AntiCode", back_populates="scan_events")

