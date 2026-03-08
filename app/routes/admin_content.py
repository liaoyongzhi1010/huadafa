from __future__ import annotations

import json
import re
import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.db import get_db
from app.models import AntiCode, Batch, PageContent, Product
from app.services.uploads import save_page_content_image
from app.web import templates

router = APIRouter(prefix="/admin", tags=["admin"])

_SECTION_ID_RE = re.compile(r"^[a-z0-9_]{1,64}$")
_DEFAULT_VERIFY_SECTIONS: list[dict[str, str]] = [
    {"id": "product_info", "title": "产品信息"},
    {"id": "brand_traceability", "title": "品牌溯源"},
    {"id": "about_us", "title": "关于我们"},
]
_BUILTIN_SECTION_IDS = {"product_info", "brand_traceability", "about_us"}
_BUILTIN_TITLE_TO_ID = {
    "产品信息": "product_info",
    "品牌溯源": "brand_traceability",
    "关于我们": "about_us",
}
_DEFAULT_VERIFY_PAGE_SETTINGS: dict[str, str] = {
    "brand_mark": "爱酷",
    "brand_name": "中国爱酷防伪中心",
    "brand_sub": "AIKU CHINA VERIFICATION CENTER",
}


def _require_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return None


def _content_storage_key(*, product_id: int, key: str) -> str:
    return f"product:{product_id}:{key}"


def _verify_sections_storage_key(*, product_id: int) -> str:
    return _content_storage_key(product_id=product_id, key="verify_sections")


def _verify_page_settings_storage_key(*, product_id: int) -> str:
    return _content_storage_key(product_id=product_id, key="verify_page_settings")


def _section_content_key(*, section_id: str) -> str:
    if section_id in _BUILTIN_SECTION_IDS:
        return section_id
    return f"section:{section_id}"


def _copy_default_sections() -> list[dict[str, str]]:
    return [{"id": s["id"], "title": s["title"]} for s in _DEFAULT_VERIFY_SECTIONS]


def _restore_default_sections(sections: list[dict[str, str]]) -> list[dict[str, str]]:
    custom_sections = [s for s in sections if s["id"] not in _BUILTIN_SECTION_IDS]
    return _copy_default_sections() + custom_sections


def _normalize_blocks(payload: object) -> list[dict[str, str]]:
    if not isinstance(payload, dict):
        return []

    blocks_raw = payload.get("blocks")
    if isinstance(blocks_raw, list):
        blocks: list[dict[str, str]] = []
        for item in blocks_raw:
            if not isinstance(item, dict):
                continue
            t = str(item.get("type", "")).strip().lower()
            link = str(item.get("link", "")).strip()
            if t == "text":
                text = str(item.get("text", "")).strip()
                if text:
                    block: dict[str, str] = {"type": "text", "text": text}
                    if link:
                        block["link"] = link
                    blocks.append(block)
            elif t == "image":
                url = str(item.get("url", "")).strip()
                if url:
                    block = {"type": "image", "url": url}
                    if link:
                        block["link"] = link
                    blocks.append(block)
        if blocks:
            return blocks

    legacy_text = str(payload.get("text", "")).strip()
    if legacy_text:
        return [{"type": "text", "text": legacy_text}]
    return []


def _normalize_sections(payload: object) -> list[dict[str, str]]:
    if not isinstance(payload, dict):
        return []

    sections_raw = payload.get("sections")
    if not isinstance(sections_raw, list):
        return []

    sections: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in sections_raw:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("id", "")).strip().lower()
        title = str(item.get("title", "")).strip()
        if not sid or not title:
            continue
        if not _SECTION_ID_RE.match(sid):
            continue
        if sid in seen:
            continue
        seen.add(sid)
        sections.append({"id": sid, "title": title})
    return sections


