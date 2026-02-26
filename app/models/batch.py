from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Batch(TimestampMixin, Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)

    production_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    disabled_reason: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    product = relationship("Product", back_populates="batches")
    anti_codes = relationship("AntiCode", back_populates="batch", cascade="all, delete-orphan")

