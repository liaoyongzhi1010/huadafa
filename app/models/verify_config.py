from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from app.models.base import Base


class VerifyConfig(Base):
    __tablename__ = "verify_configs"

    id: Mapped[int] = mapped_column(primary_key=True)

    show_code: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    warning_threshold: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    recent_events_limit: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    contact_us_url: Mapped[str] = mapped_column(String(1024), default="", nullable=False)

    text_genuine: Mapped[str] = mapped_column(String(255), default="官方正品防伪码", nullable=False)
    text_not_found: Mapped[str] = mapped_column(String(255), default="未查询到该防伪码", nullable=False)
    text_warning: Mapped[str] = mapped_column(String(255), default="此防伪码已被多次验证，请您留意！", nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