def _load_verify_sections(db: Session, *, product_id: int) -> list[dict[str, str]]:
    storage_key = _verify_sections_storage_key(product_id=product_id)
    pc = db.execute(select(PageContent).where(PageContent.key == storage_key)).scalar_one_or_none()
    if pc is None:
        return _copy_default_sections()

    content_json = pc.content_json if isinstance(pc.content_json, dict) else {}
    sections = _normalize_sections(content_json)
    if not sections:
        return _copy_default_sections()
    return sections


def _save_verify_sections(db: Session, *, product_id: int, sections: list[dict[str, str]]) -> None:
    storage_key = _verify_sections_storage_key(product_id=product_id)
    pc = db.execute(select(PageContent).where(PageContent.key == storage_key)).scalar_one_or_none()
    payload = {"sections": sections}
    if pc is None:
        pc = PageContent(key=storage_key, content_json=payload)
    else:
        pc.content_json = payload
    db.add(pc)


def _load_verify_page_settings(db: Session, *, product_id: int) -> dict[str, str]:
    settings = dict(_DEFAULT_VERIFY_PAGE_SETTINGS)
    storage_key = _verify_page_settings_storage_key(product_id=product_id)
    pc = db.execute(select(PageContent).where(PageContent.key == storage_key)).scalar_one_or_none()
    if pc is None or not isinstance(pc.content_json, dict):
        return settings

    payload = pc.content_json
    for key in ("brand_mark", "brand_name", "brand_sub"):
        value = str(payload.get(key, "")).strip()
        if value:
            settings[key] = value
    return settings


def _save_verify_page_settings(db: Session, *, product_id: int, settings: dict[str, str]) -> None:
    payload = {
        "brand_mark": str(settings.get("brand_mark", "")).strip() or _DEFAULT_VERIFY_PAGE_SETTINGS["brand_mark"],
        "brand_name": str(settings.get("brand_name", "")).strip() or _DEFAULT_VERIFY_PAGE_SETTINGS["brand_name"],
        "brand_sub": str(settings.get("brand_sub", "")).strip() or _DEFAULT_VERIFY_PAGE_SETTINGS["brand_sub"],
    }
    storage_key = _verify_page_settings_storage_key(product_id=product_id)
    pc = db.execute(select(PageContent).where(PageContent.key == storage_key)).scalar_one_or_none()
    if pc is None:
        pc = PageContent(key=storage_key, content_json=payload)
    else:
        existing = pc.content_json if isinstance(pc.content_json, dict) else {}
        merged = dict(existing)
        merged.update(payload)
        pc.content_json = merged
    db.add(pc)


def _pick_active_section_id(sections: list[dict[str, str]], requested: str | None) -> str:
    if sections:
        default_id = sections[0]["id"]
    else:
        return "product_info"
    if not requested:
        return default_id
    req = requested.strip().lower()
    if req in {s["id"] for s in sections}:
        return req
    return default_id


def _make_section_id_from_title(title: str, *, existing_ids: set[str]) -> str:
    builtin_id = _BUILTIN_TITLE_TO_ID.get(title.strip())
    if builtin_id and builtin_id not in existing_ids:
        return builtin_id

    slug = re.sub(r"[^a-z0-9_]+", "_", title.strip().lower()).strip("_")
    if not slug:
        slug = f"section_{uuid.uuid4().hex[:6]}"
    candidate = slug
    i = 1
    while candidate in existing_ids:
        candidate = f"{slug}_{i}"
        i += 1
    return candidate


def _insert_section_after_about_us(
    sections: list[dict[str, str]],
    *,
    new_section: dict[str, str],
) -> list[dict[str, str]]:
    for idx, section in enumerate(sections):
        if section["id"] == "about_us":
            return sections[: idx + 1] + [new_section] + sections[idx + 1 :]
    return sections + [new_section]


def _get_content(db: Session, *, product_id: int, key: str) -> dict[str, object]:
    storage_key = _content_storage_key(product_id=product_id, key=key)
    pc = db.execute(select(PageContent).where(PageContent.key == storage_key)).scalar_one_or_none()
    if pc is None:
        return {"text": "", "blocks": []}

    content_json = pc.content_json if isinstance(pc.content_json, dict) else {}
    blocks = _normalize_blocks(content_json)
    text = ""
    for block in blocks:
        if block.get("type") == "text":
            text = str(block.get("text", ""))
            break
    if not text:
        text = str(content_json.get("text", ""))
    return {"text": text, "blocks": blocks}


