from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AntiCode(TimestampMixin, Base):
    __tablename__ = "anti_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True, index=True)

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    disabled_reason: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    scan_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    product = relationship("Product", back_populates="anti_codes")
    batch = relationship("Batch", back_populates="anti_codes")
    scan_events = relationship("ScanEvent", back_populates="anti_code", cascade="all, delete-orphan")

