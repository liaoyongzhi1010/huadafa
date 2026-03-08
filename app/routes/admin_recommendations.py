from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_db
from app.models import AntiCode, Batch, Product, Recommendation
from app.services.uploads import save_recommendation_image
from app.web import templates

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return None


@router.get("/recommendations")
def recommendations_list_legacy(request: Request):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)


def _new_form_context(
    *,
    product: Product,
    recs: list[Recommendation],
    preview_verify_url: str,
    error: str = "",
    image_url: str = "",
    target_url: str = "",
    sort_order: str = "0",
) -> dict[str, object]:
    return {
        "product": product,
        "recs": recs,
        "active_tab": "recommendations",
        "error": error,
        "image_url": image_url,
        "target_url": target_url,
        "sort_order": sort_order,
        "preview_verify_url": preview_verify_url,
    }


def _load_product_or_redirect(db: Session, product_id: int) -> Product | None:
    return db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()


def _load_recommendation_for_product(db: Session, *, product_id: int, rec_id: int) -> Recommendation | None:
    return db.execute(
        select(Recommendation).where(
            Recommendation.id == rec_id,
            Recommendation.product_id == product_id,
        )
    ).scalar_one_or_none()


def _ordered_recommendations(db: Session, *, product_id: int) -> list[Recommendation]:
    return (
        db.execute(
            select(Recommendation)
            .where(Recommendation.product_id == product_id)
            .order_by(Recommendation.sort_order.asc(), Recommendation.id.asc())
        )
        .scalars()
        .all()
    )


def _normalize_recommendation_order(db: Session, *, product_id: int) -> list[Recommendation]:
    recs = _ordered_recommendations(db, product_id=product_id)
    changed = False
    for idx, rec in enumerate(recs, start=1):
        if rec.sort_order != idx:
            rec.sort_order = idx
            db.add(rec)
            changed = True
    if changed:
        db.commit()
        recs = _ordered_recommendations(db, product_id=product_id)
    return recs


def _pick_random_active_code_for_product(db: Session, *, product_id: int) -> str | None:
    return db.execute(
        select(AntiCode.code)
        .join(Batch, Batch.id == AntiCode.batch_id)
        .where(
            AntiCode.product_id == product_id,
            AntiCode.status == "active",
            Batch.status == "active",
        )
        .order_by(func.random())
        .limit(1)
    ).scalar_one_or_none()


@router.get("/recommendations/new")
def recommendation_new_page_legacy(request: Request):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)


@router.get("/products/{product_id}/recommendations")
def product_recommendations_list(request: Request, product_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    return RedirectResponse(url=f"/admin/products/{product_id}/recommendations/new", status_code=HTTP_303_SEE_OTHER)


@router.get("/products/{product_id}/recommendations/new")
def recommendation_new_page(request: Request, product_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    product = _load_product_or_redirect(db, product_id)
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)
    recs = _normalize_recommendation_order(db, product_id=product_id)
    preview_code = _pick_random_active_code_for_product(db, product_id=product_id)
    preview_verify_url = f"/verify?code={preview_code}&preview=1" if preview_code else ""
    return templates.TemplateResponse(
        request,
        "admin/recommendation_new.html",
        _new_form_context(product=product, recs=recs, preview_verify_url=preview_verify_url),
    )


@router.post("/recommendations/new")
def recommendation_new_submit_legacy(request: Request):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)