def _legacy_product_info_blocks(product: Product) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    text = str(product.detail_text or "").strip()
    if text:
        blocks.append({"type": "text", "text": text})

    for img in list(product.detail_images or []):
        if not isinstance(img, dict):
            continue
        url = str(img.get("url", "")).strip()
        if url:
            blocks.append({"type": "image", "url": url})
    return blocks


def _get_section_content(db: Session, *, product: Product, section_id: str) -> dict[str, object]:
    key = _section_content_key(section_id=section_id)
    content = _get_content(db, product_id=product.id, key=key)
    if section_id == "product_info" and not content["blocks"]:
        blocks = _legacy_product_info_blocks(product)
        text = ""
        for block in blocks:
            if block.get("type") == "text":
                text = str(block.get("text", ""))
                break
        return {"text": text, "blocks": blocks}
    return content


def _set_blocks_content(db: Session, *, product_id: int, key: str, blocks: list[dict[str, str]]) -> None:
    cleaned_blocks = _normalize_blocks({"blocks": blocks})
    primary_text = ""
    for block in cleaned_blocks:
        if block.get("type") == "text":
            primary_text = str(block.get("text", "")).strip()
            if primary_text:
                break

    payload = {"text": primary_text, "blocks": cleaned_blocks}
    storage_key = _content_storage_key(product_id=product_id, key=key)
    pc = db.execute(select(PageContent).where(PageContent.key == storage_key)).scalar_one_or_none()
    if pc is None:
        pc = PageContent(key=storage_key, content_json=payload)
    else:
        pc.content_json = payload
    db.add(pc)


def _delete_content_by_key(db: Session, *, product_id: int, key: str) -> None:
    storage_key = _content_storage_key(product_id=product_id, key=key)
    pc = db.execute(select(PageContent).where(PageContent.key == storage_key)).scalar_one_or_none()
    if pc is not None:
        db.delete(pc)


def _parse_blocks_json(raw: str) -> list[dict[str, str]]:
    s = (raw or "").strip()
    if not s:
        return []
    try:
        payload = json.loads(s)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _build_blocks(
    *,
    raw_blocks: list[dict[str, str]],
    uploaded_images: list[UploadFile],
    section: str,
) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    upload_queue = [u for u in uploaded_images if u.filename]
    upload_idx = 0

    for item in raw_blocks:
        t = str(item.get("type", "")).strip().lower()
        link = str(item.get("link", "")).strip()
        if t == "text":
            text = str(item.get("text", "")).strip()
            if text:
                block: dict[str, str] = {"type": "text", "text": text}
                if link:
                    block["link"] = link
                blocks.append(block)
            continue

        if t == "image":
            url = str(item.get("url", "")).strip()
            if url:
                block = {"type": "image", "url": url}
                if link:
                    block["link"] = link
                blocks.append(block)
            continue

        if t == "image_upload":
            if upload_idx >= len(upload_queue):
                continue
            upload = upload_queue[upload_idx]
            upload_idx += 1
            url = save_page_content_image(section=section, upload=upload)
            block = {"type": "image", "url": url}
            if link:
                block["link"] = link
            blocks.append(block)

    return blocks


def _sync_product_detail_from_blocks(product: Product, blocks: list[dict[str, str]]) -> None:
    detail_text = ""
    detail_images: list[dict[str, str]] = []
    for block in blocks:
        t = str(block.get("type", "")).strip().lower()
        if t == "text" and not detail_text:
            detail_text = str(block.get("text", "")).strip()
        elif t == "image":
            url = str(block.get("url", "")).strip()
            if url:
                detail_images.append({"url": url})
    product.detail_text = detail_text
    product.detail_images = detail_images


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


