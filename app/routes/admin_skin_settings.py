from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_db
from app.models import AntiCode, Batch, PageContent, Product
from app.services.page_skins import (
    DEFAULT_PAGE_SKIN_ID,
    list_page_skins,
    normalize_page_skin_id,
    skin_settings_storage_key,
)
from app.web import templates

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return None


def _load_product_or_none(db: Session, *, product_id: int) -> Product | None:
    return db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()


def _load_product_skin_id(db: Session, *, product_id: int) -> str:
    row = db.execute(select(PageContent).where(PageContent.key == skin_settings_storage_key(product_id))).scalar_one_or_none()
    if row is None or not isinstance(row.content_json, dict):
        return DEFAULT_PAGE_SKIN_ID
    return normalize_page_skin_id(row.content_json.get("skin_id"))


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


@router.get("/products/{product_id}/skin-settings")
def product_skin_settings_page(request: Request, product_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = _load_product_or_none(db, product_id=product_id)
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    current_skin_id = _load_product_skin_id(db, product_id=product_id)
    preview_code = _load_preview_code_for_product(db, product_id=product_id)
    verify_preview_base_url = f"/verify?code={preview_code}&preview=1" if preview_code else ""
    generic_preview_base_url = f"/verify/general?product_id={product_id}&preview=1"
    verify_preview_url = f"{verify_preview_base_url}&skin_id={current_skin_id}" if verify_preview_base_url else ""
    generic_preview_url = f"{generic_preview_base_url}&skin_id={current_skin_id}"

    return templates.TemplateResponse(
        request,
        "admin/skin_settings_edit.html",
        {
            "product": product,
            "active_tab": "skin_settings",
            "skins": list_page_skins(),
            "selected_skin_id": current_skin_id,
            "verify_preview_base_url": verify_preview_base_url,
            "verify_preview_url": verify_preview_url,
            "generic_preview_base_url": generic_preview_base_url,
            "generic_preview_url": generic_preview_url,
        },
    )


@router.post("/products/{product_id}/skin-settings")
def product_skin_settings_submit(
    request: Request,
    product_id: int,
    skin_id: str = Form(DEFAULT_PAGE_SKIN_ID),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = _load_product_or_none(db, product_id=product_id)
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    key = skin_settings_storage_key(product_id)
    payload = {"skin_id": normalize_page_skin_id(skin_id)}
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

    return RedirectResponse(url=f"/admin/products/{product_id}/skin-settings", status_code=HTTP_303_SEE_OTHER)
