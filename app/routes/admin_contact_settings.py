from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_db
from app.models import Product, VerifyConfig
from app.web import templates

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return None


def _load_product_or_none(db: Session, *, product_id: int) -> Product | None:
    return db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()


def _get_or_create_config(db: Session) -> VerifyConfig:
    cfg = db.execute(select(VerifyConfig).order_by(desc(VerifyConfig.id))).scalar_one_or_none()
    if cfg is not None:
        return cfg
    cfg = VerifyConfig()
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


@router.get("/products/{product_id}/contact-settings")
def product_contact_settings_page(request: Request, product_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = _load_product_or_none(db, product_id=product_id)
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    cfg = _get_or_create_config(db)
    return templates.TemplateResponse(
        request,
        "admin/contact_settings_edit.html",
        {
            "product": product,
            "active_tab": "contact_settings",
            "contact_us_url": cfg.contact_us_url,
        },
    )


@router.post("/products/{product_id}/contact-settings")
def product_contact_settings_submit(
    request: Request,
    product_id: int,
    contact_us_url: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = _load_product_or_none(db, product_id=product_id)
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    cfg = _get_or_create_config(db)
    cfg.contact_us_url = contact_us_url.strip()
    db.add(cfg)
    db.commit()

    return RedirectResponse(url=f"/admin/products/{product_id}/contact-settings", status_code=HTTP_303_SEE_OTHER)
