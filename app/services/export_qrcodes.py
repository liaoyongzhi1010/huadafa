from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import qrcode
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AntiCode, Batch, Product


def export_batch_qrcodes_zip(*, db: Session, batch_id: int, base_url: str) -> bytes:
    batch = db.execute(select(Batch).where(Batch.id == batch_id)).scalar_one_or_none()
    if batch is None:
        return b""

    codes = (
        db.execute(select(AntiCode.code).where(AntiCode.batch_id == batch_id).order_by(AntiCode.id))
        .scalars()
        .all()
    )

    base_url = base_url.rstrip("/")
    out = BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as zf:
        for code in codes:
            url = f"{base_url}/verify?code={code}"
            img = qrcode.make(url)
            buf = BytesIO()
            img.save(buf, format="PNG")
            zf.writestr(f"{code}.png", buf.getvalue())
    return out.getvalue()


def export_product_generic_qrcode_png(*, db: Session, product_id: int, base_url: str) -> bytes:
    product = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
    if product is None:
        return b""

    base_url = base_url.rstrip("/")
    url = f"{base_url}/verify/general?product_id={product_id}"
    img = qrcode.make(url)
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
