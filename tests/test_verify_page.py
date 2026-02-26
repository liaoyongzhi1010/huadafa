from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import AntiCode, Base, Batch, Product, VerifyConfig


@pytest.fixture()
def client_and_sessionmaker():
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
        yield client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()


def test_verify_page_shows_genuine_message(client_and_sessionmaker):
    client, SessionLocal = client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="ICOM 打火机", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 12), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(
            AntiCode(code="1564567894562156", product_id=product.id, batch_id=batch.id, scan_count=0)
        )
        db.add(
            VerifyConfig(
                show_code=True,
                warning_threshold=5,
                recent_events_limit=5,
                contact_us_url="https://example.com/contact",
                text_genuine="ICOM 官方正品防伪码",
                text_not_found="未查询到该防伪码",
                text_warning="此防伪码已被多次验证，请您留意！",
            )
        )
        db.commit()

    r = client.get("/verify", params={"code": "1564567894562156"})
    assert r.status_code == 200
    assert "ICOM 官方正品防伪码" in r.text


def test_verify_page_shows_not_found_message(client_and_sessionmaker):
    client, _ = client_and_sessionmaker

    r = client.get("/verify", params={"code": "1234567890123456"})
    assert r.status_code == 200
    assert "未查询到" in r.text

