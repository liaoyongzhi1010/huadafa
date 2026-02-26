from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import (
    AntiCode,
    Base,
    Batch,
    PageContent,
    Product,
    Recommendation,
    ScanEvent,
    VerifyConfig,
)


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


def test_verify_not_found_returns_404(client_and_sessionmaker):
    client, _ = client_and_sessionmaker

    r = client.get("/api/public/verify", params={"code": "1234567890123456"})
    assert r.status_code == 404
    data = r.json()
    assert data["status"] == "not_found"


def test_verify_genuine_returns_product_and_config(client_and_sessionmaker):
    client, SessionLocal = client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(
            name="ICOM 打火机",
            detail_text="产品详情文字",
            detail_images=[{"url": "https://img.example/a.png"}],
        )
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(
            product_id=product.id,
            production_date=date(2026, 2, 12),
            note="第一批",
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)

        anti_code = AntiCode(
            code="1564567894562156",
            product_id=product.id,
            batch_id=batch.id,
            scan_count=2,
        )
        db.add(anti_code)
        db.commit()
        db.refresh(anti_code)

        db.add_all(
            [
                VerifyConfig(
                    show_code=False,
                    warning_threshold=5,
                    recent_events_limit=5,
                    contact_us_url="https://example.com/contact",
                    text_genuine="ICOM 官方正品防伪码",
                    text_not_found="未查询到该防伪码",
                    text_warning="此防伪码已被多次验证，请您留意！",
                ),
                PageContent(key="brand_traceability", content_json={"text": "品牌溯源内容"}),
                PageContent(key="about_us", content_json={"text": "关于我们内容"}),
                Recommendation(
                    product_id=product.id,
                    image_url="https://img.example/reco.png",
                    target_url="https://example.com/reco",
                    enabled=True,
                    sort_order=10,
                ),
                ScanEvent(
                    anti_code_id=anti_code.id,
                    scanned_at=datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc),
                    visitor_id="v1",
                    ip_hash="",
                    ua_hash="",
                ),
            ]
        )
        db.commit()

    r = client.get("/api/public/verify", params={"code": "1564567894562156"})
    assert r.status_code == 200
    data = r.json()

    assert data["status"] == "genuine"
    assert data["scan_count"] == 2
    assert data["show_code"] is False
    assert data["warning_threshold"] == 5
    assert data["contact_us_url"] == "https://example.com/contact"

    assert data["product"]["name"] == "ICOM 打火机"
    assert data["product"]["detail_text"] == "产品详情文字"
    assert data["product"]["detail_images"] == [{"url": "https://img.example/a.png"}]

    assert data["page_content"]["brand_traceability"]["text"] == "品牌溯源内容"
    assert data["page_content"]["about_us"]["text"] == "关于我们内容"

    assert data["recommendations"] == [
        {"image_url": "https://img.example/reco.png", "target_url": "https://example.com/reco"}
    ]
    assert len(data["recent_events"]) == 1


def test_verify_disabled_code_returns_410(client_and_sessionmaker):
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

        anti_code = AntiCode(
            code="9999888877776666",
            product_id=product.id,
            batch_id=batch.id,
            status="disabled",
            disabled_reason="作废",
        )
        db.add(anti_code)
        db.commit()

    r = client.get("/api/public/verify", params={"code": "9999888877776666"})
    assert r.status_code == 410
    data = r.json()
    assert data["status"] == "disabled"

