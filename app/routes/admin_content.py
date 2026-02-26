from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_db
from app.models import PageContent

router = APIRouter(prefix="/admin", tags=["admin"])

templates = Jinja2Templates(directory="app/templates")


def _require_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return None


def _get_text(db: Session, key: str) -> str:
    pc = db.execute(select(PageContent).where(PageContent.key == key)).scalar_one_or_none()
    if pc is None:
        return ""
    if isinstance(pc.content_json, dict):
        return str(pc.content_json.get("text", ""))
    return ""


def _set_text(db: Session, key: str, text: str) -> None:
    pc = db.execute(select(PageContent).where(PageContent.key == key)).scalar_one_or_none()
    if pc is None:
        pc = PageContent(key=key, content_json={"text": text})
        db.add(pc)
        return
    pc.content_json = {"text": text}
    db.add(pc)


@router.get("/content")
def content_page(request: Request, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    return templates.TemplateResponse(
        request,
        "admin/content_edit.html",
        {
            "brand_text": _get_text(db, "brand_traceability"),
            "about_text": _get_text(db, "about_us"),
        },
    )


@router.post("/content")
def content_submit(
    request: Request,
    brand_text: str = Form(""),
    about_text: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    _set_text(db, "brand_traceability", brand_text)
    _set_text(db, "about_us", about_text)
    db.commit()

    return RedirectResponse(url="/admin/content", status_code=HTTP_303_SEE_OTHER)

