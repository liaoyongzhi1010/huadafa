from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str
    admin_username: str
    admin_password: str
    secret_key: str
    base_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite+pysqlite:///./dev.db"),
        admin_username=os.getenv("ADMIN_USERNAME", "admin"),
        admin_password=os.getenv("ADMIN_PASSWORD", "admin"),
        secret_key=os.getenv("SECRET_KEY", "dev-secret"),
        base_url=os.getenv("BASE_URL", "http://127.0.0.1:8000"),
    )

