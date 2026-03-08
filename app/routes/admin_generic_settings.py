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


def _generic_genuine_text(text_genuine: str) -> str:
    cleaned = text_genuine.replace("防伪码", "").strip()
    return cleaned or _DEFAULT_GENERIC_MESSAGE


def _load_product_generic_settings(
    db: Session, *, product_id: int, default_message: str, default_show_product_name: bool, default_show_batch_date: bool
) -> dict[str, object]:
    settings = {
        "show_product_name": default_show_product_name,
        "show_batch_date": default_show_batch_date,
        "generic_message": default_message,
    }
    key = _generic_settings_storage_key(product_id)
    row = db.execute(select(PageContent).where(PageContent.key == key)).scalar_one_or_none()
    if row is None or not isinstance(row.content_json, dict):
        return settings

    payload = row.content_json
    if "show_product_name" in payload:
        settings["show_product_name"] = bool(payload.get("show_product_name"))
    if "show_batch_date" in payload:
        settings["show_batch_date"] = bool(payload.get("show_batch_date"))
    msg = str(payload.get("generic_message", "")).strip()
    if msg:
        settings["generic_message"] = msg
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
    settings = _load_product_generic_settings(
        db,
        product_id=product_id,
        default_message=default_message,
        default_show_product_name=default_show_product_name,
        default_show_batch_date=default_show_batch_date,
    )

    return templates.TemplateResponse(
        request,
        "admin/generic_settings_edit.html",
        {
            "product": product,
            "active_tab": "generic_settings",
            "show_product_name": bool(settings["show_product_name"]),
            "show_batch_date": bool(settings["show_batch_date"]),
            "generic_message": str(settings["generic_message"]),
        },
    )


@router.post("/products/{product_id}/generic-settings")
def product_generic_settings_submit(
    request: Request,
    product_id: int,
    show_product_name: str | None = Form(None),
    show_batch_date: str | None = Form(None),
    generic_message: str = Form(""),
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
    payload = {
        "show_product_name": show_product_name is not None,
        "show_batch_date": show_batch_date is not None,
        "generic_message": generic_message.strip() or default_message,
    }

    key = _generic_settings_storage_key(product_id)
    row = db.execute(select(PageContent).where(PageContent.key == key)).scalar_one_or_none()
    if row is None:
        row = PageContent(key=key, content_json=payload)
    else:
        row.content_json = payload
    db.add(row)
    db.commit()

    return RedirectResponse(
        url=f"/admin/products/{product_id}/generic-settings",
        status_code=HTTP_303_SEE_OTHER,
    )
