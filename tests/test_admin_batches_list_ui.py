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


def test_batches_list_has_no_generate_column(admin_client_and_sessionmaker):
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

        db.add(AntiCode(code="1234567890123456", product_id=product.id, batch_id=batch.id, scan_count=0))
        db.commit()

        batch_id = batch.id

    r = client.get(f"/admin/products/{product_id}/batches")
    assert r.status_code == 200
    assert "生成防伪码" not in r.text
    assert "/codes/generate" not in r.text
    assert f"/admin/batches/{batch_id}/export/csv" in r.text
    assert f"/admin/products/{product_id}/export/generic-qrcode.png" in r.text
    assert "页面设置" in r.text
    assert f'href="/admin/products/{product_id}/content"' in r.text
    assert "商品推荐" not in r.text
    assert f'href="/admin/products/{product_id}/generic-settings"' in r.text
    assert "通用页设置" in r.text
    assert f'href="/admin/products/{product_id}/verify-page-settings"' in r.text
    assert "防伪设置" in r.text
    assert f'href="/admin/products/{product_id}/contact-settings"' in r.text
    assert "联系我们设置" in r.text
    assert "预览防伪页" not in r.text
    assert "预览通用页" not in r.text
    assert "新建批次" not in r.text
    assert (
        r.text.index("批次")
        < r.text.index("页面设置")
        < r.text.index("防伪设置")
        < r.text.index("通用页设置")
        < r.text.index("联系我们设置")
        < r.text.index("返回产品列表")
    )
