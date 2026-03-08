from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_db
from app.models import VerifyConfig
from app.web import templates

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return None


def _get_or_create_config(db: Session) -> VerifyConfig:
    cfg = db.execute(select(VerifyConfig).order_by(desc(VerifyConfig.id))).scalar_one_or_none()
    if cfg is not None:
        return cfg
    cfg = VerifyConfig()
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


@router.get("/config")
def config_page(request: Request, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    cfg = _get_or_create_config(db)
    return templates.TemplateResponse(request, "admin/config_edit.html", {"cfg": cfg})


@router.post("/config")
def config_submit(
    request: Request,
    warning_threshold: str = Form("5"),
    recent_events_limit: str = Form("5"),
    text_warning: str = Form("此防伪码已被多次验证，请您留意！"),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    cfg = _get_or_create_config(db)

    try:
        cfg.warning_threshold = max(1, int(warning_threshold))
    except ValueError:
        cfg.warning_threshold = 5
    try:
        cfg.recent_events_limit = max(1, int(recent_events_limit))
    except ValueError:
        cfg.recent_events_limit = 5

    cfg.text_warning = text_warning.strip() or cfg.text_warning

    db.add(cfg)
    db.commit()

    return RedirectResponse(url="/admin/config", status_code=HTTP_303_SEE_OTHER)
