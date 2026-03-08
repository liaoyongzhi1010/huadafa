from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import AntiCode, Base, Batch, Product


@pytest.fixture()
def admin_client_and_sessionmaker():
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
    client = TestClient(app)
    try:
        client.post("/admin/login", data={"username": "admin", "password": "admin"})
        yield client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()


def test_admin_config_changes_public_verify(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 12), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(AntiCode(code="3333444455556666", product_id=product.id, batch_id=batch.id))
        db.commit()

    r = client.post(
        "/admin/config",
        data={
            # unchecked checkbox won't submit; so omit to set False
            "warning_threshold": "7",
            "recent_events_limit": "3",
            "contact_us_url": "https://example.com/contact",
            "text_genuine": "TEST 正品",
            "text_not_found": "TEST 未查到",
            "text_warning": "TEST 警示",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    r2 = client.get("/api/public/verify", params={"code": "3333444455556666"})
    assert r2.status_code == 200
    data = r2.json()
    assert data["show_code"] is True
    assert data["warning_threshold"] == 7
    assert data["contact_us_url"] == ""


def test_admin_config_page_hides_removed_fields(admin_client_and_sessionmaker):
    client, _ = admin_client_and_sessionmaker

    r = client.get("/admin/config")
    assert r.status_code == 200
    assert "显示防伪码" not in r.text
    assert "通用二维码页显示产品名称" not in r.text
    assert "通用二维码页显示生产日期" not in r.text
    assert "联系我们跳转 URL" not in r.text
    assert "正品提示文案" not in r.text
    assert "未查到文案" not in r.text
    assert "警示阈值（次数）" in r.text
    assert "展示最近验证条数" in r.text
    assert "警示文案" in r.text
