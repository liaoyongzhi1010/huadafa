from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)

    detail_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    detail_images: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    batches = relationship("Batch", back_populates="product", cascade="all, delete-orphan")
    anti_codes = relationship("AntiCode", back_populates="product", cascade="all, delete-orphan")
    recommendations = relationship(
        "Recommendation",
        back_populates="product",
        cascade="all, delete-orphan",
    )

