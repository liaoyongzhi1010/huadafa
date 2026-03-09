from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import AntiCode, Base, Batch, PageContent, Product


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


def test_verify_page_settings_page_shows_visibility_checkboxes(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)

        batch = Batch(product_id=product.id, production_date=date(2026, 3, 10), note="")
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(AntiCode(code="1111222233334444", product_id=product.id, batch_id=batch.id))
        db.commit()

        product_id = product.id

    r = client.get(f"/admin/products/{product_id}/verify-page-settings")
    assert r.status_code == 200
    assert 'name="hide_result_product_name"' in r.text
    assert 'name="hide_batch_date"' in r.text
    assert 'name="hide_recent_events"' in r.text
    assert 'name="hide_recommendations"' in r.text
    assert 'name="hide_product_info"' in r.text
    assert 'name="hide_brand_traceability"' in r.text
    assert 'name="hide_about_us"' in r.text
    assert 'id="verifyPreviewFrame"' in r.text


def test_verify_page_settings_submit_persists_visibility_flags(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

    r = client.post(
        f"/admin/products/{product_id}/verify-page-settings",
        data={
            "hide_batch_date": "on",
            "hide_product_info": "on",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    with SessionLocal() as db:
        row = db.execute(
            select(PageContent).where(PageContent.key == f"product:{product_id}:verify_page_settings")
        ).scalar_one()
        assert row.content_json["show_batch_date"] is False
        assert row.content_json["show_product_info"] is False
        assert row.content_json["show_recent_events"] is True
