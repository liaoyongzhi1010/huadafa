from __future__ import annotations

import json
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
        product_id = product.id

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 12), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(AntiCode(code="4444555566667777", product_id=product.id, batch_id=batch.id))
        db.commit()

    r = client.post(
        f"/admin/products/{product_id}/content",
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


def test_admin_content_supports_mixed_text_and_uploaded_images(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P2", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 12), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(AntiCode(code="2222333344445555", product_id=product.id, batch_id=batch.id))
        db.commit()

    files = [
        ("brand_images", ("brand.png", b"brand-image", "image/png")),
        ("about_images", ("about.jpg", b"about-image", "image/jpeg")),
    ]
    r = client.post(
        f"/admin/products/{product_id}/content",
        data={
            "brand_text": "品牌图文",
            "about_text": "关于图文",
        },
        files=files,
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    r2 = client.get("/api/public/verify", params={"code": "2222333344445555"})
    assert r2.status_code == 200
    data = r2.json()

    brand_blocks = data["page_content"]["brand_traceability"]["blocks"]
    about_blocks = data["page_content"]["about_us"]["blocks"]
    assert brand_blocks[0]["type"] == "text"
    assert brand_blocks[0]["text"] == "品牌图文"
    assert any(b.get("type") == "image" and b.get("url", "").startswith("/uploads/content/") for b in brand_blocks)
    assert about_blocks[0]["type"] == "text"
    assert about_blocks[0]["text"] == "关于图文"
    assert any(b.get("type") == "image" and b.get("url", "").startswith("/uploads/content/") for b in about_blocks)


def test_admin_content_supports_free_order_mixed_blocks(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P3", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 12), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(AntiCode(code="3333555577779999", product_id=product.id, batch_id=batch.id))
        db.commit()

    brand_blocks = [
        {"type": "text", "text": "第一段"},
        {"type": "image_upload"},
        {"type": "text", "text": "第二段"},
    ]

    r = client.post(
        f"/admin/products/{product_id}/content",
        data={
            "brand_text": "",
            "about_text": "",
            "brand_blocks_json": json.dumps(brand_blocks, ensure_ascii=False),
            "about_blocks_json": json.dumps([], ensure_ascii=False),
        },
        files=[("brand_images", ("mix.png", b"brand-mix-image", "image/png"))],
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    r2 = client.get("/api/public/verify", params={"code": "3333555577779999"})
    assert r2.status_code == 200
    data = r2.json()
    got = data["page_content"]["brand_traceability"]["blocks"]
    assert [x["type"] for x in got] == ["text", "image", "text"]
    assert got[0]["text"] == "第一段"
    assert got[1]["url"].startswith("/uploads/content/")
    assert got[2]["text"] == "第二段"


def test_admin_content_page_has_preview_buttons_and_link_hint(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P5", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

    r = client.get(f"/admin/products/{product_id}/content")
    assert r.status_code == 200
    assert "防伪页面设置" in r.text
    assert "产品信息" in r.text
    assert "品牌溯源" in r.text
    assert "关于我们" in r.text
    assert "新增栏目" in r.text
    assert "重置恢复默认模版" in r.text
    assert "点击上面文字可跳转" in r.text
    assert "点击上面图片可跳转" in r.text
    assert "手机整页预览：防伪页" in r.text
    assert "手机整页预览：通用页" not in r.text
    assert f'src=\"/verify/general?product_id={product_id}\"' not in r.text
    assert "暂无可用防伪码" in r.text
    assert f'href=\"/admin/products/{product_id}/batches/new\"' in r.text
    assert f'href=\"/admin/products/{product_id}/recommendations/new\"' in r.text
    assert "去商品推荐设置" in r.text
    assert "返回仪表盘" not in r.text


def test_admin_content_can_add_and_delete_verify_section_buttons(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="PX", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

        batch = Batch(product_id=product.id, production_date=date(2026, 3, 8), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(AntiCode(code="9090909090909090", product_id=product.id, batch_id=batch.id))
        db.commit()

    add_resp = client.post(
        f"/admin/products/{product_id}/content",
        data={
            "action": "add_section",
            "new_section_title": "使用教程",
            "active_section_id": "brand_traceability",
        },
        follow_redirects=False,
    )
    assert add_resp.status_code in (302, 303)
    assert add_resp.headers["location"].endswith(f"/admin/products/{product_id}/content?section=brand_traceability")

    r1 = client.get(f"/admin/products/{product_id}/content")
    assert r1.status_code == 200
    assert "使用教程" in r1.text
    assert r1.text.index("关于我们") < r1.text.index("使用教程")
    assert "确认删除这个栏目" in r1.text

    del_resp = client.post(
        f"/admin/products/{product_id}/content",
        data={
            "action": "delete_section",
            "delete_section_id": "brand_traceability",
        },
        follow_redirects=False,
    )
    assert del_resp.status_code in (302, 303)

    r2 = client.get("/verify", params={"code": "9090909090909090", "preview": "1"})
    assert r2.status_code == 200
    assert "品牌溯源" not in r2.text
    assert "使用教程" in r2.text

    restore_resp = client.post(
        f"/admin/products/{product_id}/content",
        data={
            "action": "restore_default_sections",
            "active_section_id": "about_us",
        },
        follow_redirects=False,
    )
    assert restore_resp.status_code in (302, 303)
    assert restore_resp.headers["location"].endswith(f"/admin/products/{product_id}/content?section=about_us")

    r3 = client.get(f"/admin/products/{product_id}/content")
    assert r3.status_code == 200
    assert "产品信息" in r3.text
    assert "品牌溯源" in r3.text
    assert "关于我们" in r3.text
    assert "使用教程" in r3.text
    assert (
        r3.text.index("产品信息")
        < r3.text.index("品牌溯源")
        < r3.text.index("关于我们")
        < r3.text.index("使用教程")
    )


def test_admin_content_blocks_support_optional_hyperlinks(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P4", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

        batch = Batch(product_id=product.id, production_date=date(2026, 2, 12), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(AntiCode(code="1234123412341234", product_id=product.id, batch_id=batch.id))
        db.commit()

    brand_blocks = [
        {"type": "text", "text": "带链接文字", "link": "https://example.com/brand"},
    ]
    about_blocks = [
        {"type": "text", "text": "无链接文字"},
    ]

    r = client.post(
        f"/admin/products/{product_id}/content",
        data={
            "brand_blocks_json": json.dumps(brand_blocks, ensure_ascii=False),
            "about_blocks_json": json.dumps(about_blocks, ensure_ascii=False),
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    r2 = client.get("/api/public/verify", params={"code": "1234123412341234"})
    assert r2.status_code == 200
    data = r2.json()

    saved_brand = data["page_content"]["brand_traceability"]["blocks"]
    saved_about = data["page_content"]["about_us"]["blocks"]
    assert saved_brand[0]["text"] == "带链接文字"
    assert saved_brand[0]["link"] == "https://example.com/brand"
    assert saved_about[0]["text"] == "无链接文字"
    assert "link" not in saved_about[0]


def test_admin_content_preview_uses_same_mode_as_mobile_scan(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P6", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

        batch = Batch(product_id=product.id, production_date=date(2026, 3, 8), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        code = "6666777788889999"
        db.add(AntiCode(code=code, product_id=product.id, batch_id=batch.id))
        db.commit()

    r = client.get(f"/admin/products/{product_id}/content")
    assert r.status_code == 200
    assert f"/verify?code={code}" in r.text
    assert "preview=1" in r.text
    assert "full=1" not in r.text
