from __future__ import annotations

import re
from datetime import date
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import AntiCode, Base, Batch, PageContent, Product, Recommendation, ScanEvent, VerifyConfig


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
                PageContent(
                    key=f"product:{product.id}:verify_page_settings",
                    content_json={
                        "brand_mark": "测标",
                        "brand_name": "中国爱酷防伪中心",
                        "brand_sub": "AIKU CHINA VERIFICATION CENTER",
                    },
                ),
                PageContent(key="brand_traceability", content_json={"text": "品牌溯源内容"}),
                PageContent(key="about_us", content_json={"text": "关于我们内容"}),
            ]
        )
        db.commit()

    r = client.get("/verify", params={"code": "1564567894562156"})
    assert r.status_code == 200
    assert "ICOM 打火机" in r.text
    assert "ICOM 官方正品防伪码" not in r.text
    assert "生产日期" in r.text
    assert "2026-02-12" in r.text
    assert "首次查询" in r.text
    assert "产品详情文字" in r.text
    assert "/uploads/products/1/x.png" in r.text
    assert "暂无推荐" in r.text
    assert r.text.index("官方推荐") < r.text.index("产品信息")
    assert "品牌溯源内容" in r.text
    assert "关于我们内容" in r.text
    assert "测标" in r.text
    assert "中国爱酷防伪中心" in r.text
    assert "爱酷，中国爱酷防伪中心" not in r.text


def test_verify_page_optional_links_render_conditionally(client_and_sessionmaker):
    client, SessionLocal = client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="LINK-P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 12), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(AntiCode(code="8181818181818181", product_id=product.id, batch_id=batch.id, scan_count=0))
        db.add_all(
            [
                PageContent(
                    key=f"product:{product.id}:brand_traceability",
                    content_json={"blocks": [{"type": "text", "text": "品牌链接文字", "link": "https://example.com/brand"}]},
                ),
                PageContent(
                    key=f"product:{product.id}:about_us",
                    content_json={"blocks": [{"type": "text", "text": "关于我们纯文字"}]},
                ),
                Recommendation(
                    product_id=product.id,
                    image_url="https://img.example/reco-no-link.png",
                    target_url="",
                    enabled=True,
                    sort_order=9,
                ),
            ]
        )
        db.commit()

    r = client.get("/verify", params={"code": "8181818181818181"})
    assert r.status_code == 200
    assert "https://example.com/brand" in r.text
    assert "https://img.example/reco-no-link.png" in r.text
    assert 'aria-label="recommendation link"' not in r.text


def test_verify_page_recommendations_support_swipe_carousel(client_and_sessionmaker):
    client, SessionLocal = client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="CAROUSEL-P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 12), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(AntiCode(code="7171717171717171", product_id=product.id, batch_id=batch.id, scan_count=0))
        db.add_all(
            [
                Recommendation(
                    product_id=product.id,
                    image_url="https://img.example/reco-1.png",
                    target_url="https://example.com/reco-1",
                    enabled=True,
                    sort_order=20,
                ),
                Recommendation(
                    product_id=product.id,
                    image_url="https://img.example/reco-2.png",
                    target_url="",
                    enabled=True,
                    sort_order=10,
                ),
            ]
        )
        db.commit()

    r = client.get("/verify", params={"code": "7171717171717171"})
    assert r.status_code == 200
    assert "https://img.example/reco-1.png" in r.text
    assert "https://img.example/reco-2.png" in r.text
    assert "v-reco-track" in r.text
    assert "v-reco-dots" in r.text
    assert "aspect-ratio: 3 / 2;" not in r.text
    assert "object-fit: cover;" not in r.text
    assert re.search(r"\.v-content-image-link,\s*\.v-content-image-box\s*\{[^}]*border-radius:\s*0;", r.text)
    assert re.search(r"\.v-reco\s*\{[^}]*border-radius:\s*0;", r.text)


def test_verify_page_multi_scan_shows_queried_text(client_and_sessionmaker):
    client, SessionLocal = client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 11), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(AntiCode(code="1555666677778888", product_id=product.id, batch_id=batch.id, scan_count=2))
        db.commit()

    r = client.get("/verify", params={"code": "1555666677778888"})
    assert r.status_code == 200
    assert "生产日期" in r.text
    assert "2026-02-11" in r.text
    assert "已被查询过" in r.text


def test_verify_page_preserves_year_precision_batch_date(client_and_sessionmaker):
    client, SessionLocal = client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="YEAR-P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date="2026", note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(AntiCode(code="4444555566667777", product_id=product.id, batch_id=batch.id, scan_count=0))
        db.commit()

    r = client.get("/verify", params={"code": "4444555566667777"})
    assert r.status_code == 200
    assert "生产日期" in r.text
    assert "2026" in r.text


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


