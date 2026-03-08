from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response, RedirectResponse
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_db
from app.services.export_csv import export_batch_codes_csv
from app.services.export_qrcodes import export_batch_qrcodes_zip, export_product_generic_qrcode_png
from app.settings import get_settings

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return None


@router.get("/batches/{batch_id}/export/csv")
def export_batch_csv(request: Request, batch_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    settings = get_settings()
    content = export_batch_codes_csv(db=db, batch_id=batch_id, base_url=settings.base_url)
    if not content:
        return RedirectResponse(url="/admin", status_code=HTTP_303_SEE_OTHER)

    filename = f"batch_{batch_id}_codes.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/batches/{batch_id}/export/qrcodes.zip")
def export_batch_qrcodes_zipfile(request: Request, batch_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    settings = get_settings()
    content = export_batch_qrcodes_zip(db=db, batch_id=batch_id, base_url=settings.base_url)
    if not content:
        return RedirectResponse(url="/admin", status_code=HTTP_303_SEE_OTHER)

    filename = f"batch_{batch_id}_qrcodes.zip"
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/products/{product_id}/export/generic-qrcode.png")
def export_product_generic_qrcode(request: Request, product_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    settings = get_settings()
    content = export_product_generic_qrcode_png(db=db, product_id=product_id, base_url=settings.base_url)
    if not content:
        return RedirectResponse(url="/admin", status_code=HTTP_303_SEE_OTHER)

    filename = f"product_{product_id}_generic_qrcode.png"
    return Response(
        content=content,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
