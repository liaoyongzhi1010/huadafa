from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_db
from app.models import AntiCode, Batch, Product
from app.paths import UPLOADS_DIR
from app.services.uploads import save_product_detail_image
from app.web import templates

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return None


def _is_delete_confirmed(confirm_text: str) -> bool:
    t = (confirm_text or "").strip()
    return t == "删除" or t.upper() == "DELETE"


def _pick_random_active_code_for_product(db: Session, *, product_id: int) -> str | None:
    return db.execute(
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


@router.get("/products")
def products_list(request: Request, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    products = db.execute(select(Product).order_by(desc(Product.id))).scalars().all()
    return templates.TemplateResponse(request, "admin/products_list.html", {"products": products})


@router.get("/products/{product_id}/workspace")
def product_workspace(request: Request, product_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)
    return RedirectResponse(url=f"/admin/products/{product_id}/batches", status_code=HTTP_303_SEE_OTHER)


@router.get("/products/{product_id}/preview/verify")
def product_preview_verify(request: Request, product_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    code = _pick_random_active_code_for_product(db, product_id=product_id)
    if code is None:
        return RedirectResponse(
            url=f"/admin/products/{product_id}/batches/new?notice=preview_no_code",
            status_code=HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=f"/verify?code={code}&preview=1",
        status_code=HTTP_303_SEE_OTHER,
    )


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


@router.get("/products/{product_id}/delete")
def product_delete_confirm_page(request: Request, product_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    batch_count = db.execute(select(func.count(Batch.id)).where(Batch.product_id == product_id)).scalar_one()
    code_count = db.execute(select(func.count(AntiCode.id)).where(AntiCode.product_id == product_id)).scalar_one()

    return templates.TemplateResponse(
        request,
        "admin/product_delete_confirm.html",
        {
            "product": product,
            "batch_count": int(batch_count or 0),
            "code_count": int(code_count or 0),
            "error": "",
        },
    )


@router.post("/products/{product_id}/delete")
def product_delete_submit(
    request: Request,
    product_id: int,
    confirm_text: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    if not _is_delete_confirmed(confirm_text):
        batch_count = db.execute(select(func.count(Batch.id)).where(Batch.product_id == product_id)).scalar_one()
        code_count = db.execute(select(func.count(AntiCode.id)).where(AntiCode.product_id == product_id)).scalar_one()
        return templates.TemplateResponse(
            request,
            "admin/product_delete_confirm.html",
            {
                "product": product,
                "batch_count": int(batch_count or 0),
                "code_count": int(code_count or 0),
                "error": "请输入 DELETE（或 删除）以确认永久删除。",
            },
            status_code=200,
        )

    uploads_dir = UPLOADS_DIR / "products" / str(product_id)
    if uploads_dir.exists():
        shutil.rmtree(uploads_dir, ignore_errors=True)

    db.delete(product)
    db.commit()

    return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)
