from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_db
from app.models import AntiCode, Batch

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


def _require_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return None


def _generate_code() -> str:
    first = str(secrets.randbelow(9) + 1)
    rest = "".join(str(secrets.randbelow(10)) for _ in range(15))
    return first + rest


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
        return RedirectResponse(url="/admin", status_code=HTTP_303_SEE_OTHER)

    try:
        n = int(quantity)
    except ValueError:
        n = 0

    n = max(0, min(n, 10000))
    if n == 0:
        return RedirectResponse(url=f"/admin/batches/{batch_id}", status_code=HTTP_303_SEE_OTHER)

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

    return RedirectResponse(url=f"/admin/batches/{batch_id}", status_code=HTTP_303_SEE_OTHER)


@router.get("/batches/{batch_id}")
def batch_detail(request: Request, batch_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    batch = db.execute(select(Batch).where(Batch.id == batch_id)).scalar_one_or_none()
    if batch is None:
        return RedirectResponse(url="/admin", status_code=HTTP_303_SEE_OTHER)

    code_count = db.execute(
        select(func.count()).select_from(AntiCode).where(AntiCode.batch_id == batch_id)
    ).scalar_one()
    return templates.TemplateResponse(
        request,
        "admin/batch_detail.html",
        {"batch": batch, "code_count": int(code_count)},
    )
