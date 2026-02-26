from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import Base, Product


@pytest.fixture()
def admin_client_and_sessionmaker(tmp_path: Path):
    old_cwd = Path.cwd()
    os.chdir(tmp_path)

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
        yield client, TestingSessionLocal, tmp_path
    finally:
        app.dependency_overrides.clear()
        os.chdir(old_cwd)


def test_admin_can_upload_product_detail_images(admin_client_and_sessionmaker):
    client, SessionLocal, tmp_path = admin_client_and_sessionmaker

    client.post("/admin/products/new", data={"name": "ICOM", "detail_text": "T"})

    with SessionLocal() as db:
        product = db.execute(select(Product).where(Product.name == "ICOM")).scalar_one()
        product_id = product.id

    files = [
        ("detail_images", ("a.png", b"fakepng", "image/png")),
        ("detail_images", ("b.jpg", b"fakejpg", "image/jpeg")),
    ]
    r = client.post(
        f"/admin/products/{product_id}/edit",
        data={"name": "ICOM", "detail_text": "T2"},
        files=files,
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    with SessionLocal() as db:
        product = db.get(Product, product_id)
        assert product is not None
        assert product.detail_text == "T2"
        assert len(product.detail_images) == 2
        assert all(img.get("url", "").startswith("/uploads/") for img in product.detail_images)

    # Files are saved under uploads/
    upload_dir = tmp_path / "uploads"
    assert upload_dir.exists()
