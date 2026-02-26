from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import Base


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
        r = client.post("/admin/login", data={"username": "admin", "password": "admin"})
        assert r.status_code in (200, 302, 303)
        yield client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()


def test_admin_products_page_and_create(admin_client_and_sessionmaker):
    client, _ = admin_client_and_sessionmaker

    r = client.get("/admin/products")
    assert r.status_code == 200

    r2 = client.post("/admin/products/new", data={"name": "ICOM 打火机", "detail_text": ""})
    assert r2.status_code in (200, 302, 303)

    r3 = client.get("/admin/products")
    assert r3.status_code == 200
    assert "ICOM 打火机" in r3.text

