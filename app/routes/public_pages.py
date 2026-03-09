from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AntiCode, Batch, PageContent, Product, Recommendation, ScanEvent, VerifyConfig
from app.services.track_scan import track_scan
from app.web import templates

router = APIRouter(tags=["public-pages"])

_CODE_RE = re.compile(r"^\d{16}$")
_TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")

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
_DEFAULT_VERIFY_SECTIONS: list[dict[str, str]] = [
    {"id": "product_info", "title": "产品信息"},
    {"id": "brand_traceability", "title": "品牌溯源"},
    {"id": "about_us", "title": "关于我们"},
]
_DEFAULT_BRAND_SETTINGS: dict[str, str] = {
    "brand_mark": "爱酷",
    "brand_name": "中国爱酷防伪中心",
    "brand_sub": "AIKU CHINA VERIFICATION CENTER",
}
_SECTION_ID_RE = re.compile(r"^[a-z0-9_]{1,64}$")


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


def _normalize_blocks(payload: object) -> list[dict[str, str]]:
    if not isinstance(payload, dict):
        return []

    blocks_raw = payload.get("blocks")
    if isinstance(blocks_raw, list):
        blocks: list[dict[str, str]] = []
        for item in blocks_raw:
            if not isinstance(item, dict):
                continue
            t = str(item.get("type", "")).strip().lower()
            link = str(item.get("link", "")).strip()
            if t == "text":
                text = str(item.get("text", "")).strip()
                if text:
                    block: dict[str, str] = {"type": "text", "text": text}
                    if link:
                        block["link"] = link
                    blocks.append(block)
            elif t == "image":
                url = str(item.get("url", "")).strip()
                if url:
                    block = {"type": "image", "url": url}
                    if link:
                        block["link"] = link
                    blocks.append(block)
        if blocks:
            return blocks

    legacy_text = str(payload.get("text", "")).strip()
    if legacy_text:
        return [{"type": "text", "text": legacy_text}]
    return []


def _verify_sections_storage_key(product_id: int) -> str:
    return f"product:{product_id}:verify_sections"


def _verify_page_settings_storage_key(product_id: int) -> str:
    return f"product:{product_id}:verify_page_settings"


def _load_verify_page_branding_for_product(db: Session, *, product_id: int) -> dict[str, str]:
    settings = dict(_DEFAULT_BRAND_SETTINGS)
    row = db.execute(
        select(PageContent).where(PageContent.key == _verify_page_settings_storage_key(product_id))
    ).scalar_one_or_none()
    if row is None or not isinstance(row.content_json, dict):
        return settings

    payload = row.content_json
    for key in ("brand_mark", "brand_name", "brand_sub"):
        value = str(payload.get(key, "")).strip()
        if value:
            settings[key] = value
    return settings


def _section_content_key(*, product_id: int, section_id: str) -> str:
    if section_id in {"product_info", "brand_traceability", "about_us"}:
        return f"product:{product_id}:{section_id}"
    return f"product:{product_id}:section:{section_id}"


def _load_verify_sections(db: Session, *, product_id: int) -> list[dict[str, str]]:
    row = db.execute(
        select(PageContent).where(PageContent.key == _verify_sections_storage_key(product_id))
    ).scalar_one_or_none()
    if row is None or not isinstance(row.content_json, dict):
        return [{"id": s["id"], "title": s["title"]} for s in _DEFAULT_VERIFY_SECTIONS]

    raw_sections = row.content_json.get("sections")
    if not isinstance(raw_sections, list):
        return [{"id": s["id"], "title": s["title"]} for s in _DEFAULT_VERIFY_SECTIONS]

    sections: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw_sections:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("id", "")).strip().lower()
        title = str(item.get("title", "")).strip()
        if not sid or not title or not _SECTION_ID_RE.match(sid):
            continue
        if sid in seen:
            continue
        seen.add(sid)
        sections.append({"id": sid, "title": title})
    if not sections:
        return [{"id": s["id"], "title": s["title"]} for s in _DEFAULT_VERIFY_SECTIONS]
    return sections


