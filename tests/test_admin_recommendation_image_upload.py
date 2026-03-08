from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import AntiCode, Base, Batch, Product, Recommendation


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


def test_admin_can_upload_recommendation_image(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P1", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

    r = client.post(
        f"/admin/products/{product_id}/recommendations/new",
        data={
            "target_url": "https://example.com/reco",
        },
        files={"image_file": ("reco.png", b"fake-reco-image", "image/png")},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    with SessionLocal() as db:
        rec = db.execute(select(Recommendation).order_by(Recommendation.id.desc())).scalar_one()
        assert rec.image_url.startswith("/uploads/recommendations/")
        assert rec.target_url == "https://example.com/reco"
        assert rec.sort_order == 1
        assert rec.product_id == product_id

    file_path = Path(rec.image_url.lstrip("/"))
    assert file_path.exists()


def test_admin_recommendation_target_url_is_optional(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P2", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

    r = client.post(
        f"/admin/products/{product_id}/recommendations/new",
        data={
            "target_url": "",
        },
        files={"image_file": ("reco.png", b"fake-reco-image", "image/png")},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    with SessionLocal() as db:
        rec = db.execute(select(Recommendation).order_by(Recommendation.id.desc())).scalar_one()
        assert rec.product_id == product_id
        assert rec.target_url == ""


def test_admin_recommendations_list_redirects_to_new(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P3", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

    r = client.get(f"/admin/products/{product_id}/recommendations", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"].endswith(f"/admin/products/{product_id}/recommendations/new")


def test_admin_recommendation_page_has_preview_buttons_and_hint(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P4", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

    r = client.get(f"/admin/products/{product_id}/recommendations/new")
    assert r.status_code == 200
    assert "不填则不跳转" in r.text
    assert "启用展示" not in r.text
    assert "手机整页预览：防伪页" in r.text
    assert "手机整页预览：通用页" not in r.text
    assert f'src=\"/verify/general?product_id={product_id}\"' not in r.text
    assert "暂无可用防伪码" in r.text
    assert f'href=\"/admin/products/{product_id}/batches/new\"' in r.text
    assert f'href=\"/admin/products/{product_id}/content\"' in r.text
    assert "去产品描述设置" in r.text
    assert "预览通用页" not in r.text
    assert "预览防伪页" not in r.text


def test_admin_can_move_and_delete_recommendation(admin_client_and_sessionmaker):
    client, SessionLocal = admin_client_and_sessionmaker

    with SessionLocal() as db:
        product = Product(name="P5", detail_text="", detail_images=[])
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

    first_create = client.post(
        f"/admin/products/{product_id}/recommendations/new",
        data={
            "target_url": "https://example.com/1",
        },
        files={"image_file": ("reco1.png", b"fake-reco-1", "image/png")},
        follow_redirects=False,
    )
    assert first_create.status_code in (302, 303)

    second_create = client.post(
        f"/admin/products/{product_id}/recommendations/new",
        data={
            "target_url": "https://example.com/2",
        },
        files={"image_file": ("reco2.png", b"fake-reco-2", "image/png")},
        follow_redirects=False,
    )
    assert second_create.status_code in (302, 303)

    with SessionLocal() as db:
        recs = db.execute(select(Recommendation).order_by(Recommendation.sort_order.asc())).scalars().all()
        assert len(recs) == 2
        first_id = recs[0].id
        second_id = recs[1].id
        assert recs[0].sort_order == 1
        assert recs[1].sort_order == 2

    move_up_resp = client.post(
        f"/admin/products/{product_id}/recommendations/{second_id}/move-up",
        follow_redirects=False,
    )
    assert move_up_resp.status_code in (302, 303)

    with SessionLocal() as db:
        recs = db.execute(select(Recommendation).order_by(Recommendation.sort_order.asc())).scalars().all()
        assert recs[0].id == second_id
        assert recs[1].id == first_id

    delete_resp = client.post(
        f"/admin/products/{product_id}/recommendations/{second_id}/delete",
        follow_redirects=False,
    )
    assert delete_resp.status_code in (302, 303)

    with SessionLocal() as db:
        rec = db.get(Recommendation, second_id)
        assert rec is None


def test_admin_recommendation_preview_uses_same_mode_as_mobile_scan(admin_client_and_sessionmaker):
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

        code = "7777888899990000"
        db.add(AntiCode(code=code, product_id=product.id, batch_id=batch.id))
        db.commit()

    r = client.get(f"/admin/products/{product_id}/recommendations/new")
    assert r.status_code == 200
    assert f"/verify?code={code}" in r.text
    assert "preview=1" in r.text
    assert "full=1" not in r.text