@router.post("/products/{product_id}/recommendations/new")
def recommendation_new_submit(
    request: Request,
    product_id: int,
    image_url: str = Form(""),
    image_file: UploadFile | None = File(None),
    target_url: str = Form(""),
    sort_order: str = Form("0"),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    product = _load_product_or_redirect(db, product_id)
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    recs = (
        _normalize_recommendation_order(db, product_id=product_id)
    )
    preview_code = _pick_random_active_code_for_product(db, product_id=product_id)
    preview_verify_url = f"/verify?code={preview_code}&preview=1" if preview_code else ""

    image_url = image_url.strip()
    if image_file is not None and image_file.filename:
        image_url = save_recommendation_image(upload=image_file)

    target_url = target_url.strip()
    if not image_url:
        return templates.TemplateResponse(
            request,
            "admin/recommendation_new.html",
            _new_form_context(
                product=product,
                recs=recs,
                preview_verify_url=preview_verify_url,
                error="推荐图片不能为空",
                image_url=image_url,
                target_url=target_url,
                sort_order=sort_order,
            ),
            status_code=200,
        )

    max_order = (
        db.execute(select(func.max(Recommendation.sort_order)).where(Recommendation.product_id == product_id))
        .scalar_one_or_none()
    )
    order = int(max_order or 0) + 1

    db.add(
        Recommendation(
            product_id=product_id,
            image_url=image_url,
            target_url=target_url,
            enabled=True,
            sort_order=order,
        )
    )
    db.commit()
    return RedirectResponse(url=f"/admin/products/{product_id}/recommendations/new", status_code=HTTP_303_SEE_OTHER)


@router.post("/products/{product_id}/recommendations/{rec_id}/update")
def recommendation_update_submit(
    request: Request,
    product_id: int,
    rec_id: int,
    target_url: str = Form(""),
    sort_order: str = Form("0"),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = _load_product_or_redirect(db, product_id)
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    rec = _load_recommendation_for_product(db, product_id=product_id, rec_id=rec_id)
    if rec is None:
        return RedirectResponse(url=f"/admin/products/{product_id}/recommendations/new", status_code=HTTP_303_SEE_OTHER)

    rec.target_url = target_url.strip()
    try:
        rec.sort_order = int(sort_order)
    except ValueError:
        rec.sort_order = 0
    rec.enabled = True
    db.add(rec)
    db.commit()
    return RedirectResponse(url=f"/admin/products/{product_id}/recommendations/new", status_code=HTTP_303_SEE_OTHER)


@router.post("/products/{product_id}/recommendations/{rec_id}/move-up")
def recommendation_move_up_submit(request: Request, product_id: int, rec_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    recs = _normalize_recommendation_order(db, product_id=product_id)
    idx_map = {r.id: i for i, r in enumerate(recs)}
    idx = idx_map.get(rec_id)
    if idx is None or idx <= 0:
        return RedirectResponse(url=f"/admin/products/{product_id}/recommendations/new", status_code=HTTP_303_SEE_OTHER)

    current = recs[idx]
    previous = recs[idx - 1]
    current.sort_order, previous.sort_order = previous.sort_order, current.sort_order
    db.add_all([current, previous])
    db.commit()
    return RedirectResponse(url=f"/admin/products/{product_id}/recommendations/new", status_code=HTTP_303_SEE_OTHER)


@router.post("/products/{product_id}/recommendations/{rec_id}/move-down")
def recommendation_move_down_submit(request: Request, product_id: int, rec_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    recs = _normalize_recommendation_order(db, product_id=product_id)
    idx_map = {r.id: i for i, r in enumerate(recs)}
    idx = idx_map.get(rec_id)
    if idx is None or idx >= len(recs) - 1:
        return RedirectResponse(url=f"/admin/products/{product_id}/recommendations/new", status_code=HTTP_303_SEE_OTHER)

    current = recs[idx]
    nxt = recs[idx + 1]
    current.sort_order, nxt.sort_order = nxt.sort_order, current.sort_order
    db.add_all([current, nxt])
    db.commit()
    return RedirectResponse(url=f"/admin/products/{product_id}/recommendations/new", status_code=HTTP_303_SEE_OTHER)


@router.post("/products/{product_id}/recommendations/{rec_id}/delete")
def recommendation_delete_submit(request: Request, product_id: int, rec_id: int, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    rec = _load_recommendation_for_product(db, product_id=product_id, rec_id=rec_id)
    if rec is None:
        return RedirectResponse(url=f"/admin/products/{product_id}/recommendations/new", status_code=HTTP_303_SEE_OTHER)

    db.delete(rec)
    db.commit()
    return RedirectResponse(url=f"/admin/products/{product_id}/recommendations/new", status_code=HTTP_303_SEE_OTHER)