def _render_content_edit_page(request: Request, *, product: Product, db: Session, active_section_id: str):
    sections = _load_verify_sections(db, product_id=product.id)
    active_section_id = _pick_active_section_id(sections, active_section_id)
    active_section = next((s for s in sections if s["id"] == active_section_id), sections[0])
    active_content = _get_section_content(db, product=product, section_id=active_section_id)
    verify_page_settings = _load_verify_page_settings(db, product_id=product.id)
    preview_code = _pick_random_active_code_for_product(db, product_id=product.id)
    preview_verify_url = f"/verify?code={preview_code}&preview=1" if preview_code else ""

    return templates.TemplateResponse(
        request,
        "admin/content_edit.html",
        {
            "product": product,
            "active_tab": "content",
            "sections": sections,
            "active_section_id": active_section_id,
            "active_section_title": active_section["title"],
            "active_blocks": active_content["blocks"],
            "preview_verify_url": preview_verify_url,
            "verify_brand_mark": verify_page_settings["brand_mark"],
            "verify_brand_name": verify_page_settings["brand_name"],
            "verify_brand_sub": verify_page_settings["brand_sub"],
        },
    )


@router.get("/content")
def content_page_legacy(request: Request):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)


@router.get("/products/{product_id}/content")
def product_content_page(request: Request, product_id: int, section: str | None = None, db: Session = Depends(get_db)):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    return _render_content_edit_page(request, product=product, db=db, active_section_id=section or "")


