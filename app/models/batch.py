from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.services.batch_dates import BatchDateString


class Batch(TimestampMixin, Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)

    production_date: Mapped[str] = mapped_column(BatchDateString(), nullable=False)
    note: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    disabled_reason: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    product = relationship("Product", back_populates="batches")
    anti_codes = relationship("AntiCode", back_populates="batch", cascade="all, delete-orphan")
