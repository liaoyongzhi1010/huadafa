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
        r = client.post("/admin/login", data={"username": "admin", "password": "admin"})
        assert r.status_code in (200, 302, 303)
        yield client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()


def test_admin_products_page_and_create(admin_client_and_sessionmaker):
    client, _ = admin_client_and_sessionmaker

    r = client.get("/admin/products")
    assert r.status_code == 200

    r2 = client.post("/admin/products/new", data={"name": "ICOM 打火机", "detail_text": ""})
    assert r2.status_code in (200, 302, 303)

    r3 = client.get("/admin/products")
    assert r3.status_code == 200
    assert "ICOM 打火机" in r3.text
    assert "产品工作台" in r3.text
    assert "/admin/products/" in r3.text
    assert "/edit" not in r3.text
    assert "/workspace" not in r3.text
    assert "/batches" in r3.text


def test_admin_product_workspace_route_redirects_to_batches(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="Jump", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

    r = client.get(f"/admin/products/{product_id}/workspace", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"].endswith(f"/admin/products/{product_id}/batches")


def test_admin_product_preview_verify_redirects_with_random_code(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

        batch = Batch(product_id=product_id, production_date=date(2026, 3, 7), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(AntiCode(code="1234432112344321", product_id=product_id, batch_id=batch.id, status="active"))
        db.commit()

    r = client.get(f"/admin/products/{product_id}/preview/verify", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"].endswith("/verify?code=1234432112344321&preview=1")


def test_admin_product_preview_verify_redirects_to_workspace_when_no_code(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="NoCode", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

    r = client.get(f"/admin/products/{product_id}/preview/verify", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"].endswith(f"/admin/products/{product_id}/batches/new?notice=preview_no_code")