@router.post("/products/{product_id}/content")
def product_content_submit(
    request: Request,
    product_id: int,
    action: str = Form("legacy"),
    active_section_id: str = Form(""),
    section_blocks_json: str = Form(""),
    brand_mark: str = Form(""),
    brand_name: str = Form(""),
    brand_sub: str = Form(""),
    new_section_title: str = Form(""),
    delete_section_id: str = Form(""),
    section_images: list[UploadFile] = File(default_factory=list),
    # legacy fields (compatibility for existing tests/old forms)
    brand_text: str = Form(""),
    about_text: str = Form(""),
    brand_blocks_json: str = Form(""),
    about_blocks_json: str = Form(""),
    clear_brand_images: str | None = Form(None),
    clear_about_images: str | None = Form(None),
    brand_images: list[UploadFile] = File(default_factory=list),
    about_images: list[UploadFile] = File(default_factory=list),
    db: Session = Depends(get_db),
):
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    product = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=HTTP_303_SEE_OTHER)

    sections = _load_verify_sections(db, product_id=product_id)

    if action == "save_page_settings":
        _save_verify_page_settings(
            db,
            product_id=product_id,
            settings={
                "brand_mark": brand_mark,
                "brand_name": brand_name,
                "brand_sub": brand_sub,
            },
        )
        db.commit()
        fallback_id = _pick_active_section_id(sections, active_section_id)
        return RedirectResponse(
            url=f"/admin/products/{product_id}/content?section={fallback_id}",
            status_code=HTTP_303_SEE_OTHER,
        )

    if action == "add_section":
        current_id = _pick_active_section_id(sections, active_section_id)
        title = new_section_title.strip()
        if title:
            sid = _make_section_id_from_title(title, existing_ids={s["id"] for s in sections})
            sections = _insert_section_after_about_us(
                sections,
                new_section={"id": sid, "title": title},
            )
            _save_verify_sections(db, product_id=product_id, sections=sections)
            db.commit()
        fallback_id = _pick_active_section_id(sections, current_id)
        return RedirectResponse(
            url=f"/admin/products/{product_id}/content?section={fallback_id}",
            status_code=HTTP_303_SEE_OTHER,
        )

    if action == "delete_section":
        sid = delete_section_id.strip().lower()
        if sid and len(sections) > 1 and sid in {s["id"] for s in sections}:
            sections = [s for s in sections if s["id"] != sid]
            _save_verify_sections(db, product_id=product_id, sections=sections)
            _delete_content_by_key(db, product_id=product_id, key=_section_content_key(section_id=sid))
            db.commit()
        fallback_id = _pick_active_section_id(sections, active_section_id)
        return RedirectResponse(
            url=f"/admin/products/{product_id}/content?section={fallback_id}",
            status_code=HTTP_303_SEE_OTHER,
        )

    if action == "restore_default_sections":
        current_id = _pick_active_section_id(sections, active_section_id)
        sections = _restore_default_sections(sections)
        _save_verify_sections(db, product_id=product_id, sections=sections)
        db.commit()
        fallback_id = _pick_active_section_id(sections, current_id)
        return RedirectResponse(
            url=f"/admin/products/{product_id}/content?section={fallback_id}",
            status_code=HTTP_303_SEE_OTHER,
        )

    if action == "save_section":
        sid = _pick_active_section_id(sections, active_section_id)
        blocks = _build_blocks(
            raw_blocks=_parse_blocks_json(section_blocks_json),
            uploaded_images=section_images,
            section=f"product_{product_id}_{sid}",
        )
        key = _section_content_key(section_id=sid)
        _set_blocks_content(db, product_id=product_id, key=key, blocks=blocks)
        if sid == "product_info":
            _sync_product_detail_from_blocks(product, blocks)
            db.add(product)
        db.commit()
        return RedirectResponse(
            url=f"/admin/products/{product_id}/content?section={sid}",
            status_code=HTTP_303_SEE_OTHER,
        )

    # Legacy compatibility path.
    has_free_blocks = bool(brand_blocks_json.strip() or about_blocks_json.strip())
    if has_free_blocks:
        brand_blocks = _build_blocks(
            raw_blocks=_parse_blocks_json(brand_blocks_json),
            uploaded_images=brand_images,
            section=f"product_{product_id}_brand_traceability",
        )
        about_blocks = _build_blocks(
            raw_blocks=_parse_blocks_json(about_blocks_json),
            uploaded_images=about_images,
            section=f"product_{product_id}_about_us",
        )
        _set_blocks_content(db, product_id=product_id, key="brand_traceability", blocks=brand_blocks)
        _set_blocks_content(db, product_id=product_id, key="about_us", blocks=about_blocks)
    else:
        brand_urls: list[str] = []
        for upload in brand_images:
            if upload.filename:
                brand_urls.append(
                    save_page_content_image(section=f"product_{product_id}_brand_traceability", upload=upload)
                )

        about_urls: list[str] = []
        for upload in about_images:
            if upload.filename:
                about_urls.append(
                    save_page_content_image(section=f"product_{product_id}_about_us", upload=upload)
                )

        if brand_urls or brand_text.strip() or clear_brand_images is not None:
            old_brand = _get_content(db, product_id=product_id, key="brand_traceability")
            blocks: list[dict[str, str]] = []
            if brand_text.strip():
                blocks.append({"type": "text", "text": brand_text.strip()})
            if clear_brand_images is None:
                for block in old_brand["blocks"]:
                    if block.get("type") == "image" and str(block.get("url", "")).strip():
                        blocks.append({"type": "image", "url": str(block["url"]).strip()})
            for url in brand_urls:
                blocks.append({"type": "image", "url": url})
            _set_blocks_content(db, product_id=product_id, key="brand_traceability", blocks=blocks)

        if about_urls or about_text.strip() or clear_about_images is not None:
            old_about = _get_content(db, product_id=product_id, key="about_us")
            blocks = []
            if about_text.strip():
                blocks.append({"type": "text", "text": about_text.strip()})
            if clear_about_images is None:
                for block in old_about["blocks"]:
                    if block.get("type") == "image" and str(block.get("url", "")).strip():
                        blocks.append({"type": "image", "url": str(block["url"]).strip()})
            for url in about_urls:
                blocks.append({"type": "image", "url": url})
            _set_blocks_content(db, product_id=product_id, key="about_us", blocks=blocks)

    db.commit()
    return RedirectResponse(url=f"/admin/products/{product_id}/content", status_code=HTTP_303_SEE_OTHER)
