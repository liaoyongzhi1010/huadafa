from __future__ import annotations

import secrets
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_db
from app.models import AntiCode, Batch, Product
from app.web import templates

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return None


def _generate_code() -> str:
    first = str(secrets.randbelow(9) + 1)
    rest = "".join(str(secrets.randbelow(10)) for _ in range(15))
    return first + rest


def _is_delete_confirmed(confirm_text: str) -> bool:
    t = (confirm_text or "").strip()
    return t == "删除" or t.upper() == "DELETE"


@router.post("/batches/{batch_id}/codes/generate")
def generate_codes_for_batch(
    request: Request,
    batch_id: int,
    quantity: str = Form(...),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    batch = db.execute(select(Batch).where(Batch.id == batch_id)).scalar_one_or_none()
    if batch is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    try:
        n = int(quantity)
    except ValueError:
        n = 0

    n = max(0, min(n, 10000))
    if n == 0:
        return RedirectResponse(
            url=f"/admin/products/{batch.product_id}/batches",
            status_code=HTTP_303_SEE_OTHER,
        )

    codes: set[str] = set()
    while len(codes) < n:
        codes.add(_generate_code())

    objects = [AntiCode(code=c, product_id=batch.product_id, batch_id=batch.id) for c in codes]
    db.add_all(objects)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Fallback: insert one by one, retry on collisions
        inserted = 0
        while inserted < n:
            candidate = _generate_code()
            db.add(AntiCode(code=candidate, product_id=batch.product_id, batch_id=batch.id))
            try:
                db.commit()
                inserted += 1
            except IntegrityError:
                db.rollback()

    return RedirectResponse(
        url=f"/admin/products/{batch.product_id}/batches",
        status_code=HTTP_303_SEE_OTHER,
    )


@router.get("/batches/{batch_id}")
def batch_detail(request: Request, batch_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    batch = db.execute(select(Batch).where(Batch.id == batch_id)).scalar_one_or_none()
    if batch is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    return RedirectResponse(
        url=f"/admin/products/{batch.product_id}/batches",
        status_code=HTTP_303_SEE_OTHER,
    )


@router.get("/products/{product_id}/batches")
def product_batches_list(request: Request, product_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    count_subq = (
        select(
            AntiCode.batch_id.label("batch_id"),
            func.count(AntiCode.id).label("code_count"),
        )
        .group_by(AntiCode.batch_id)
        .subquery()
    )

    rows = db.execute(
        select(Batch, func.coalesce(count_subq.c.code_count, 0))
        .outerjoin(count_subq, count_subq.c.batch_id == Batch.id)
        .where(Batch.product_id == product_id)
        .order_by(desc(Batch.id))
    ).all()

    batch_rows = [{"batch": b, "code_count": int(count)} for b, count in rows]
    return templates.TemplateResponse(
        request,
        "admin/batches_list.html",
        {"product": product, "batch_rows": batch_rows},
    )


@router.get("/products/{product_id}/batches/new")
def product_batch_new_page(request: Request, product_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "admin/batch_new.html",
        {"product": product, "today": date.today().isoformat(), "quantity": "100", "error": ""},
    )


@router.post("/products/{product_id}/batches/new")
def product_batch_new_submit(
    request: Request,
    product_id: int,
    production_date: str = Form(""),
    quantity: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    try:
        parsed_date = date.fromisoformat(production_date)
    except ValueError:
        parsed_date = date.today()

    try:
        n = int(quantity)
    except ValueError:
        n = 0
    n = max(0, min(n, 10000))
    if n <= 0:
        return templates.TemplateResponse(
            request,
            "admin/batch_new.html",
            {
                "product": product,
                "today": parsed_date.isoformat(),
                "quantity": quantity,
                "error": "数量必须为 1–10000。",
            },
            status_code=200,
        )

    batch = Batch(product_id=product_id, production_date=parsed_date, note=note)
    db.add(batch)
    db.commit()
    db.refresh(batch)

    codes: set[str] = set()
    while len(codes) < n:
        codes.add(_generate_code())

    objects = [AntiCode(code=c, product_id=product_id, batch_id=batch.id) for c in codes]
    db.add_all(objects)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        inserted = 0
        while inserted < n:
            candidate = _generate_code()
            db.add(AntiCode(code=candidate, product_id=product_id, batch_id=batch.id))
            try:
                db.commit()
                inserted += 1
            except IntegrityError:
                db.rollback()

    return RedirectResponse(
        url=f"/admin/products/{product_id}/batches",
        status_code=HTTP_303_SEE_OTHER,
    )


@router.get("/batches/{batch_id}/delete")
def batch_delete_confirm_page(request: Request, batch_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    batch = db.execute(select(Batch).where(Batch.id == batch_id)).scalar_one_or_none()
    if batch is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    code_count = db.execute(select(func.count(AntiCode.id)).where(AntiCode.batch_id == batch_id)).scalar_one()
    product = batch.product

    return templates.TemplateResponse(
        request,
        "admin/batch_delete_confirm.html",
        {
            "batch": batch,
            "product": product,
            "code_count": int(code_count or 0),
            "error": "",
        },
    )


@router.post("/batches/{batch_id}/delete")
def batch_delete_submit(
    request: Request,
    batch_id: int,
    confirm_text: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    batch = db.execute(select(Batch).where(Batch.id == batch_id)).scalar_one_or_none()
    if batch is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    product_id = batch.product_id

    if not _is_delete_confirmed(confirm_text):
        code_count = db.execute(select(func.count(AntiCode.id)).where(AntiCode.batch_id == batch_id)).scalar_one()
        product = batch.product
        return templates.TemplateResponse(
            request,
            "admin/batch_delete_confirm.html",
            {
                "batch": batch,
                "product": product,
                "code_count": int(code_count or 0),
                "error": "请输入 DELETE（或 删除）以确认永久删除。",
            },
            status_code=200,
        )

    db.delete(batch)
    db.commit()

    return RedirectResponse(
        url=f"/admin/products/{product_id}/batches",
        status_code=HTTP_303_SEE_OTHER,
    )
