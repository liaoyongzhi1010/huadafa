# 产品页皮肤设置 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a per-product skin selector so verify pages and generic pages share one saved visual theme, with live preview before save.

**Architecture:** Store a product-level `skin_id` in existing `PageContent.content_json`, define all preset skins in a shared `page_skins` service, add a dedicated admin `skin-settings` page, and let public pages read the saved skin or a preview-only `skin_id` query override.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, Jinja2 templates, pytest, inline JavaScript.

---

### Task 1: Lock admin and public skin behavior with failing tests

**Files:**
- Modify: `tests/test_admin_batches_list_ui.py`
- Modify: `tests/test_verify_page.py`
- Create: `tests/test_admin_skin_settings.py`

**Step 1: Write the failing test**

Add tests that prove:

```python
def test_product_tabs_include_skin_settings_after_contact_settings():
    ...

def test_admin_skin_settings_page_has_skin_cards_and_two_previews():
    ...

def test_verify_pages_use_saved_skin_and_preview_override():
    ...
```

**Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_verify_page.py tests/test_admin_batches_list_ui.py tests/test_admin_skin_settings.py -q
```

Expected: FAIL because there is no skin settings route, no tab button, and public pages do not load skin definitions.

**Step 3: Write minimal implementation**

Implement only enough to make the tests in later tasks pass.

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

### Task 2: Add the shared skin catalog and product skin persistence

**Files:**
- Create: `app/services/page_skins.py`
- Modify: `app/routes/public_pages.py`

**Step 1: Write the failing test**

Add tests that prove:

```python
def test_verify_page_uses_default_skin_when_not_configured():
    ...

def test_verify_page_uses_saved_skin_when_configured():
    ...
```

**Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_verify_page.py -q
```

**Step 3: Write minimal implementation**

- define the 4 preset skins in `page_skins.py`
- add helpers to read product `skin_id`
- default invalid or missing values to `classic_red`
- allow `preview=1&skin_id=...` to temporarily override

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

### Task 3: Add the admin skin settings page and navigation entry

**Files:**
- Create: `app/routes/admin_skin_settings.py`
- Create: `app/templates/admin/skin_settings_edit.html`
- Modify: `app/templates/admin/_product_tabs.html`
- Modify: `app/main.py`
- Test: `tests/test_admin_skin_settings.py`
- Test: `tests/test_admin_batches_list_ui.py`

**Step 1: Write the failing test**

Cover:

```python
def test_admin_skin_settings_submit_persists_current_product_skin():
    ...

def test_admin_skin_settings_preview_iframes_update_with_selected_skin():
    ...
```

**Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_admin_skin_settings.py tests/test_admin_batches_list_ui.py -q
```

**Step 3: Write minimal implementation**

- add the `皮肤设置` tab after `联系我们设置`
- build a skin settings page with 4 selectable cards
- include two preview iframes using preview-only `skin_id` query overrides
- save `skin_id` into `product:{id}:skin_settings`

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

### Task 4: Apply skin variables to verify and generic templates

**Files:**
- Modify: `app/templates/verify.html`
- Modify: `app/templates/verify_generic.html`
- Test: `tests/test_verify_page.py`

**Step 1: Write the failing test**

Add tests that prove a non-default skin affects both page types and preview override works before save.

**Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_verify_page.py -q
```

**Step 3: Write minimal implementation**

- inject shared skin CSS vars into both templates
- apply full-style differences through variables and minimal skin id branching
- preserve all existing content, visibility, and preview logic

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

### Task 5: Full verification

**Files:**
- Verify only

**Step 1: Run targeted tests**

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_verify_page.py tests/test_admin_batches_list_ui.py tests/test_admin_skin_settings.py -q
```

**Step 2: Run full suite**

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest -q
```
