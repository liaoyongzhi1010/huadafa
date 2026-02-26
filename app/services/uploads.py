from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.paths import UPLOADS_DIR

_ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def save_product_detail_image(
    *,
    product_id: int,
    upload: UploadFile,
    upload_root: Path = UPLOADS_DIR,
) -> str:
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTS:
        ext = ".bin"

    filename = f"{uuid.uuid4().hex}{ext}"
    dir_path = upload_root / "products" / str(product_id)
    dir_path.mkdir(parents=True, exist_ok=True)

    file_path = dir_path / filename
    with file_path.open("wb") as f:
        shutil.copyfileobj(upload.file, f)

    return f"/uploads/products/{product_id}/{filename}"
