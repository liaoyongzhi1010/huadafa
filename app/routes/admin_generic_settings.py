from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_db
from app.models import PageContent, Product, VerifyConfig
from app.web import templates

router = APIRouter(prefix="/admin", tags=["admin"])


_DEFAULT_GENERIC_MESSAGE = "官方正品"
_DEFAULT_BRAND_SETTINGS: dict[str, str] = {
    "brand_mark": "爱酷",
    "brand_name": "中国爱酷防伪中心",
    "brand_sub": "AIKU CHINA VERIFICATION CENTER",
}
_DEFAULT_GENERIC_VISIBILITY: dict[str, bool] = {
    "show_product_name": True,
    "show_batch_date": True,
    "show_recommendations": True,
    "show_product_info": True,
    "show_brand_traceability": True,
    "show_about_us": True,
}


def _require_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return None


def _load_product_or_none(db: Session, *, product_id: int) -> Product | None:
    return db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()


def _load_verify_config_or_none(db: Session) -> VerifyConfig | None:
    return db.execute(select(VerifyConfig).order_by(desc(VerifyConfig.id))).scalar_one_or_none()


def _generic_settings_storage_key(product_id: int) -> str:
    return f"product:{product_id}:generic_settings"


def _verify_page_settings_storage_key(product_id: int) -> str:
    return f"product:{product_id}:verify_page_settings"


def _load_verify_page_brand_defaults(db: Session, *, product_id: int) -> dict[str, str]:
    settings = dict(_DEFAULT_BRAND_SETTINGS)
    row = db.execute(select(PageContent).where(PageContent.key == _verify_page_settings_storage_key(product_id))).scalar_one_or_none()
    if row is None or not isinstance(row.content_json, dict):
        return settings
    payload = row.content_json
    for key in ("brand_mark", "brand_name", "brand_sub"):
        value = str(payload.get(key, "")).strip()
        if value:
            settings[key] = value
    return settings


def _generic_genuine_text(text_genuine: str) -> str:
    cleaned = text_genuine.replace("防伪码", "").strip()
    return cleaned or _DEFAULT_GENERIC_MESSAGE


def _load_product_generic_settings(
    db: Session,
    *,
    product_id: int,
    default_message: str,
    default_show_product_name: bool,
    default_show_batch_date: bool,
    default_brand_settings: dict[str, str],
) -> dict[str, object]:
    settings = {
        **_DEFAULT_GENERIC_VISIBILITY,
        "show_product_name": default_show_product_name,
        "show_batch_date": default_show_batch_date,
        "generic_message": default_message,
        "brand_mark": default_brand_settings["brand_mark"],
        "brand_name": default_brand_settings["brand_name"],
        "brand_sub": default_brand_settings["brand_sub"],
    }
    key = _generic_settings_storage_key(product_id)
    row = db.execute(select(PageContent).where(PageContent.key == key)).scalar_one_or_none()
    if row is None or not isinstance(row.content_json, dict):
        return settings

    payload = row.content_json
    for key in _DEFAULT_GENERIC_VISIBILITY:
        if key in payload:
            settings[key] = bool(payload.get(key))
    msg = str(payload.get("generic_message", "")).strip()
    if msg:
        settings["generic_message"] = msg
    for key in ("brand_mark", "brand_name", "brand_sub"):
        value = str(payload.get(key, "")).strip()
        if value:
            settings[key] = value
    return settings


