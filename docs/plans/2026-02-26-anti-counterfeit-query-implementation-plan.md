# 防伪查询功能（防伪码扫码验证）Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an MVP anti-counterfeit system: admin backend to generate 16-digit codes per batch and a public H5 verification page (`/verify?code=...`) that tracks scans with 60s per-device de-duplication.

**Architecture:** A single Python FastAPI service serves (1) admin web UI (server-rendered) + admin APIs, (2) public JSON APIs for verify/track, and (3) the public H5 verification page. Data is stored in a relational DB (SQLite for local dev, PostgreSQL in production).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Jinja2 templates, HTMX (optional), Tailwind (CDN), pytest, httpx, qrcode + Pillow, python-multipart.

---

## Conventions / Decisions (locked)
- QR code payload: verification URL with query param: `https://<domain>/verify?code=<16digits>`.
- Scan “success” definition: a successful verify + track write of a scan event.
- Scan counting rule: same `code` on same device within **60 seconds** counts as **1** (de-dupe by `visitor_id` cookie; fallback to `ip_hash+ua_hash`).
- Repeat scans: still show “正品”，但提示“已被查询过”，显示次数与最近 N 次时间；次数 >= 阈值（默认 5）显示红字提醒。
- Admin: single account for now (one username/password), can be expanded later.
- Scale: single batch < 10k codes (still design for larger later).

---

## Task 0: Bootstrap repository (Python app skeleton)

**Files:**
- Create: `README.md`
- Create: `requirements.txt`
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `app/settings.py`
- Create: `app/db.py`
- Create: `app/models/__init__.py`
- Create: `app/models/base.py`
- Create: `app/templates/base.html`
- Create: `app/static/.gitkeep`
- Create: `tests/test_health.py`

**Step 1: Create venv + install deps**

Run:
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

Expected: installs FastAPI + pytest toolchain successfully.

**Step 2: Write a failing health test**

Create `tests/test_health.py`:
```python
from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
```

**Step 3: Run test to verify it fails**

Run: `pytest -q`  
Expected: FAIL because `/health` route not implemented (or import errors).

**Step 4: Implement minimal FastAPI app**

In `app/main.py`:
```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health():
    return {"ok": True}
```

**Step 5: Run tests**

Run: `pytest -q`  
Expected: PASS.

**Step 6: (Optional) Commit**

If using git:
```bash
git init
git add .
git commit -m "chore: bootstrap fastapi app skeleton"
```

---

## Task 1: Database layer (SQLAlchemy + Alembic)

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/.gitkeep`
- Modify: `app/db.py`
- Modify: `app/settings.py`
- Create: `app/models/product.py`
- Create: `app/models/batch.py`
- Create: `app/models/anti_code.py`
- Create: `app/models/scan_event.py`
- Create: `app/models/recommendation.py`
- Create: `app/models/page_content.py`
- Create: `app/models/verify_config.py`
- Modify: `app/models/__init__.py`
- Test: `tests/test_db_migrations.py`

**Step 1: Add settings**

In `app/settings.py` define:
- `DATABASE_URL` default `sqlite:///./dev.db`
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` (for single admin account)

**Step 2: Write failing test that tables exist**

`tests/test_db_migrations.py`:
```python
from app.db import engine


def test_can_connect():
    with engine.connect() as conn:
        conn.exec_driver_sql("SELECT 1")
```

Run: `pytest -q`  
Expected: FAIL until `engine` exists.

**Step 3: Implement `app/db.py`**

Implement:
- SQLAlchemy engine from `DATABASE_URL`
- SessionLocal factory
- `get_db()` dependency

**Step 4: Create models**

Create SQLAlchemy models mirroring the design doc:
- Product, Batch, AntiCode, ScanEvent, Recommendation, PageContent, VerifyConfig
- Unique constraint on `AntiCode.code`
- Index on `ScanEvent.scanned_at`, `AntiCode.batch_id`, etc.

**Step 5: Add Alembic and generate initial migration**

Run:
```bash
alembic init alembic
alembic revision --autogenerate -m "init schema"
alembic upgrade head
```

Expected: `dev.db` created with tables.

**Step 6: Run tests**

Run: `pytest -q`  
Expected: PASS.

**Step 7: Commit**
`git commit -am "feat: add db models and migrations"`

---

## Task 2: Public verify JSON API (`GET /api/public/verify`)

**Files:**
- Create: `app/schemas/public.py`
- Create: `app/routes/public_verify.py`
- Modify: `app/main.py`
- Test: `tests/test_public_verify.py`

**Step 1: Write failing tests**

`tests/test_public_verify.py` should cover:
- code not found → 404 + minimal response (no product details)
- code found → 200 with `scan_count`, `show_code`, `warning_threshold`, `recent_events`, product details, tabs content, recommendations (only if image present)

Example skeleton:
```python
from fastapi.testclient import TestClient

