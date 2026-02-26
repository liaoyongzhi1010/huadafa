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


def test_admin_content_changes_public_verify(admin_client_and_sessionmaker):
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

        db.add(AntiCode(code="4444555566667777", product_id=product.id, batch_id=batch.id))
        db.commit()

    r = client.post(
        "/admin/content",
        data={
            "brand_text": "品牌溯源内容 A",
            "about_text": "关于我们内容 B",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    r2 = client.get("/api/public/verify", params={"code": "4444555566667777"})
    assert r2.status_code == 200
    data = r2.json()
    assert data["page_content"]["brand_traceability"]["text"] == "品牌溯源内容 A"
    assert data["page_content"]["about_us"]["text"] == "关于我们内容 B"

