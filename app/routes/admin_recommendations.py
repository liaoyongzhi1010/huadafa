from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_db
from app.models import Recommendation

router = APIRouter(prefix="/admin", tags=["admin"])

templates = Jinja2Templates(directory="app/templates")


def _require_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return None


@router.get("/recommendations")
def recommendations_list(request: Request, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    recs = db.execute(select(Recommendation).order_by(desc(Recommendation.sort_order), desc(Recommendation.id))).scalars().all()
    return templates.TemplateResponse(request, "admin/recommendations_list.html", {"recs": recs})


@router.get("/recommendations/new")
def recommendation_new_page(request: Request):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    return templates.TemplateResponse(request, "admin/recommendation_new.html", {})


@router.post("/recommendations/new")
def recommendation_new_submit(
    request: Request,
    image_url: str = Form(""),
    target_url: str = Form(""),
    product_id: str = Form(""),
    enabled: str | None = Form(None),
    sort_order: str = Form("0"),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    image_url = image_url.strip()
    target_url = target_url.strip()
    if not image_url or not target_url:
        return templates.TemplateResponse(
            request,
            "admin/recommendation_new.html",
            {"error": "推荐图片与跳转链接不能为空", "image_url": image_url, "target_url": target_url},
            status_code=200,
        )

    pid: int | None = None
    try:
        if product_id.strip():
            pid = int(product_id)
    except ValueError:
        pid = None

    try:
        order = int(sort_order)
    except ValueError:
        order = 0

    db.add(
        Recommendation(
            product_id=pid,
            image_url=image_url,
            target_url=target_url,
            enabled=enabled is not None,
            sort_order=order,
        )
    )
    db.commit()
    return RedirectResponse(url="/admin/recommendations", status_code=HTTP_303_SEE_OTHER)