def _legacy_product_info_blocks(product: Product) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    text = str(product.detail_text or "").strip()
    if text:
        blocks.append({"type": "text", "text": text})
    for img in list(product.detail_images or []):
        if not isinstance(img, dict):
            continue
        url = str(img.get("url", "")).strip()
        if url:
            blocks.append({"type": "image", "url": url})
    return blocks


def _load_verify_sections_payload(
    db: Session,
    *,
    product: Product,
    page_content: dict[str, object],
) -> list[dict[str, object]]:
    sections = _load_verify_sections(db, product_id=product.id)
    payload: list[dict[str, object]] = []

    for section in sections:
        sid = section["id"]
        title = section["title"]

        blocks: list[dict[str, str]] = []
        if sid in {"brand_traceability", "about_us"}:
            blocks = _normalize_blocks(page_content.get(sid, {}))
        else:
            row = db.execute(
                select(PageContent).where(PageContent.key == _section_content_key(product_id=product.id, section_id=sid))
            ).scalar_one_or_none()
            content_json = row.content_json if row is not None and isinstance(row.content_json, dict) else {}
            blocks = _normalize_blocks(content_json)

        if sid == "product_info" and not blocks:
            blocks = _legacy_product_info_blocks(product)

        payload.append(
            {
                "id": sid,
                "title": title,
                "blocks": blocks,
            }
        )

    return payload


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


