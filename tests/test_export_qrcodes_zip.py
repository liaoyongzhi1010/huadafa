from __future__ import annotations

from datetime import date
from io import BytesIO
from zipfile import ZipFile

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


def test_export_qrcodes_zip_contains_pngs(admin_client_and_sessionmaker):
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

        db.add_all(
            [
                AntiCode(code="7777888899990000", product_id=product.id, batch_id=batch.id),
                AntiCode(code="8888999900001111", product_id=product.id, batch_id=batch.id),
            ]
        )
        db.commit()
        batch_id = batch.id

    r = client.get(f"/admin/batches/{batch_id}/export/qrcodes.zip")
    assert r.status_code == 200
    assert "application/zip" in r.headers.get("content-type", "")

    with ZipFile(BytesIO(r.content)) as zf:
        names = set(zf.namelist())
    assert "7777888899990000.png" in names
    assert "8888999900001111.png" in names


def test_export_generic_qrcode_png(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        product_id = product.id

    r = client.get(f"/admin/products/{product_id}/export/generic-qrcode.png")
    assert r.status_code == 200
    assert "image/png" in r.headers.get("content-type", "")
    assert r.content.startswith(b"\x89PNG\r\n\x1a\n")
