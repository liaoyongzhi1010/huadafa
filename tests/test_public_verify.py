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


def test_verify_recommendations_are_product_specific(client_and_sessionmaker):
    client, SessionLocal = client_and_sessionmaker

    with SessionLocal() as db:
        p1 = Product(name="P1", detail_text="", detail_images=[])
        p2 = Product(name="P2", detail_text="", detail_images=[])
        db.add_all([p1, p2])
        db.commit()
        db.refresh(p1)
        db.refresh(p2)

        b1 = Batch(product_id=p1.id, production_date=date(2026, 2, 12), note="")
        b2 = Batch(product_id=p2.id, production_date=date(2026, 2, 12), note="")
        db.add_all([b1, b2])
        db.commit()
        db.refresh(b1)
        db.refresh(b2)

        db.add(AntiCode(code="1212121212121212", product_id=p1.id, batch_id=b1.id))
        db.add(AntiCode(code="3434343434343434", product_id=p2.id, batch_id=b2.id))
        db.add_all(
            [
                Recommendation(
                    product_id=None,
                    image_url="https://img.example/global.png",
                    target_url="https://example.com/global",
                    enabled=True,
                    sort_order=99,
                ),
                Recommendation(
                    product_id=p1.id,
                    image_url="https://img.example/p1.png",
                    target_url="https://example.com/p1",
                    enabled=True,
                    sort_order=10,
                ),
                Recommendation(
                    product_id=p2.id,
                    image_url="https://img.example/p2.png",
                    target_url="https://example.com/p2",
                    enabled=True,
                    sort_order=10,
                ),
            ]
        )
        db.commit()

    r = client.get("/api/public/verify", params={"code": "1212121212121212"})
    assert r.status_code == 200
    data = r.json()
    assert data["recommendations"] == [
        {"image_url": "https://img.example/p1.png", "target_url": "https://example.com/p1"}
    ]


def test_verify_page_content_is_product_specific(client_and_sessionmaker):
    client, SessionLocal = client_and_sessionmaker

    with SessionLocal() as db:
        p1 = Product(name="PX1", detail_text="", detail_images=[])
        p2 = Product(name="PX2", detail_text="", detail_images=[])
        db.add_all([p1, p2])
        db.commit()
        db.refresh(p1)
        db.refresh(p2)

        b1 = Batch(product_id=p1.id, production_date=date(2026, 2, 12), note="")
        b2 = Batch(product_id=p2.id, production_date=date(2026, 2, 12), note="")
        db.add_all([b1, b2])
        db.commit()
        db.refresh(b1)
        db.refresh(b2)

        db.add(AntiCode(code="5656565656565656", product_id=p1.id, batch_id=b1.id))
        db.add(AntiCode(code="7878787878787878", product_id=p2.id, batch_id=b2.id))
        db.add_all(
            [
                PageContent(key=f"product:{p1.id}:brand_traceability", content_json={"text": "P1 品牌内容"}),
                PageContent(key=f"product:{p1.id}:about_us", content_json={"text": "P1 关于我们"}),
                PageContent(key=f"product:{p2.id}:brand_traceability", content_json={"text": "P2 品牌内容"}),
                PageContent(key=f"product:{p2.id}:about_us", content_json={"text": "P2 关于我们"}),
            ]
        )
        db.commit()

    r = client.get("/api/public/verify", params={"code": "5656565656565656"})
    assert r.status_code == 200
    data = r.json()
    assert data["page_content"]["brand_traceability"]["text"] == "P1 品牌内容"
    assert data["page_content"]["about_us"]["text"] == "P1 关于我们"
