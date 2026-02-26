from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_303_SEE_OTHER

from app.settings import get_settings
from app.web import templates

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "admin/login.html", {})


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    settings = get_settings()
    if username == settings.admin_username and password == settings.admin_password:
        request.session["admin_logged_in"] = True
        return RedirectResponse(url="/admin", status_code=HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "admin/login.html",
        {"error": "账号或密码错误"},
        status_code=200,
    )


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
