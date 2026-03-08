from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.paths import UPLOADS_DIR

_ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _pick_ext(upload: UploadFile) -> str:
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTS:
        return ".bin"
    return ext


def _save_upload(*, upload: UploadFile, dir_path: Path, url_prefix: str) -> str:
    ext = _pick_ext(upload)
    filename = f"{uuid.uuid4().hex}{ext}"
    dir_path.mkdir(parents=True, exist_ok=True)

    file_path = dir_path / filename
    with file_path.open("wb") as f:
        shutil.copyfileobj(upload.file, f)

    return f"{url_prefix}/{filename}"


def save_product_detail_image(
    *,
    product_id: int,
    upload: UploadFile,
    upload_root: Path = UPLOADS_DIR,
) -> str:
    return _save_upload(
        upload=upload,
        dir_path=upload_root / "products" / str(product_id),
        url_prefix=f"/uploads/products/{product_id}",
    )


def save_recommendation_image(*, upload: UploadFile, upload_root: Path = UPLOADS_DIR) -> str:
    return _save_upload(
        upload=upload,
        dir_path=upload_root / "recommendations",
        url_prefix="/uploads/recommendations",
    )


def save_page_content_image(
    *,
    section: str,
    upload: UploadFile,
    upload_root: Path = UPLOADS_DIR,
) -> str:
    safe_section = section.strip().lower() or "misc"
    return _save_upload(
        upload=upload,
        dir_path=upload_root / "content" / safe_section,
        url_prefix=f"/uploads/content/{safe_section}",
    )
