from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_303_SEE_OTHER

router = APIRouter(prefix="/admin", tags=["admin"])

from app.web import templates


@router.get("")
@router.get("/")
def admin_index(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "admin/index.html", {})