from app.main import app


def test_verify_not_found_returns_404():
    client = TestClient(app)
    r = client.get("/api/public/verify", params={"code": "1234567890123456"})
    assert r.status_code == 404
```

**Step 2: Run tests to verify failure**
Run: `pytest -q`  
Expected: FAIL (route missing).

**Step 3: Implement route**
- Validate `code` format: exactly 16 digits
- Query AntiCode + joins (Product/Batch) + VerifyConfig + PageContent + Recommendation
- If not found: return 404 with `{ "status": "not_found", "message": ... }`
- If disabled: return 410 with `{ "status": "disabled", ... }`
- If found: return `{ status: "genuine", scan_count, first_scanned_at, last_scanned_at, recent_events, show_code, ... }`

**Step 4: Run tests**
Run: `pytest -q`  
Expected: PASS.

**Step 5: Commit**
`git commit -am "feat: add public verify json api"`

---

## Task 3: Scan tracking API with 60s de-dupe (`POST /api/public/verify/track`)

**Files:**
- Modify: `app/routes/public_verify.py`
- Create: `app/services/track_scan.py`
- Modify: `app/main.py` (middleware/cookie)
- Test: `tests/test_track_dedupe.py`

**Step 1: Write failing dedupe tests**

Test cases:
- First track call increments `scan_count` and creates 1 ScanEvent.
- Second call within 60s with same `visitor_id` does NOT increment and does NOT create a new ScanEvent.
- Second call after 60s increments again.

**Step 2: Implement `visitor_id` cookie**
- On `/verify` page response and/or on track response, set `visitor_id` cookie if missing (UUID v4).

**Step 3: Implement de-dupe logic**
- Key: (`anti_code_id`, `visitor_id`)
- Rule: if exists ScanEvent in last 60 seconds, skip insert/increment.
- Fallback: use `ip_hash` + `ua_hash` if no visitor_id (still apply 60s).

**Step 4: Run tests**
Run: `pytest -q`  
Expected: PASS.

**Step 5: Commit**
`git commit -am "feat: add scan tracking with 60s dedupe"`

---

## Task 4: Public H5 verification page (`GET /verify`)

**Files:**
- Create: `app/routes/public_pages.py`
- Create: `app/templates/verify.html`
- Modify: `app/templates/base.html`
- Modify: `app/main.py`
- Test: `tests/test_verify_page.py`

**Step 1: Write failing test**
- `/verify?code=...` returns HTML 200
- page contains “正品防伪码” when genuine
- contains “未查询到” when not found

**Step 2: Implement template**
- Layout per reference images:
  - top: check icon / brand + title
  - scan count + warning
  - recent times list
  - recommendation block (conditional)
  - tabs: 产品信息 / 品牌溯源 / 关于我们
  - bottom: 联系我们

**Step 3: Ensure JS calls track endpoint once**
- On page load, call `POST /api/public/verify/track` with code.
- If API returns `deduped: true` show same count.

**Step 4: Run tests**
Run: `pytest -q`  
Expected: PASS.

**Step 5: Commit**
`git commit -am "feat: add public verify h5 page"`

---

## Task 5: Admin authentication (single account)

**Files:**
- Create: `app/routes/admin_auth.py`
- Create: `app/templates/admin/login.html`
- Modify: `app/main.py`
- Create: `app/auth.py`
- Test: `tests/test_admin_auth.py`

**Step 1: Write failing tests**
- GET `/admin/login` 200
- POST `/admin/login` with correct creds sets session cookie and redirects to `/admin`
- Wrong creds shows error
- Protected routes redirect to login

**Step 2: Implement session auth**
- Use Starlette SessionMiddleware with secret key from env.
- Store `admin_logged_in=True` in session.
- Dependency `require_admin()` to protect `/admin/*` routes.

**Step 3: Run tests**
Run: `pytest -q`  
Expected: PASS.

**Step 4: Commit**
`git commit -am "feat: add admin session login"`

---

## Task 6: Admin UI - Products / Batches / Code generation

**Files:**
- Create: `app/routes/admin_products.py`
- Create: `app/routes/admin_batches.py`
- Create: `app/routes/admin_codes.py`
- Create: `app/templates/admin/layout.html`
- Create: `app/templates/admin/index.html`
- Create: `app/templates/admin/products_list.html`
- Create: `app/templates/admin/product_edit.html`
- Create: `app/templates/admin/batches_list.html`
- Create: `app/templates/admin/batch_detail.html`
- Create: `app/templates/admin/codes_search.html`
- Test: `tests/test_admin_products.py`
- Test: `tests/test_admin_batches_generate.py`

**Step 1: TDD product CRUD**
- List/create/edit product name + detail text
- Upload multiple detail images (store under `./uploads/` and persist URLs)

**Step 2: TDD batch creation + code generation**
- Create batch with production_date + note
- Generate N codes (N <= 10000) in one request
- Ensure uniqueness + store `created_at`

**Step 3: Add code search + scan events view**
- Search by exact code
- View scan_count + recent events

**Step 4: Run tests**
Run: `pytest -q`  
Expected: PASS.

**Step 5: Commit**
`git commit -am "feat: admin products, batches, and code generation"`

---

## Task 7: Admin UI - Content, config, recommendations

**Files:**
- Create: `app/routes/admin_content.py`
- Create: `app/routes/admin_config.py`
- Create: `app/routes/admin_recommendations.py`
- Create: `app/templates/admin/content_edit.html`
- Create: `app/templates/admin/config_edit.html`
- Create: `app/templates/admin/recommendations_list.html`
- Create: `app/templates/admin/recommendation_edit.html`
- Test: `tests/test_admin_config_effect.py`

**Step 1: Implement VerifyConfig editor**
- show_code toggle
- warning_threshold default 5
- recent_events_limit default 5
- contact_us_url
- text_genuine / text_not_found / text_warning

**Step 2: Implement PageContent editor**
- brand_traceability / about_us as rich text (start with markdown/plain textarea)
- optional images upload

**Step 3: Implement recommendations**
- image upload required; no image => disabled by validation
- target_url required
- enabled toggle + sort order

**Step 4: Tests**
- Changing config affects public verify responses (e.g., hide code, threshold)

**Step 5: Commit**
`git commit -am "feat: admin config, content, recommendations"`

---

## Task 8: Exports (CSV + QR code ZIP)

**Files:**
- Create: `app/services/export_csv.py`
- Create: `app/services/export_qrcodes.py`
- Create: `app/routes/admin_exports.py`
- Create: `app/models/export_job.py`
- Create: `app/templates/admin/export_jobs.html`
- Test: `tests/test_export_csv.py`

**Step 1: CSV export**
- `GET /admin/batches/{id}/export/csv` returns `text/csv`
- Columns: `product_name, production_date, code, verify_url`

**Step 2: QR code ZIP export (async job)**
- Create ExportJob table: `id, batch_id, status, progress, file_path, created_at`
- Start job endpoint: creates job record, spawns background task
- Background task:
  - generate PNG per code using `qrcode`
  - write to temp dir and zip
  - update job status + file_path
- Download endpoint serves zip and sets correct headers

**Step 3: Tests**
- CSV export returns expected headers and contains verify_url with code.

**Step 4: Commit**
`git commit -am "feat: export csv and qrcode zip"`

---

## Task 9: Basic rate limiting + hardening

**Files:**
- Create: `app/middleware/rate_limit.py`
- Modify: `app/main.py`
- Test: `tests/test_rate_limit.py`

**Step 1: Rate limit public endpoints**
- Apply token bucket per IP for `/api/public/*`
- Return 429 on exceeded

**Step 2: Security defaults**
- Force HTTPS-aware settings (proxy headers)
- Ensure admin session cookie is HttpOnly + SameSite=Lax

**Step 3: Tests**
- Repeated requests exceed limit -> 429

**Step 4: Commit**
`git commit -am "feat: add basic rate limiting and security hardening"`

---

## Task 10: Packaging + runbook (Docker + docs)

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Modify: `README.md`

**Step 1: Dockerize**
- app container + postgres container
- env vars: DATABASE_URL, ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY, BASE_URL

**Step 2: Document operations**
- How to generate a batch, export CSV/ZIP
- How to configure contact URL, texts, hide/show code
- Backup `uploads/` + database

**Step 3: Smoke test**
Run:
```bash
docker compose up --build
curl -s http://localhost:8000/health
```
Expected: `{"ok":true}`

**Step 4: Commit**
`git commit -am "chore: dockerize and document deployment"`

---

## Notes / Simplifications (MVP)
- Admin UI uses server-rendered templates for speed; can later replace with React/Vue.
- PageContent rich text starts as markdown/plain textarea; can later add WYSIWYG editor.
- Export job runner uses FastAPI background tasks; for large scale, move to Celery/RQ.

