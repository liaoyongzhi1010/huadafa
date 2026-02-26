from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_db
from app.models import AntiCode, Batch, ScanEvent

router = APIRouter(prefix="/admin", tags=["admin"])

from app.web import templates


@router.get("")
@router.get("/")
def admin_index(request: Request, db: Session = Depends(get_db)):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)

    tz = ZoneInfo("Asia/Shanghai")
    now_utc = datetime.now(timezone.utc)
    today_start_local = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = today_start_local.astimezone(timezone.utc)
    last7_start_utc = now_utc - timedelta(days=7)

    today_scans = db.execute(
        select(func.count()).select_from(ScanEvent).where(ScanEvent.scanned_at >= today_start_utc)
    ).scalar_one()
    last7_scans = db.execute(
        select(func.count()).select_from(ScanEvent).where(ScanEvent.scanned_at >= last7_start_utc)
    ).scalar_one()

    total_codes = db.execute(select(func.count()).select_from(AntiCode)).scalar_one()
    total_batches = db.execute(select(func.count()).select_from(Batch)).scalar_one()

    top_codes = (
        db.execute(
            select(AntiCode.code, AntiCode.scan_count)
            .where(AntiCode.scan_count > 0)
            .order_by(AntiCode.scan_count.desc(), AntiCode.id.desc())
            .limit(5)
        )
        .all()
    )

    return templates.TemplateResponse(
        request,
        "admin/index.html",
        {
            "stats": {
                "today_scans": int(today_scans),
                "last7_scans": int(last7_scans),
                "total_codes": int(total_codes),
                "total_batches": int(total_batches),
            },
            "top_codes": [{"code": code, "scan_count": int(count)} for code, count in top_codes],
        },
    )


@router.get("/help")
def admin_help(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "admin/help.html", {})
