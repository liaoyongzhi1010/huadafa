from __future__ import annotations

import re

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    AntiCode,
    PageContent,
    Recommendation,
    ScanEvent,
    VerifyConfig,
)
from app.services.track_scan import track_scan

router = APIRouter(prefix="/api/public", tags=["public"])

_CODE_RE = re.compile(r"^\d{16}$")

_DEFAULT_CONFIG: dict[str, object] = {
    "show_code": True,
    "show_product_name": True,
    "show_batch_date": True,
    "warning_threshold": 5,
    "recent_events_limit": 5,
    "contact_us_url": "",
    "text_genuine": "官方正品防伪码",
    "text_not_found": "未查询到该防伪码",
    "text_warning": "此防伪码已被多次验证，请您留意！",
}


def _content_keys_for_product(product_id: int) -> dict[str, str]:
    return {
        "brand_traceability": f"product:{product_id}:brand_traceability",
        "about_us": f"product:{product_id}:about_us",
    }


def _load_page_content_for_product(db: Session, product_id: int) -> dict[str, object]:
    keys = _content_keys_for_product(product_id)
    rows = (
        db.execute(
            select(PageContent).where(
                PageContent.key.in_(
                    [
                        keys["brand_traceability"],
                        keys["about_us"],
                        "brand_traceability",
                        "about_us",
                    ]
                )
            )
        )
        .scalars()
        .all()
    )
    content_map: dict[str, object] = {c.key: c.content_json for c in rows}
    return {
        "brand_traceability": content_map.get(
            keys["brand_traceability"],
            content_map.get("brand_traceability", {}),
        ),
        "about_us": content_map.get(
            keys["about_us"],
            content_map.get("about_us", {}),
        ),
    }


def _load_verify_config(db: Session) -> dict[str, object]:
    cfg = db.execute(select(VerifyConfig).order_by(desc(VerifyConfig.id))).scalar_one_or_none()
    if cfg is None:
        return dict(_DEFAULT_CONFIG)
    return {
        "show_code": cfg.show_code,
        "show_product_name": cfg.show_product_name,
        "show_batch_date": cfg.show_batch_date,
        "warning_threshold": cfg.warning_threshold,
        "recent_events_limit": cfg.recent_events_limit,
        "contact_us_url": cfg.contact_us_url,
        "text_genuine": cfg.text_genuine,
        "text_not_found": cfg.text_not_found,
        "text_warning": cfg.text_warning,
    }


@router.get("/verify")
def verify(code: str, db: Session = Depends(get_db)):
    if not _CODE_RE.match(code):
        raise HTTPException(status_code=422, detail="invalid_code")

    cfg = _load_verify_config(db)

    anti_code = db.execute(select(AntiCode).where(AntiCode.code == code)).scalar_one_or_none()
    if anti_code is None:
        return JSONResponse(
            status_code=404,
            content={"status": "not_found", "message": cfg["text_not_found"]},
        )

    if anti_code.status != "active":
        return JSONResponse(
            status_code=410,
            content={"status": "disabled", "message": "code_disabled"},
        )

    if anti_code.batch is not None and anti_code.batch.status != "active":
        return JSONResponse(
            status_code=410,
            content={"status": "disabled", "message": "batch_disabled"},
        )

    recent_limit = int(cfg["recent_events_limit"])
    recent_events = (
        db.execute(
            select(ScanEvent.scanned_at)
            .where(ScanEvent.anti_code_id == anti_code.id)
            .order_by(ScanEvent.scanned_at.desc())
            .limit(recent_limit)
        )
        .scalars()
        .all()
    )

    loaded_page_content = _load_page_content_for_product(db, anti_code.product_id)

    product_id = anti_code.product_id
    recs = (
        db.execute(
            select(Recommendation)
            .where(
                Recommendation.image_url != "",
                Recommendation.product_id == product_id,
            )
            .order_by(Recommendation.sort_order.asc(), Recommendation.id.asc())
        )
        .scalars()
        .all()
    )

    product = anti_code.product
    return {
        "status": "genuine",
        "scan_count": anti_code.scan_count,
        "show_code": bool(cfg["show_code"]),
        "warning_threshold": int(cfg["warning_threshold"]),
        "contact_us_url": str(cfg["contact_us_url"]),
        "product": {
            "id": product.id,
            "name": product.name,
            "detail_text": product.detail_text,
            "detail_images": product.detail_images,
        },
        "page_content": {
            "brand_traceability": loaded_page_content.get("brand_traceability", {}),
            "about_us": loaded_page_content.get("about_us", {}),
        },
        "recommendations": [{"image_url": r.image_url, "target_url": r.target_url} for r in recs],
        "recent_events": recent_events,
    }


class TrackVerifyRequest(BaseModel):
    code: str


@router.post("/verify/track")
def track_verify(payload: TrackVerifyRequest, request: Request, db: Session = Depends(get_db)):
    code = payload.code
    if not _CODE_RE.match(code):
        raise HTTPException(status_code=422, detail="invalid_code")

    anti_code = db.execute(select(AntiCode).where(AntiCode.code == code)).scalar_one_or_none()
    if anti_code is None:
        cfg = _load_verify_config(db)
        return JSONResponse(
            status_code=404,
            content={"status": "not_found", "message": cfg["text_not_found"]},
        )

    if anti_code.status != "active" or (anti_code.batch is not None and anti_code.batch.status != "active"):
        return JSONResponse(status_code=410, content={"status": "disabled"})

    visitor_id = request.cookies.get("visitor_id")
    set_cookie = False
    if not visitor_id:
        visitor_id = uuid.uuid4().hex
        set_cookie = True

    client_host = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")

    result = track_scan(
        db=db,
        anti_code=anti_code,
        visitor_id=visitor_id,
        ip=client_host,
        user_agent=user_agent,
        dedupe_seconds=3,
    )

    resp = JSONResponse(content={"deduped": result.deduped, "scan_count": result.scan_count})
    if set_cookie:
        resp.set_cookie(
            "visitor_id",
            visitor_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="lax",
        )
    return resp
