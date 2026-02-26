from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AntiCode, ScanEvent


@dataclass(frozen=True)
class TrackScanResult:
    deduped: bool
    scan_count: int


def _sha256_hex(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def track_scan(
    *,
    db: Session,
    anti_code: AntiCode,
    visitor_id: str,
    ip: str,
    user_agent: str,
    dedupe_seconds: int = 60,
    now: datetime | None = None,
) -> TrackScanResult:
    if now is None:
        now = datetime.now(timezone.utc)

    cutoff = now - timedelta(seconds=dedupe_seconds)
    recent_event_id = db.execute(
        select(ScanEvent.id)
        .where(
            ScanEvent.anti_code_id == anti_code.id,
            ScanEvent.visitor_id == visitor_id,
            ScanEvent.scanned_at >= cutoff,
        )
        .limit(1)
    ).scalar_one_or_none()

    if recent_event_id is not None:
        return TrackScanResult(deduped=True, scan_count=anti_code.scan_count)

    db.add(
        ScanEvent(
            anti_code_id=anti_code.id,
            scanned_at=now,
            visitor_id=visitor_id,
            ip_hash=_sha256_hex(ip),
            ua_hash=_sha256_hex(user_agent),
        )
    )

    anti_code.scan_count += 1
    if anti_code.first_scanned_at is None:
        anti_code.first_scanned_at = now
    anti_code.last_scanned_at = now

    db.add(anti_code)
    db.commit()
    db.refresh(anti_code)

    return TrackScanResult(deduped=False, scan_count=anti_code.scan_count)

