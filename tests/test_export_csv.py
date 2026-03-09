from __future__ import annotations

import codecs
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


def test_export_batch_csv_contains_verify_urls(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="产品A", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 12), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add_all(
            [
                AntiCode(code="5555666677778888", product_id=product.id, batch_id=batch.id),
                AntiCode(code="1111222233334444", product_id=product.id, batch_id=batch.id),
            ]
        )
        db.commit()

        batch_id = batch.id

    r = client.get(f"/admin/batches/{batch_id}/export/csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    assert r.content.startswith(codecs.BOM_UTF8)
    body = r.content.decode("utf-8-sig")
    assert "product_name,production_date,code,verify_url" in body
    assert "产品A,2026-02-12,5555666677778888" in body
    assert "verify_url" in body
    assert "/verify?code=5555666677778888" in body
    assert "/verify?code=1111222233334444" in body


def test_export_batch_csv_preserves_batch_date_precision(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="产品B", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date="2026-02", note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(AntiCode(code="2222333344445555", product_id=product.id, batch_id=batch.id))
        db.commit()

        batch_id = batch.id

    r = client.get(f"/admin/batches/{batch_id}/export/csv")
    assert r.status_code == 200
    body = r.content.decode("utf-8-sig")
    assert "产品B,2026-02,2222333344445555" in body
