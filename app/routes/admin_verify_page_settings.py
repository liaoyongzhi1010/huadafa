from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_db
from app.models import AntiCode, Batch, PageContent, Product
from app.web import templates

router = APIRouter(prefix="/admin", tags=["admin"])

_DEFAULT_VERIFY_PAGE_SETTINGS: dict[str, str] = {
    "brand_mark": "爱酷",
    "brand_name": "中国爱酷防伪中心",
    "brand_sub": "AIKU CHINA VERIFICATION CENTER",
}


def _require_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return None


def _load_product_or_none(db: Session, *, product_id: int) -> Product | None:
    return db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()


def _verify_page_settings_storage_key(product_id: int) -> str:
    return f"product:{product_id}:verify_page_settings"


def _load_verify_page_settings(db: Session, *, product_id: int) -> dict[str, str]:
    settings = dict(_DEFAULT_VERIFY_PAGE_SETTINGS)
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


def _load_preview_code_for_product(db: Session, *, product_id: int) -> str:
    code = db.execute(
        select(AntiCode.code)
        .join(Batch, Batch.id == AntiCode.batch_id)
        .where(
            AntiCode.product_id == product_id,
            AntiCode.status == "active",
            Batch.status == "active",
        )
        .order_by(func.random())
        .limit(1)
    ).scalar_one_or_none()
    return str(code or "").strip()


@router.get("/products/{product_id}/verify-page-settings")
def verify_page_settings_page(request: Request, product_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = _load_product_or_none(db, product_id=product_id)
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    settings = _load_verify_page_settings(db, product_id=product_id)
    preview_code = _load_preview_code_for_product(db, product_id=product_id)
    preview_url = f"/verify?code={preview_code}&preview=1" if preview_code else ""
    return templates.TemplateResponse(
        request,
        "admin/verify_page_settings_edit.html",
        {
            "product": product,
            "active_tab": "verify_page_settings",
            "brand_mark": settings["brand_mark"],
            "brand_name": settings["brand_name"],
            "brand_sub": settings["brand_sub"],
            "preview_url": preview_url,
        },
    )


@router.post("/products/{product_id}/verify-page-settings")
def verify_page_settings_submit(
    request: Request,
    product_id: int,
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

    payload = {
        "brand_mark": brand_mark.strip() or _DEFAULT_VERIFY_PAGE_SETTINGS["brand_mark"],
        "brand_name": brand_name.strip() or _DEFAULT_VERIFY_PAGE_SETTINGS["brand_name"],
        "brand_sub": brand_sub.strip() or _DEFAULT_VERIFY_PAGE_SETTINGS["brand_sub"],
    }

    key = _verify_page_settings_storage_key(product_id)
    row = db.execute(select(PageContent).where(PageContent.key == key)).scalar_one_or_none()
    if row is None:
        row = PageContent(key=key, content_json=payload)
    else:
        existing = row.content_json if isinstance(row.content_json, dict) else {}
        merged = dict(existing)
        merged.update(payload)
        row.content_json = merged
    db.add(row)
    db.commit()

    return RedirectResponse(url=f"/admin/products/{product_id}/verify-page-settings", status_code=HTTP_303_SEE_OTHER)
