# 批次日期精度与可编辑能力 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Support batch dates stored and displayed as year-only, year-month, or full date strings, and allow admins to edit an existing batch's date and note.

**Architecture:** Keep the existing FastAPI + server-rendered admin flow, but change `Batch.production_date` from a SQL date to a validated string field. Add a shared parser/validator for batch date inputs, wire it into create and edit routes, and update all downstream display/export code to treat the value as a string.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2.x, Alembic, Jinja2, pytest.

---

### Task 1: Lock behavior with failing tests

**Files:**
- Modify: `tests/test_admin_batch_create.py`
- Modify: `tests/test_export_csv.py`
- Modify: `tests/test_public_verify.py`
- Create: `tests/test_admin_batch_edit.py`

**Step 1: Write the failing test**

Add tests that prove:

```python
def test_admin_can_create_batch_with_year_month_precision():
    ...

def test_admin_rejects_invalid_batch_date():
    ...

def test_admin_can_edit_batch_date_and_note():
    ...
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_admin_batch_create.py tests/test_admin_batch_edit.py tests/test_export_csv.py tests/test_public_verify.py -q`
Expected: FAIL because the model, validation, and edit routes do not yet support string batch dates.

**Step 3: Write minimal implementation**

Implement only enough code to satisfy the tests in the next tasks.

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

**Step 5: Commit**

```bash
git add tests/test_admin_batch_create.py tests/test_admin_batch_edit.py tests/test_export_csv.py tests/test_public_verify.py
git commit -m "test: cover batch date precision and editing"
```

### Task 2: Migrate the batch date data model

**Files:**
- Modify: `app/models/batch.py`
- Create: `app/services/batch_dates.py`
- Create: `alembic/versions/<revision>_batch_date_string_precision.py`
- Modify: `tests/test_db_migrations.py`

**Step 1: Write the failing test**

Extend migration/model tests to assert the batch date field behaves as a string value and that validation accepts only supported formats.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_db_migrations.py tests/test_admin_batch_create.py -q`
Expected: FAIL because `Batch.production_date` is still a `Date`.

**Step 3: Write minimal implementation**

Create a shared parser/validator:

```python
def normalize_batch_date(value: str) -> str:
    ...
```

Then:
- change the model column to `String(10)`
- add Alembic migration converting historical `Date` values to strings

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

**Step 5: Commit**

```bash
git add app/models/batch.py app/services/batch_dates.py alembic/versions tests/test_db_migrations.py
git commit -m "feat: store batch dates as validated strings"
```

### Task 3: Add batch edit flow and strict validation

**Files:**
- Modify: `app/routes/admin_batches.py`
- Create: `app/templates/admin/batch_edit.html`
- Modify: `app/templates/admin/batches_list.html`
- Modify: `app/templates/admin/batch_new.html`

**Step 1: Write the failing test**

Add route/UI tests that prove:

```python
def test_batch_list_shows_edit_action():
    ...

def test_edit_page_renders_existing_batch_values():
    ...
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_admin_batch_edit.py tests/test_admin_batches_list_ui.py -q`
Expected: FAIL because no edit route or template exists.

**Step 3: Write minimal implementation**

Add:
- GET `/admin/batches/{batch_id}/edit`
- POST `/admin/batches/{batch_id}/edit`
- shared validation error rendering for create/edit
- edit button in the batch list

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

**Step 5: Commit**

```bash
git add app/routes/admin_batches.py app/templates/admin/batch_edit.html app/templates/admin/batches_list.html app/templates/admin/batch_new.html tests/test_admin_batch_edit.py tests/test_admin_batches_list_ui.py
git commit -m "feat: add editable batch dates in admin"
```

### Task 4: Update downstream display and export paths

**Files:**
- Modify: `app/services/export_csv.py`
- Modify: `app/routes/public_pages.py`
- Modify: `app/routes/public_verify.py`
- Modify: `tests/test_export_csv.py`
- Modify: `tests/test_public_verify.py`

**Step 1: Write the failing test**

Add assertions for year/month precision flowing through to CSV and public verify responses.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_export_csv.py tests/test_public_verify.py -q`
Expected: FAIL because current code calls `.isoformat()` on batch dates.

**Step 3: Write minimal implementation**

Replace `.isoformat()` usage with direct string output from the batch model.

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

**Step 5: Commit**

```bash
git add app/services/export_csv.py app/routes/public_pages.py app/routes/public_verify.py tests/test_export_csv.py tests/test_public_verify.py
git commit -m "fix: propagate string batch dates to exports and public pages"
```

### Task 5: Final verification

**Files:**
- Verify only

**Step 1: Run targeted tests**

Run:

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_admin_batch_create.py tests/test_admin_batch_edit.py tests/test_admin_batches_list_ui.py tests/test_export_csv.py tests/test_public_verify.py tests/test_db_migrations.py -q
```

Expected: PASS.

**Step 2: Run full suite**

Run:

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest -q
```

Expected: PASS.

**Step 3: Commit**

```bash
git add .
git commit -m "feat: support editable batch dates with year/month/day precision"
```