def test_verify_page_preview_mode_does_not_track_scan(client_and_sessionmaker):
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

        db.add(AntiCode(code="2222333344445555", product_id=product.id, batch_id=batch.id, scan_count=0))
        db.commit()

    r = client.get("/verify", params={"code": "2222333344445555", "preview": "1"})
    assert r.status_code == 200
    assert "P" in r.text

    with SessionLocal() as db:
        anti = db.execute(select(AntiCode).where(AntiCode.code == "2222333344445555")).scalar_one()
        event_count = db.execute(
            select(func.count(ScanEvent.id)).where(ScanEvent.anti_code_id == anti.id)
        ).scalar_one()
        assert anti.scan_count == 0
        assert int(event_count) == 0


def test_verify_generic_page_shows_product_and_batch_info(client_and_sessionmaker):
    client, SessionLocal = client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(
            name="IMCO 6700",
            detail_text="通用页产品详情文案",
            detail_images=[{"url": "/uploads/products/generic/info.png"}],
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 27), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(
            VerifyConfig(
                show_code=False,
                warning_threshold=5,
                recent_events_limit=5,
                contact_us_url="",
                text_genuine="官方正品防伪码",
                text_not_found="未查询到该防伪码",
                text_warning="此防伪码已被多次验证，请您留意！",
            )
        )
        db.add_all(
            [
                PageContent(
                    key=f"product:{product_id}:generic_settings",
                    content_json={
                        "show_product_name": True,
                        "show_batch_date": True,
                        "generic_message": "官方正品",
                        "brand_mark": "测标通用",
                        "brand_name": "中国爱酷防伪中心",
                        "brand_sub": "AIKU CHINA VERIFICATION CENTER",
                    },
                ),
                PageContent(
                    key=f"product:{product_id}:brand_traceability",
                    content_json={"blocks": [{"type": "text", "text": "通用页品牌溯源内容"}]},
                ),
                PageContent(
                    key=f"product:{product_id}:about_us",
                    content_json={"blocks": [{"type": "text", "text": "通用页关于我们内容"}]},
                ),
            ]
        )
        db.commit()

    r = client.get("/verify/general", params={"product_id": str(product_id)})
    assert r.status_code == 200
    assert "官方正品" in r.text
    assert "防伪码" not in r.text
    assert "IMCO 6700" in r.text
    assert "生产日期" in r.text
    assert "2026-02-27" in r.text
    assert "此防伪码已验证" not in r.text
    assert "最近验证时间" not in r.text
    assert "产品信息" in r.text
    assert "通用页产品详情文案" in r.text
    assert "/uploads/products/generic/info.png" in r.text
    assert "品牌溯源" in r.text
    assert "通用页品牌溯源内容" in r.text
    assert "关于我们" in r.text
    assert "通用页关于我们内容" in r.text
    assert "官方推荐" in r.text
    assert r.text.index("官方推荐") < r.text.index("产品信息")
    assert "暂无推荐" in r.text
    assert "测标通用" in r.text
    assert "中国爱酷防伪中心" in r.text
    assert "爱酷，中国爱酷防伪中心" not in r.text
    assert "爱酷，中国爱酷" not in r.text


def test_verify_generic_page_preserves_month_precision_batch_date(client_and_sessionmaker):
    client, SessionLocal = client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="MONTH-P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

        batch = Batch(product_id=product.id, production_date="2026-02", note="")
        db.add(batch)
        db.commit()

    r = client.get("/verify/general", params={"product_id": str(product_id)})
    assert r.status_code == 200
    assert "生产日期" in r.text
    assert "2026-02" in r.text


def test_verify_generic_page_shows_recommendations_when_configured(client_and_sessionmaker):
    client, SessionLocal = client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="GEN-RECO", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 28), note="")
        db.add(batch)
        db.commit()

        db.add_all(
            [
                Recommendation(
                    product_id=product_id,
                    image_url="https://img.example/generic-reco-1.png",
                    target_url="https://example.com/generic-reco-1",
                    enabled=True,
                    sort_order=20,
                ),
                Recommendation(
                    product_id=product_id,
                    image_url="https://img.example/generic-reco-2.png",
                    target_url="",
                    enabled=True,
                    sort_order=10,
                ),
            ]
        )
        db.commit()

    r = client.get("/verify/general", params={"product_id": str(product_id)})
    assert r.status_code == 200
    assert "官方推荐" in r.text
    assert "https://img.example/generic-reco-1.png" in r.text
    assert "https://img.example/generic-reco-2.png" in r.text
    assert "v-reco-track" in r.text
    assert "v-reco-dots" in r.text
    assert "target.offsetLeft" in r.text
    assert "track.scrollLeft / w" not in r.text


def test_verify_generic_page_respects_display_switches(client_and_sessionmaker):
    client, SessionLocal = client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="NO-SHOW", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 28), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(
            VerifyConfig(
                show_code=False,
                show_product_name=False,
                show_batch_date=False,
                warning_threshold=5,
                recent_events_limit=5,
                contact_us_url="",
                text_genuine="官方正品防伪码",
                text_not_found="未查询到该防伪码",
                text_warning="此防伪码已被多次验证，请您留意！",
            )
        )
        db.commit()

    r = client.get("/verify/general", params={"product_id": str(product_id)})
    assert r.status_code == 200
    assert "NO-SHOW" not in r.text
    assert "生产日期" not in r.text
