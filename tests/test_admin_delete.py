from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
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


def test_admin_delete_product_requires_confirmation(admin_client_and_sessionmaker):
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

        db.add(AntiCode(code="1234567890123456", product_id=product.id, batch_id=batch.id, scan_count=0))
        db.commit()

        product_id = product.id

    r = client.get(f"/admin/products/{product_id}/delete")
    assert r.status_code == 200
    assert "删除产品" in r.text

    r2 = client.post(f"/admin/products/{product_id}/delete", data={"confirm_text": "nope"})
    assert r2.status_code == 200

    with SessionLocal() as db:
        assert db.execute(select(func.count(Product.id))).scalar_one() == 1
        assert db.execute(select(func.count(Batch.id))).scalar_one() == 1
        assert db.execute(select(func.count(AntiCode.id))).scalar_one() == 1

    r3 = client.post(f"/admin/products/{product_id}/delete", data={"confirm_text": "DELETE"})
    assert r3.status_code in (200, 302, 303)

    with SessionLocal() as db:
        assert db.execute(select(func.count(Product.id))).scalar_one() == 0
        assert db.execute(select(func.count(Batch.id))).scalar_one() == 0
        assert db.execute(select(func.count(AntiCode.id))).scalar_one() == 0


def test_admin_delete_batch_deletes_only_that_batch(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch1 = Batch(product_id=product.id, production_date=date(2026, 2, 12), note="")
        batch2 = Batch(product_id=product.id, production_date=date(2026, 2, 13), note="")
        db.add_all([batch1, batch2])
        db.commit()
        db.refresh(batch1)
        db.refresh(batch2)

        db.add(AntiCode(code="1234567890123456", product_id=product.id, batch_id=batch1.id, scan_count=0))
        db.commit()

        product_id = product.id
        batch1_id = batch1.id
        batch2_id = batch2.id

    r = client.get(f"/admin/batches/{batch1_id}/delete")
    assert r.status_code == 200
    assert "删除批次" in r.text

    r2 = client.post(f"/admin/batches/{batch1_id}/delete", data={"confirm_text": "DELETE"})
    assert r2.status_code in (200, 302, 303)

    with SessionLocal() as db:
        batch_ids = set(db.execute(select(Batch.id)).scalars().all())
        assert batch1_id not in batch_ids
        assert batch2_id in batch_ids
        assert db.execute(select(func.count(AntiCode.id))).scalar_one() == 0

    # Remaining batch list still accessible
    r3 = client.get(f"/admin/products/{product_id}/batches")
    assert r3.status_code == 200

