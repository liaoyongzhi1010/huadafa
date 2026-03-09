# 设置页隐藏开关与即时预览 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make verify and generic settings use "checked means hide", default to all visible, and refresh the phone preview immediately before saving.

**Architecture:** Keep persisted data in existing `show_*` fields for compatibility. Translate admin form `hide_*` inputs into `show_*` booleans on submit, and let preview pages accept temporary query-parameter overrides only in `preview=1` mode.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, Jinja2 templates, pytest, small inline JavaScript.

---

### Task 1: Lock the new hide semantics with failing tests

**Files:**
- Modify: `tests/test_admin_verify_page_settings.py`
- Modify: `tests/test_admin_generic_settings.py`
- Modify: `tests/test_verify_page.py`

**Step 1: Write the failing test**

Add tests that prove:

- settings pages render `hide_*` checkbox names
- posting `hide_*` stores `show_* = False`
- preview routes hide blocks when `preview=1` query overrides are present

**Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_verify_page.py tests/test_admin_generic_settings.py tests/test_admin_verify_page_settings.py -q
```

Expected: FAIL because templates and routes still use `show_*` form fields and preview ignores unsaved form state.

**Step 3: Write minimal implementation**

Implement only enough route/template behavior to satisfy the new tests.

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

### Task 2: Wire hide-checkbox admin forms and live preview

**Files:**
- Modify: `app/routes/admin_verify_page_settings.py`
- Modify: `app/routes/admin_generic_settings.py`
- Modify: `app/templates/admin/verify_page_settings_edit.html`
- Modify: `app/templates/admin/generic_settings_edit.html`

**Step 1: Write the failing test**

Ensure form rendering and submit semantics match the new `hide_*` behavior.

**Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_admin_generic_settings.py tests/test_admin_verify_page_settings.py -q
```

**Step 3: Write minimal implementation**

- render `hide_*` checkboxes checked when corresponding `show_*` is false
- save `show_* = False` when a `hide_*` checkbox is present
- add lightweight JS to rebuild the preview iframe URL from current form values

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

### Task 3: Support preview-only query overrides on public pages

**Files:**
- Modify: `app/routes/public_pages.py`
- Modify: `app/templates/verify.html`
- Modify: `app/templates/verify_generic.html`

**Step 1: Write the failing test**

Add tests that request preview URLs with `hide_*` query params and verify the corresponding blocks disappear without any saved DB config.

**Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_verify_page.py -q
```

**Step 3: Write minimal implementation**

- in preview mode only, apply query overrides for brand text, generic message, and visibility
- keep existing saved `show_*` behavior for normal page visits

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

### Task 4: Full verification

**Files:**
- Verify only

**Step 1: Run targeted tests**

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest tests/test_verify_page.py tests/test_admin_generic_settings.py tests/test_admin_verify_page_settings.py -q
```

**Step 2: Run full suite**

```bash
PYTHONPATH=/srv/anticounterfeit/.deps python3 -m pytest -q
```
