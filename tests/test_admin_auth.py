from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import Base


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


def test_admin_login_page_ok(client: TestClient):
    r = client.get("/admin/login")
    assert r.status_code == 200


def test_admin_requires_login_redirects(client: TestClient):
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"].endswith("/admin/login")


def test_admin_login_success_sets_session_and_allows_admin(client: TestClient):
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


def test_admin_login_wrong_password_shows_error(client: TestClient):
    r = client.post("/admin/login", data={"username": "admin", "password": "bad"})
    assert r.status_code == 200
    assert "账号" in r.text or "密码" in r.text or "错误" in r.text


def test_admin_help_requires_login_redirects(client: TestClient):
    r = client.get("/admin/help", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"].endswith("/admin/login")


def test_admin_help_page_ok_when_logged_in(client: TestClient):
    client.post("/admin/login", data={"username": "admin", "password": "admin"})

    r = client.get("/admin/help")
    assert r.status_code == 200
    assert "使用文档" in r.text
