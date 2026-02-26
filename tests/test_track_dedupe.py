from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import AntiCode, Base, Batch, Product, ScanEvent


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


def _seed_code(SessionLocal, code: str) -> int:
    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 12), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        anti_code = AntiCode(code=code, product_id=product.id, batch_id=batch.id, scan_count=0)
        db.add(anti_code)
        db.commit()
        db.refresh(anti_code)
        return anti_code.id


def test_track_increments_once_and_dedupes_within_60s(client_and_sessionmaker):
    client, SessionLocal = client_and_sessionmaker
    anti_code_id = _seed_code(SessionLocal, "1111222233334444")

    r1 = client.post(
        "/api/public/verify/track",
        json={"code": "1111222233334444"},
        cookies={"visitor_id": "v1"},
    )
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["deduped"] is False
    assert data1["scan_count"] == 1

    r2 = client.post(
        "/api/public/verify/track",
        json={"code": "1111222233334444"},
        cookies={"visitor_id": "v1"},
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["deduped"] is True
    assert data2["scan_count"] == 1

    with SessionLocal() as db:
        events = db.execute(select(ScanEvent).where(ScanEvent.anti_code_id == anti_code_id)).scalars().all()
        assert len(events) == 1
        refreshed = db.get(AntiCode, anti_code_id)
        assert refreshed is not None
        assert refreshed.scan_count == 1


def test_track_allows_again_after_60s(client_and_sessionmaker):
    client, SessionLocal = client_and_sessionmaker
    anti_code_id = _seed_code(SessionLocal, "2222333344445555")

    r1 = client.post(
        "/api/public/verify/track",
        json={"code": "2222333344445555"},
        cookies={"visitor_id": "v1"},
    )
    assert r1.status_code == 200
    assert r1.json()["scan_count"] == 1

    with SessionLocal() as db:
        event = (
            db.execute(select(ScanEvent).where(ScanEvent.anti_code_id == anti_code_id))
            .scalars()
            .first()
        )
        assert event is not None
        event.scanned_at = datetime.now(timezone.utc) - timedelta(seconds=61)
        db.commit()

    r2 = client.post(
        "/api/public/verify/track",
        json={"code": "2222333344445555"},
        cookies={"visitor_id": "v1"},
    )
    assert r2.status_code == 200
    assert r2.json()["deduped"] is False
    assert r2.json()["scan_count"] == 2

