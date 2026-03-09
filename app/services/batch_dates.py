from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from sqlalchemy.types import String, TypeDecorator

_YEAR_RE = re.compile(r"^\d{4}$")
_YEAR_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_FULL_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_BATCH_DATE_ERROR = "批次日期格式必须是 YYYY、YYYY-MM 或 YYYY-MM-DD。"


def batch_date_error_message() -> str:
    return _BATCH_DATE_ERROR


def normalize_batch_date(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise ValueError(_BATCH_DATE_ERROR)

    try:
        if _YEAR_RE.match(raw):
            datetime.strptime(raw, "%Y")
            return raw
        if _YEAR_MONTH_RE.match(raw):
            datetime.strptime(raw, "%Y-%m")
            return raw
        if _FULL_DATE_RE.match(raw):
            date.fromisoformat(raw)
            return raw
    except ValueError as exc:
        raise ValueError(_BATCH_DATE_ERROR) from exc

    raise ValueError(_BATCH_DATE_ERROR)


def coerce_batch_date(value: str | date) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return normalize_batch_date(value)
    raise TypeError("Batch date must be a string or date.")


class BatchDateString(TypeDecorator[str]):
    impl = String(10)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return coerce_batch_date(value)

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)
