from __future__ import annotations

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
        data={"production_date": "2026-02-12", "note": "第一批", "quantity": "3"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    with SessionLocal() as db:
        batch = db.query(Batch).filter(Batch.product_id == product_id).order_by(Batch.id.desc()).first()
        assert batch is not None
        assert batch.production_date == "2026-02-12"
        codes = db.query(AntiCode).filter(AntiCode.batch_id == batch.id).all()
        assert len(codes) == 3

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

        batch = Batch(product_id=product.id, production_date="2026-02-12", note="第一批")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        product_id = product.id
        batch_id = batch.id

    r = client.get(f"/admin/batches/{batch_id}", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"].endswith(f"/admin/products/{product_id}/batches")


@pytest.mark.parametrize("batch_date", ["2026", "2026-02", "2026-02-12"])
def test_admin_can_create_batch_with_supported_date_precision(
    admin_client_and_sessionmaker, batch_date: str
):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

    r = client.post(
        f"/admin/products/{product_id}/batches/new",
        data={"production_date": batch_date, "note": "多精度", "quantity": "1"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    with SessionLocal() as db:
        batch = db.query(Batch).filter(Batch.product_id == product_id).order_by(Batch.id.desc()).first()
        assert batch is not None
        assert batch.production_date == batch_date


def test_admin_rejects_invalid_batch_date(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

    r = client.post(
        f"/admin/products/{product_id}/batches/new",
        data={"production_date": "2026-13", "note": "错误日期", "quantity": "1"},
    )
    assert r.status_code == 200
    assert "批次日期格式必须是 YYYY、YYYY-MM 或 YYYY-MM-DD。" in r.text
    assert 'value="2026-13"' in r.text

    with SessionLocal() as db:
        count = db.query(Batch).filter(Batch.product_id == product_id).count()
        assert count == 0
