from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import AntiCode, Base, Batch, Product, ScanEvent


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


def test_admin_dashboard_shows_basic_stats(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 12), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        code1 = AntiCode(code="1234567890123456", product_id=product.id, batch_id=batch.id, scan_count=2)
        db.add_all(
            [
                code1,
                AntiCode(code="1111222233334444", product_id=product.id, batch_id=batch.id, scan_count=0),
            ]
        )
        db.commit()
        db.refresh(code1)

        db.add_all(
            [
                ScanEvent(anti_code_id=code1.id, scanned_at=now, visitor_id="v1", ip_hash="", ua_hash=""),
                ScanEvent(
                    anti_code_id=code1.id,
                    scanned_at=now - timedelta(hours=1),
                    visitor_id="v2",
                    ip_hash="",
                    ua_hash="",
                ),
                ScanEvent(
                    anti_code_id=code1.id,
                    scanned_at=now - timedelta(days=8),
                    visitor_id="v3",
                    ip_hash="",
                    ua_hash="",
                ),
            ]
        )
        db.commit()

    r = client.get("/admin")
    assert r.status_code == 200
    assert "今日扫码" in r.text
    assert "近7天扫码" in r.text
    assert "防伪码总数" in r.text
    assert "批次数" in r.text
