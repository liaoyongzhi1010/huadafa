from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import Base, Batch, Product


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


def test_admin_can_create_batch_for_product(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

    r = client.post(
        f"/admin/products/{product_id}/batches/new",
        data={"production_date": date(2026, 2, 12).isoformat(), "note": "第一批"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    r2 = client.get(f"/admin/products/{product_id}/batches")
    assert r2.status_code == 200
    assert "2026-02-12" in r2.text


def test_admin_batch_detail_redirects_to_product_batches(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 12), note="第一批")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        product_id = product.id
        batch_id = batch.id

    r = client.get(f"/admin/batches/{batch_id}", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"].endswith(f"/admin/products/{product_id}/batches")
