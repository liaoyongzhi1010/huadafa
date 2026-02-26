from __future__ import annotations

import re
from datetime import date
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import AntiCode, Base, Batch, PageContent, Product, ScanEvent, VerifyConfig


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

        db.add(AntiCode(code="1564567894562156", product_id=product.id, batch_id=batch.id, scan_count=0))
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
        product.detail_text = "产品详情文字"
        product.detail_images = [{"url": "/uploads/products/1/x.png"}, {"url": "/uploads/products/1/y.png"}]
        db.add_all(
            [
                PageContent(key="brand_traceability", content_json={"text": "品牌溯源内容"}),
                PageContent(key="about_us", content_json={"text": "关于我们内容"}),
            ]
        )
        db.commit()

    r = client.get("/verify", params={"code": "1564567894562156"})
    assert r.status_code == 200
    assert "ICOM 官方正品防伪码" in r.text
    assert "产品详情文字" in r.text
    assert "/uploads/products/1/x.png" in r.text
    assert "/static/placeholders/recommendation.svg" in r.text
    assert "品牌溯源内容" in r.text
    assert "关于我们内容" in r.text


def test_verify_page_shows_not_found_message(client_and_sessionmaker):
    client, _ = client_and_sessionmaker

    r = client.get("/verify", params={"code": "1234567890123456"})
    assert r.status_code == 200
    assert "未查询到" in r.text


def test_verify_page_first_scan_shows_recent_time(client_and_sessionmaker):
    client, SessionLocal = client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 12), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(AntiCode(code="1564567894562156", product_id=product.id, batch_id=batch.id, scan_count=0))
        db.commit()

    r = client.get("/verify", params={"code": "1564567894562156"})
    assert r.status_code == 200
    assert "最近验证时间" in r.text
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", r.text)


def test_verify_page_formats_recent_events_in_beijing_time(client_and_sessionmaker):
    client, SessionLocal = client_and_sessionmaker

    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    expected = now_utc.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 12), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        anti = AntiCode(code="9999888877776666", product_id=product.id, batch_id=batch.id, scan_count=0)
        db.add(anti)
        db.commit()
        db.refresh(anti)

        db.add(ScanEvent(anti_code_id=anti.id, scanned_at=now_utc, visitor_id="v1", ip_hash="", ua_hash=""))
        db.commit()

    r = client.get("/verify", params={"code": "9999888877776666"}, cookies={"visitor_id": "v1"})
    assert r.status_code == 200
    assert expected in r.text
