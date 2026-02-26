from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AntiCode, PageContent, Recommendation, ScanEvent, VerifyConfig
from app.services.track_scan import track_scan
from app.web import templates

router = APIRouter(tags=["public-pages"])

_CODE_RE = re.compile(r"^\d{16}$")
_TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")

_DEFAULT_CONFIG: dict[str, object] = {
    "show_code": True,
    "warning_threshold": 5,
    "recent_events_limit": 5,
    "contact_us_url": "",
    "text_genuine": "官方正品防伪码",
    "text_not_found": "未查询到该防伪码",
    "text_warning": "此防伪码已被多次验证，请您留意！",
}


def _load_verify_config(db: Session) -> dict[str, object]:
    cfg = db.execute(select(VerifyConfig).order_by(desc(VerifyConfig.id))).scalar_one_or_none()
    if cfg is None:
        return dict(_DEFAULT_CONFIG)
    return {
        "show_code": cfg.show_code,
        "warning_threshold": cfg.warning_threshold,
        "recent_events_limit": cfg.recent_events_limit,
        "contact_us_url": cfg.contact_us_url,
        "text_genuine": cfg.text_genuine,
        "text_not_found": cfg.text_not_found,
        "text_warning": cfg.text_warning,
    }


def _format_dt_shanghai(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_TZ_SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")


@router.get("/verify")
def verify_page(request: Request, code: str, db: Session = Depends(get_db)):
    cfg = _load_verify_config(db)

    status = "not_found"
    message = str(cfg["text_not_found"])
    scan_count = 0
    warning_threshold = int(cfg["warning_threshold"])
    show_code = bool(cfg["show_code"])
    warning_active = False
    recent_events: list[object] = []
    recommendations: list[dict[str, str]] = []
    page_content: dict[str, object] = {"brand_traceability": {}, "about_us": {}}
    product: dict[str, object] | None = None

    visitor_id = request.cookies.get("visitor_id")
    set_cookie = False
    if not visitor_id:
        visitor_id = uuid.uuid4().hex
        set_cookie = True

    if _CODE_RE.match(code):
        anti_code = db.execute(select(AntiCode).where(AntiCode.code == code)).scalar_one_or_none()
        if anti_code is not None and anti_code.status == "active" and (
            anti_code.batch is None or anti_code.batch.status == "active"
        ):
            status = "genuine"
            message = str(cfg["text_genuine"])
            client_host = request.client.host if request.client else ""
            user_agent = request.headers.get("user-agent", "")
            result = track_scan(
                db=db,
                anti_code=anti_code,
                visitor_id=str(visitor_id),
                ip=client_host,
                user_agent=user_agent,
                dedupe_seconds=3,
            )
            scan_count = result.scan_count
            warning_active = scan_count >= warning_threshold

            recent_limit = int(cfg["recent_events_limit"])
            recent_dt = (
                db.execute(
                    select(ScanEvent.scanned_at)
                    .where(ScanEvent.anti_code_id == anti_code.id)
                    .order_by(ScanEvent.scanned_at.desc())
                    .limit(recent_limit)
                )
                .scalars()
                .all()
            )
            recent_events = [_format_dt_shanghai(t) for t in recent_dt]

            contents = (
                db.execute(
                    select(PageContent).where(PageContent.key.in_(["brand_traceability", "about_us"]))
                )
                .scalars()
                .all()
            )
            content_map: dict[str, object] = {c.key: c.content_json for c in contents}
            page_content = {
                "brand_traceability": content_map.get("brand_traceability", {}),
                "about_us": content_map.get("about_us", {}),
            }

            product_id = anti_code.product_id
            recs = (
                db.execute(
                    select(Recommendation)
                    .where(
                        Recommendation.enabled.is_(True),
                        Recommendation.image_url != "",
                        or_(
                            Recommendation.product_id.is_(None),
                            Recommendation.product_id == product_id,
                        ),
                    )
                    .order_by(desc(Recommendation.sort_order), desc(Recommendation.id))
                )
                .scalars()
                .all()
            )
            recommendations = [{"image_url": r.image_url, "target_url": r.target_url} for r in recs]

            p = anti_code.product
            product = {
                "id": p.id,
                "name": p.name,
                "detail_text": p.detail_text,
                "detail_images": p.detail_images,
            }
        elif anti_code is not None:
            status = "disabled"
            message = "该防伪码已作废，请联系官方"
    else:
        status = "invalid"
        message = "防伪码格式错误"

    resp = templates.TemplateResponse(
        request,
        "verify.html",
        {
            "status": status,
            "message": message,
            "code": code,
            "show_code": show_code,
            "scan_count": scan_count,
            "warning_threshold": warning_threshold,
            "warning_active": warning_active,
            "text_warning": str(cfg["text_warning"]),
            "contact_us_url": str(cfg["contact_us_url"]),
            "recent_events": recent_events,
            "recommendations": recommendations,
            "product": product,
            "page_content": page_content,
        },
    )
    if set_cookie:
        resp.set_cookie(
            "visitor_id",
            str(visitor_id),
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="lax",
        )
    return resp
