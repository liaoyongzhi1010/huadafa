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


def test_batches_list_hides_generate_form_when_codes_exist(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

        batch_empty = Batch(product_id=product.id, production_date=date(2026, 2, 12), note="")
        batch_generated = Batch(product_id=product.id, production_date=date(2026, 2, 13), note="")
        db.add_all([batch_empty, batch_generated])
        db.commit()
        db.refresh(batch_empty)
        db.refresh(batch_generated)

        db.add(AntiCode(code="1234567890123456", product_id=product.id, batch_id=batch_generated.id, scan_count=0))
        db.commit()

        empty_id = batch_empty.id
        generated_id = batch_generated.id

    r = client.get(f"/admin/products/{product_id}/batches")
    assert r.status_code == 200
    assert f'/admin/batches/{empty_id}/codes/generate' in r.text
    assert f'/admin/batches/{generated_id}/codes/generate' not in r.text
