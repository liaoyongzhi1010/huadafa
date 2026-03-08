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


def test_verify_page_settings_page_and_submit_affect_public_pages(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="Title-P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date=date(2026, 3, 8), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(AntiCode(code="6666777788889999", product_id=product.id, batch_id=batch.id, scan_count=0))
        db.commit()
        product_id = product.id

    page = client.get(f"/admin/products/{product_id}/verify-page-settings")
    assert page.status_code == 200
    assert "防伪设置" in page.text
    assert "左侧设置，右侧手机整页预览" in page.text
    assert "手机整页预览：防伪页" in page.text
    assert "去页面设置" in page.text
    assert '/verify?code=6666777788889999&amp;preview=1' in page.text
    assert f'action="/admin/products/{product_id}/verify-page-settings"' in page.text

    submit = client.post(
        f"/admin/products/{product_id}/verify-page-settings",
        data={
            "brand_mark": "中",
            "brand_name": "中国爱酷防伪中心",
            "brand_sub": "AIKU CUSTOM SUBTITLE",
        },
        follow_redirects=False,
    )
    assert submit.status_code in (302, 303)
    assert submit.headers["location"].endswith(f"/admin/products/{product_id}/verify-page-settings")

    verify_page = client.get("/verify", params={"code": "6666777788889999", "preview": "1"})
    assert verify_page.status_code == 200
    assert "中" in verify_page.text
    assert "中国爱酷防伪中心" in verify_page.text
    assert "AIKU CUSTOM SUBTITLE" in verify_page.text
    assert "爱酷，中国爱酷防伪中心" not in verify_page.text

    generic_page = client.get("/verify/general", params={"product_id": str(product_id)})
    assert generic_page.status_code == 200
    assert "中" in generic_page.text
    assert "中国爱酷防伪中心" in generic_page.text
    assert "AIKU CUSTOM SUBTITLE" in generic_page.text
    assert "爱酷，中国爱酷防伪中心" not in generic_page.text


def test_verify_page_settings_page_shows_default_values_when_empty(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="Default-P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

    page = client.get(f"/admin/products/{product_id}/verify-page-settings")
    assert page.status_code == 200
    assert 'name="brand_mark" value="爱酷"' in page.text
    assert 'name="brand_name" value="中国爱酷防伪中心"' in page.text
    assert 'name="brand_sub" value="AIKU CHINA VERIFICATION CENTER"' in page.text
    assert "暂无可用防伪码" in page.text


def test_contact_settings_page_and_submit_affect_public_pages(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="Contact-P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date=date(2026, 3, 8), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(AntiCode(code="1010101010101010", product_id=product.id, batch_id=batch.id, scan_count=0))
        db.commit()
        product_id = product.id

    page = client.get(f"/admin/products/{product_id}/contact-settings")
    assert page.status_code == 200
    assert "联系我们设置" in page.text
    assert "手机整页预览：联系我们" in page.text
    assert "暂无联系我们链接" in page.text
    assert f'action="/admin/products/{product_id}/contact-settings"' in page.text

    submit = client.post(
        f"/admin/products/{product_id}/contact-settings",
        data={"contact_us_url": "https://example.com/contact-us"},
        follow_redirects=False,
    )
    assert submit.status_code in (302, 303)
    assert submit.headers["location"].endswith(f"/admin/products/{product_id}/contact-settings")

    page_after = client.get(f"/admin/products/{product_id}/contact-settings")
    assert page_after.status_code == 200
    assert 'src="https://example.com/contact-us"' in page_after.text
    assert "暂无联系我们链接" not in page_after.text

    verify_page = client.get("/verify", params={"code": "1010101010101010", "preview": "1"})
    assert verify_page.status_code == 200
    assert 'href="https://example.com/contact-us"' in verify_page.text
    assert "联系我们" in verify_page.text

    generic_page = client.get("/verify/general", params={"product_id": str(product_id)})
    assert generic_page.status_code == 200
    assert 'href="https://example.com/contact-us"' in generic_page.text
    assert "联系我们" in generic_page.text
