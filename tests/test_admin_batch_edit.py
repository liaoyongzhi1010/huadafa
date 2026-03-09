from __future__ import annotations

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


def test_admin_can_open_batch_edit_page(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date="2026-02", note="初版备注")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        batch_id = batch.id

    r = client.get(f"/admin/batches/{batch_id}/edit")
    assert r.status_code == 200
    assert 'value="2026-02"' in r.text
    assert 'value="初版备注"' in r.text


def test_admin_can_edit_batch_date_and_note(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date="2026-02-12", note="初版备注")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        product_id = product.id
        batch_id = batch.id

    r = client.post(
        f"/admin/batches/{batch_id}/edit",
        data={"production_date": "2026", "note": "改成按年"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert r.headers["location"].endswith(f"/admin/products/{product_id}/batches")

    with SessionLocal() as db:
        batch = db.query(Batch).filter(Batch.id == batch_id).one()
        assert batch.production_date == "2026"
        assert batch.note == "改成按年"


def test_admin_rejects_invalid_batch_date_when_editing(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date="2026-02-12", note="初版备注")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        batch_id = batch.id

    r = client.post(
        f"/admin/batches/{batch_id}/edit",
        data={"production_date": "2026-02-31", "note": "不合法"},
    )
    assert r.status_code == 200
    assert "批次日期格式必须是 YYYY、YYYY-MM 或 YYYY-MM-DD。" in r.text
    assert 'value="2026-02-31"' in r.text