@router.get("/products/{product_id}/generic-settings")
def product_generic_settings_page(request: Request, product_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = _load_product_or_none(db, product_id=product_id)
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    cfg = _load_verify_config_or_none(db)
    default_message = _generic_genuine_text(cfg.text_genuine if cfg is not None else _DEFAULT_GENERIC_MESSAGE)
    default_show_product_name = cfg.show_product_name if cfg is not None else True
    default_show_batch_date = cfg.show_batch_date if cfg is not None else True
    default_brand_settings = _load_verify_page_brand_defaults(db, product_id=product_id)
    settings = _load_product_generic_settings(
        db,
        product_id=product_id,
        default_message=default_message,
        default_show_product_name=default_show_product_name,
        default_show_batch_date=default_show_batch_date,
        default_brand_settings=default_brand_settings,
    )

    return templates.TemplateResponse(
        request,
        "admin/generic_settings_edit.html",
        {
            "product": product,
            "active_tab": "generic_settings",
            "hide_product_name": not bool(settings["show_product_name"]),
            "hide_batch_date": not bool(settings["show_batch_date"]),
            "hide_recommendations": not bool(settings["show_recommendations"]),
            "hide_product_info": not bool(settings["show_product_info"]),
            "hide_brand_traceability": not bool(settings["show_brand_traceability"]),
            "hide_about_us": not bool(settings["show_about_us"]),
            "generic_message": str(settings["generic_message"]),
            "brand_mark": str(settings["brand_mark"]),
            "brand_name": str(settings["brand_name"]),
            "brand_sub": str(settings["brand_sub"]),
        },
    )


@router.post("/products/{product_id}/generic-settings")
def product_generic_settings_submit(
    request: Request,
    product_id: int,
    visibility_form: str | None = Form(None),
    hide_product_name: str | None = Form(None),
    hide_batch_date: str | None = Form(None),
    hide_recommendations: str | None = Form(None),
    hide_product_info: str | None = Form(None),
    hide_brand_traceability: str | None = Form(None),
    hide_about_us: str | None = Form(None),
    generic_message: str = Form(""),
    brand_mark: str = Form(""),
    brand_name: str = Form(""),
    brand_sub: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = _load_product_or_none(db, product_id=product_id)
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    cfg = _load_verify_config_or_none(db)
    default_message = _generic_genuine_text(cfg.text_genuine if cfg is not None else _DEFAULT_GENERIC_MESSAGE)
    default_brand_settings = _load_verify_page_brand_defaults(db, product_id=product_id)
    key = _generic_settings_storage_key(product_id)
    row = db.execute(select(PageContent).where(PageContent.key == key)).scalar_one_or_none()
    existing = row.content_json if row is not None and isinstance(row.content_json, dict) else {}
    default_show_product_name = cfg.show_product_name if cfg is not None else True
    default_show_batch_date = cfg.show_batch_date if cfg is not None else True
    preserved_visibility = {
        "show_product_name": bool(existing.get("show_product_name", default_show_product_name)),
        "show_batch_date": bool(existing.get("show_batch_date", default_show_batch_date)),
        "show_recommendations": bool(existing.get("show_recommendations", _DEFAULT_GENERIC_VISIBILITY["show_recommendations"])),
        "show_product_info": bool(existing.get("show_product_info", _DEFAULT_GENERIC_VISIBILITY["show_product_info"])),
        "show_brand_traceability": bool(
            existing.get("show_brand_traceability", _DEFAULT_GENERIC_VISIBILITY["show_brand_traceability"])
        ),
        "show_about_us": bool(existing.get("show_about_us", _DEFAULT_GENERIC_VISIBILITY["show_about_us"])),
    }

    if visibility_form is not None or any(
        value is not None
        for value in (
            hide_product_name,
            hide_batch_date,
            hide_recommendations,
            hide_product_info,
            hide_brand_traceability,
            hide_about_us,
        )
    ):
        preserved_visibility = {
            "show_product_name": hide_product_name is None,
            "show_batch_date": hide_batch_date is None,
            "show_recommendations": hide_recommendations is None,
            "show_product_info": hide_product_info is None,
            "show_brand_traceability": hide_brand_traceability is None,
            "show_about_us": hide_about_us is None,
        }

    payload: dict[str, object] = {
        **preserved_visibility,
        "generic_message": generic_message.strip() or default_message,
        "brand_mark": (
            brand_mark.strip()
            or str(existing.get("brand_mark", "")).strip()
            or default_brand_settings["brand_mark"]
        ),
        "brand_name": (
            brand_name.strip()
            or str(existing.get("brand_name", "")).strip()
            or default_brand_settings["brand_name"]
        ),
        "brand_sub": (
            brand_sub.strip()
            or str(existing.get("brand_sub", "")).strip()
            or default_brand_settings["brand_sub"]
        ),
    }

    if row is None:
        row = PageContent(key=key, content_json=payload)
    else:
        merged = dict(existing)
        merged.update(payload)
        row.content_json = merged
    db.add(row)
    db.commit()

    return RedirectResponse(
        url=f"/admin/products/{product_id}/generic-settings",
        status_code=HTTP_303_SEE_OTHER,
    )
