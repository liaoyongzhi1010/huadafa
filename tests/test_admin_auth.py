from __future__ import annotations

from fastapi.testclient import TestClient


def test_admin_login_page_ok():
    from app.main import app

    client = TestClient(app)
    r = client.get("/admin/login")
    assert r.status_code == 200


def test_admin_requires_login_redirects():
    from app.main import app

    client = TestClient(app)
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"].endswith("/admin/login")


def test_admin_login_success_sets_session_and_allows_admin():
    from app.main import app

    client = TestClient(app)
    r = client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert r.headers["location"].endswith("/admin")

    r2 = client.get("/admin", follow_redirects=False)
    assert r2.status_code == 200
    assert "/admin/products" in r2.text
    assert "/admin/config" in r2.text
    assert "/admin/content" not in r2.text
    assert "/admin/recommendations" not in r2.text
    assert "/admin/products/new" not in r2.text
    assert "新增产品" not in r2.text


def test_admin_login_wrong_password_shows_error():
    from app.main import app

    client = TestClient(app)
    r = client.post("/admin/login", data={"username": "admin", "password": "bad"})
    assert r.status_code == 200
    assert "账号" in r.text or "密码" in r.text or "错误" in r.text


def test_admin_help_requires_login_redirects():
    from app.main import app

    client = TestClient(app)
    r = client.get("/admin/help", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"].endswith("/admin/login")


def test_admin_help_page_ok_when_logged_in():
    from app.main import app

    client = TestClient(app)
    client.post("/admin/login", data={"username": "admin", "password": "admin"})

    r = client.get("/admin/help")
    assert r.status_code == 200
    assert "使用文档" in r.text
