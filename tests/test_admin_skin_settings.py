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


def test_admin_skin_settings_page_has_skin_cards_and_two_previews(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="Skin-P", detail_text="", detail_images=[])
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

    r = client.get(f"/admin/products/{product_id}/skin-settings")
    assert r.status_code == 200
    assert "皮肤设置" in r.text
    assert 'name="skin_id"' in r.text
    assert 'value="classic_red"' in r.text
    assert 'value="black_gold"' in r.text
    assert 'value="ocean_blue"' in r.text
    assert 'value="forest_green"' in r.text
    assert 'value="mist_rose"' in r.text
    assert 'value="pearl_silver"' in r.text
    assert 'value="champagne_cream"' not in r.text
    assert "选择皮肤后，下方会同时预览防伪页和通用页" in r.text
    assert 'id="skinPreviewVerifyFrame"' in r.text
    assert 'id="skinPreviewGenericFrame"' in r.text
    assert f'/verify/general?product_id={product_id}&amp;preview=1' in r.text
    assert '/verify?code=1111222233334444&amp;preview=1' in r.text


def test_admin_skin_settings_submit_persists_current_product_skin(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        p1 = Product(name="Skin-P1", detail_text="", detail_images=[])
        p2 = Product(name="Skin-P2", detail_text="", detail_images=[])
        db.add_all([p1, p2])
        db.commit()
        db.refresh(p1)
        db.refresh(p2)
        p1_id = p1.id
        p2_id = p2.id

    submit = client.post(
        f"/admin/products/{p1_id}/skin-settings",
        data={"skin_id": "black_gold"},
        follow_redirects=False,
    )
    assert submit.status_code in (302, 303)
    assert submit.headers["location"].endswith(f"/admin/products/{p1_id}/skin-settings")

    with SessionLocal() as db:
        row = db.execute(
            select(PageContent).where(PageContent.key == f"product:{p1_id}:skin_settings")
        ).scalar_one()
        assert row.content_json["skin_id"] == "black_gold"

        row2 = db.execute(
            select(PageContent).where(PageContent.key == f"product:{p2_id}:skin_settings")
        ).scalar_one_or_none()
        assert row2 is None
