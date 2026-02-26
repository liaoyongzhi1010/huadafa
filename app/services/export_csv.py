from __future__ import annotations

import csv
from io import StringIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AntiCode, Batch


def export_batch_codes_csv(*, db: Session, batch_id: int, base_url: str) -> str:
    batch = db.execute(select(Batch).where(Batch.id == batch_id)).scalar_one_or_none()
    if batch is None:
        return ""

    product = batch.product
    codes = (
        db.execute(select(AntiCode.code).where(AntiCode.batch_id == batch_id).order_by(AntiCode.id))
        .scalars()
        .all()
    )

    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(["product_name", "production_date", "code", "verify_url"])

    base_url = base_url.rstrip("/")
    for code in codes:
        writer.writerow(
            [
                product.name,
                batch.production_date.isoformat(),
                code,
                f"{base_url}/verify?code={code}",
            ]
        )

    return buf.getvalue()

