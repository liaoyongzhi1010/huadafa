# 防伪页与通用页独立显示开关 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add independent visibility toggles for verify pages and generic pages so admins can control which content blocks render on each page type.

**Architecture:** Keep using product-scoped `PageContent.content_json` records as the source of truth. Extend `verify_page_settings` and `generic_settings` JSON payloads with boolean toggles, then add filtering logic in `public_pages.py` so templates render only the enabled blocks for each page type.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, Jinja2 templates, pytest.

---

### Task 1: Lock behavior with failing tests

**Files:**
- Modify: `tests/test_verify_page.py`
- Modify: `tests/test_admin_generic_settings.py`
- Create: `tests/test_admin_verify_page_settings.py`

**Step 1: Write the failing test**

Add tests that prove:

```python
def test_verify_page_hides_disabled_blocks():
    ...

def test_verify_generic_page_hides_disabled_blocks():
    ...

def test_verify_page_settings_page_shows_visibility_checkboxes():
    ...
```

**Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_verify_page.py tests/test_admin_generic_settings.py tests/test_admin_verify_page_settings.py -q
```

Expected: FAIL because the settings pages do not expose the new checkboxes and public pages do not yet respect the toggles.

**Step 3: Write minimal implementation**

Only implement enough behavior to make the tests in later tasks pass.

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

**Step 5: Commit**

```bash
git add tests/test_verify_page.py tests/test_admin_generic_settings.py tests/test_admin_verify_page_settings.py
git commit -m "test: cover independent page visibility toggles"
```

### Task 2: Add verify-page visibility settings

**Files:**
- Modify: `app/routes/admin_verify_page_settings.py`
- Modify: `app/templates/admin/verify_page_settings_edit.html`
- Test: `tests/test_admin_verify_page_settings.py`

**Step 1: Write the failing test**

Add tests that prove the verify-page settings form:

```python
def test_verify_page_settings_submit_persists_visibility_flags():
    ...
```

**Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_admin_verify_page_settings.py -q
```

Expected: FAIL because the route only stores brand header fields today.

**Step 3: Write minimal implementation**

Extend loading and saving so `product:{id}:verify_page_settings` handles:

- `show_result_product_name`
- `show_batch_date`
- `show_recent_events`
- `show_recommendations`
- `show_product_info`
- `show_brand_traceability`
- `show_about_us`

Add matching checkboxes to the settings template.

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

**Step 5: Commit**

```bash
git add app/routes/admin_verify_page_settings.py app/templates/admin/verify_page_settings_edit.html tests/test_admin_verify_page_settings.py
git commit -m "feat: add verify page visibility settings"
```

### Task 3: Add generic-page visibility settings

**Files:**
- Modify: `app/routes/admin_generic_settings.py`
- Modify: `app/templates/admin/generic_settings_edit.html`
- Modify: `tests/test_admin_generic_settings.py`

**Step 1: Write the failing test**

Add tests that prove the generic settings form exposes and persists:

```python
def test_admin_generic_settings_page_shows_visibility_checkboxes():
    ...

def test_admin_generic_settings_submit_persists_visibility_flags():
    ...
```

**Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_admin_generic_settings.py -q
```

Expected: FAIL because the page does not expose the new controls and the route only persists the old subset of fields.

**Step 3: Write minimal implementation**

Extend `product:{id}:generic_settings` handling so it supports:

- `show_product_name`
- `show_batch_date`
- `show_recommendations`
- `show_product_info`
- `show_brand_traceability`
- `show_about_us`

Add matching checkboxes to the template while preserving existing brand/message fields.

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

**Step 5: Commit**

```bash
git add app/routes/admin_generic_settings.py app/templates/admin/generic_settings_edit.html tests/test_admin_generic_settings.py
git commit -m "feat: add generic page visibility settings"
```

### Task 4: Wire public page rendering to the new toggles

**Files:**
- Modify: `app/routes/public_pages.py`
- Modify: `app/templates/verify.html`
- Modify: `app/templates/verify_generic.html`
- Modify: `tests/test_verify_page.py`

**Step 1: Write the failing test**

Add tests that prove:

```python
def test_verify_page_hides_result_title_and_sections_when_disabled():
    ...

def test_verify_generic_page_hides_meta_recommendations_and_sections_when_disabled():
    ...
```

**Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_verify_page.py -q
```

Expected: FAIL because current rendering always shows recommendations and always passes all sections through.

**Step 3: Write minimal implementation**

In `public_pages.py`:

- load the new verify-page visibility flags from `verify_page_settings`
- load the new generic-page visibility flags from `generic_settings`
- filter `verify_sections` based on the page-specific toggles
- gate recommendations and recent-events data before rendering

In templates:

- hide the verify-page result product title when disabled
- hide the batch-date row/line when disabled
- skip recommendation block entirely when disabled
- render tabs only from the filtered section list

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

**Step 5: Commit**

```bash
git add app/routes/public_pages.py app/templates/verify.html app/templates/verify_generic.html tests/test_verify_page.py
git commit -m "feat: honor independent visibility toggles on public pages"
```

### Task 5: Full verification

**Files:**
- Verify only

**Step 1: Run targeted tests**

Run:

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_verify_page.py tests/test_admin_generic_settings.py tests/test_admin_verify_page_settings.py -q
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
git commit -m "feat: add independent verify and generic page visibility toggles"
```
