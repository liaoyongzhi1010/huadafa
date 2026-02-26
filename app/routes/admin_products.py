from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_db
from app.models import Product

router = APIRouter(prefix="/admin", tags=["admin"])

templates = Jinja2Templates(directory="app/templates")


def _require_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return None


@router.get("/products")
def products_list(request: Request, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    products = db.execute(select(Product).order_by(desc(Product.id))).scalars().all()
    return templates.TemplateResponse(request, "admin/products_list.html", {"products": products})


@router.get("/products/new")
def product_new_page(request: Request):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    return templates.TemplateResponse(request, "admin/product_new.html", {})


@router.post("/products/new")
def product_new_submit(
    request: Request,
    name: str = Form(...),
    detail_text: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = Product(name=name.strip(), detail_text=detail_text, detail_images=[])
    db.add(product)
    db.commit()
    return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

