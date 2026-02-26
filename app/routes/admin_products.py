from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_db
from app.models import Product
from app.services.uploads import save_product_detail_image
from app.web import templates

router = APIRouter(prefix="/admin", tags=["admin"])


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


@router.get("/products/{product_id}/edit")
def product_edit_page(request: Request, product_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "admin/product_edit.html",
        {"product": product},
    )


@router.post("/products/{product_id}/edit")
def product_edit_submit(
    request: Request,
    product_id: int,
    name: str = Form(...),
    detail_text: str = Form(""),
    clear_images: str | None = Form(None),
    detail_images: list[UploadFile] = File(default_factory=list),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    product.name = name.strip()
    product.detail_text = detail_text

    if clear_images is not None:
        product.detail_images = []

    images = list(product.detail_images or [])
    for upload in detail_images:
        if not upload.filename:
            continue
        url = save_product_detail_image(product_id=product.id, upload=upload)
        images.append({"url": url})

    product.detail_images = images

    db.add(product)
    db.commit()

    return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)