def _format_dt_shanghai(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_TZ_SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")


def _generic_genuine_text(text_genuine: str) -> str:
    cleaned = text_genuine.replace("防伪码", "").strip()
    return cleaned or "官方正品"


def _generic_settings_storage_key(product_id: int) -> str:
    return f"product:{product_id}:generic_settings"


def _load_generic_settings_for_product(db: Session, *, product_id: int, cfg: dict[str, object]) -> dict[str, object]:
    default_branding = _load_verify_page_branding_for_product(db, product_id=product_id)
    settings = {
        "generic_message": _generic_genuine_text(str(cfg["text_genuine"])),
        "show_product_name": bool(cfg["show_product_name"]),
        "show_batch_date": bool(cfg["show_batch_date"]),
        "brand_mark": default_branding["brand_mark"],
        "brand_name": default_branding["brand_name"],
        "brand_sub": default_branding["brand_sub"],
    }
    row = db.execute(
        select(PageContent).where(PageContent.key == _generic_settings_storage_key(product_id))
    ).scalar_one_or_none()
    if row is None or not isinstance(row.content_json, dict):
        return settings

    payload = row.content_json
    if "show_product_name" in payload:
        settings["show_product_name"] = bool(payload.get("show_product_name"))
    if "show_batch_date" in payload:
        settings["show_batch_date"] = bool(payload.get("show_batch_date"))
    message = str(payload.get("generic_message", "")).strip()
    if message:
        settings["generic_message"] = message
    for key in ("brand_mark", "brand_name", "brand_sub"):
        value = str(payload.get(key, "")).strip()
        if value:
            settings[key] = value
    return settings


def _is_preview_mode(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


@router.get("/verify")
def verify_page(
    request: Request,
    code: str,
    preview: str | None = None,
    full: str | None = None,
    db: Session = Depends(get_db),
):
    cfg = _load_verify_config(db)
    preview_mode = _is_preview_mode(preview)
    full_mode = _is_preview_mode(full)

    status = "not_found"
    message = str(cfg["text_not_found"])
    scan_count = 0
    warning_threshold = int(cfg["warning_threshold"])
    show_code = bool(cfg["show_code"])
    warning_active = False
    recent_events: list[object] = []
    recommendations: list[dict[str, str]] = []
    page_content: dict[str, object] = {"brand_traceability": {}, "about_us": {}}
    verify_sections: list[dict[str, object]] = []
    product: dict[str, object] | None = None
    production_date = ""
    query_status_text = ""
    brand_settings = dict(_DEFAULT_BRAND_SETTINGS)

    visitor_id = request.cookies.get("visitor_id")
    set_cookie = False
    if not visitor_id:
        visitor_id = uuid.uuid4().hex
        set_cookie = True

    if _CODE_RE.match(code):
        anti_code = db.execute(select(AntiCode).where(AntiCode.code == code)).scalar_one_or_none()
        if anti_code is not None:
            brand_settings = _load_verify_page_branding_for_product(db, product_id=anti_code.product_id)
        if anti_code is not None and anti_code.status == "active" and (
            anti_code.batch is None or anti_code.batch.status == "active"
        ):
            status = "genuine"
            if preview_mode:
                scan_count = anti_code.scan_count
            else:
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

            page_content = _load_page_content_for_product(db, anti_code.product_id)

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
            recommendations = [{"image_url": r.image_url, "target_url": r.target_url} for r in recs]

            p = anti_code.product
            message = p.name.strip() or str(cfg["text_genuine"])
            verify_sections = _load_verify_sections_payload(db, product=p, page_content=page_content)
            product = {
                "id": p.id,
                "name": p.name,
                "detail_text": p.detail_text,
                "detail_images": p.detail_images,
            }
            if anti_code.batch is not None:
                production_date = anti_code.batch.production_date
            query_status_text = "首次查询" if scan_count <= 1 else "已被查询过"
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
            "verify_sections": verify_sections,
            "production_date": production_date,
            "query_status_text": query_status_text,
            "preview_mode": preview_mode,
            "full_mode": full_mode,
            "brand_mark": brand_settings["brand_mark"],
            "brand_name": brand_settings["brand_name"],
            "brand_sub": brand_settings["brand_sub"],
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


@router.get("/verify/general")
def verify_general_page(request: Request, product_id: int, db: Session = Depends(get_db)):
    cfg = _load_verify_config(db)
    generic_settings = _load_generic_settings_for_product(db, product_id=product_id, cfg=cfg)
    product = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()

    if product is None:
        return templates.TemplateResponse(
            request,
            "verify_generic.html",
            {
                "message": "未查询到产品信息",
                "show_product_name": False,
                "show_batch_date": False,
                "product_name": "",
                "batch_date": "",
                "verify_sections": [],
                "recommendations": [],
                "contact_us_url": str(cfg["contact_us_url"]),
                "brand_mark": _DEFAULT_BRAND_SETTINGS["brand_mark"],
                "brand_name": _DEFAULT_BRAND_SETTINGS["brand_name"],
                "brand_sub": _DEFAULT_BRAND_SETTINGS["brand_sub"],
            },
        )

    batch = (
        db.execute(
            select(Batch)
            .where(Batch.product_id == product_id, Batch.status == "active")
            .order_by(desc(Batch.id))
        )
        .scalars()
        .first()
    )

    batch_date = ""
    if batch is not None:
        batch_date = batch.production_date
    elif product.created_at is not None:
        batch_date = product.created_at.date().isoformat()

    page_content = _load_page_content_for_product(db, product_id=product_id)
    verify_sections = _load_verify_sections_payload(db, product=product, page_content=page_content)

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
    recommendations = [{"image_url": r.image_url, "target_url": r.target_url} for r in recs]

    return templates.TemplateResponse(
        request,
        "verify_generic.html",
        {
            "message": str(generic_settings["generic_message"]),
            "show_product_name": bool(generic_settings["show_product_name"]),
            "show_batch_date": bool(generic_settings["show_batch_date"]),
            "product_name": product.name,
            "batch_date": batch_date,
            "verify_sections": verify_sections,
            "recommendations": recommendations,
            "contact_us_url": str(cfg["contact_us_url"]),
            "brand_mark": str(generic_settings["brand_mark"]),
            "brand_name": str(generic_settings["brand_name"]),
            "brand_sub": str(generic_settings["brand_sub"]),
        },
    )
