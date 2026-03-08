from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import Base, Batch, Product


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


def test_admin_generic_settings_page_has_editor_and_preview(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

    r = client.get(f"/admin/products/{product_id}/generic-settings")
    assert r.status_code == 200
    assert "通用页设置" in r.text
    assert "左侧设置，右侧手机整页预览" in r.text
    assert f'src="/verify/general?product_id={product_id}"' in r.text
    assert 'name="show_product_name"' in r.text
    assert 'name="show_batch_date"' in r.text
    assert 'name="generic_message"' in r.text


def test_admin_generic_settings_only_affect_current_product(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        p1 = Product(name="P1", detail_text="", detail_images=[])
        p2 = Product(name="P2", detail_text="", detail_images=[])
        db.add_all([p1, p2])
        db.commit()
        db.refresh(p1)
        db.refresh(p2)

        db.add(Batch(product_id=p1.id, production_date=date(2026, 3, 8), note=""))
        db.add(Batch(product_id=p2.id, production_date=date(2026, 3, 8), note=""))
        db.commit()
        p1_id = p1.id
        p2_id = p2.id

    submit = client.post(
        f"/admin/products/{p1_id}/generic-settings",
        data={
            "generic_message": "品牌官方正品",
        },
        follow_redirects=False,
    )
    assert submit.status_code in (302, 303)
    assert submit.headers["location"].endswith(f"/admin/products/{p1_id}/generic-settings")

    r1 = client.get("/verify/general", params={"product_id": str(p1_id)})
    assert r1.status_code == 200
    assert "品牌官方正品" in r1.text
    assert "P1" not in r1.text
    assert "生产日期" not in r1.text

    r2 = client.get("/verify/general", params={"product_id": str(p2_id)})
    assert r2.status_code == 200
    assert "官方正品" in r2.text
    assert "P2" in r2.text
    assert "生产日期" in r2.text
