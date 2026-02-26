# 管理后台 UI（现代简洁白底）+ 使用文档（静态）Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current mobile-card admin UI with a modern desktop-friendly white layout, and add a static in-admin help page (`/admin/help`).

**Architecture:** Keep the server-rendered Jinja2 templates. Introduce an admin-only base template (`admin/base.html`) that provides a shared layout (topbar + sidebar + content). Update all admin templates to extend it. Add one admin route for help.

**Tech Stack:** FastAPI, Jinja2 templates, inline CSS (no external CDN).

---

## Task 1: Add `/admin/help` page (TDD)

**Files:**
- Modify: `tests/test_admin_auth.py`
- Modify: `app/routes/admin_pages.py`
- Create: `app/templates/admin/help.html`

**Step 1: Write a failing test**

Add to `tests/test_admin_auth.py`:
- Logged-out GET `/admin/help` redirects to `/admin/login`
- Logged-in GET `/admin/help` returns 200 and contains key text (e.g. “使用文档”)

**Step 2: Run the specific test**

Run: `PYTHONPATH=.deps python3 -m pytest -q tests/test_admin_auth.py`  
Expected: FAIL (route/template missing).

**Step 3: Implement route**

In `app/routes/admin_pages.py`:
- Add `GET /admin/help`
- Reuse the same session guard as `/admin`
- Render `admin/help.html`

**Step 4: Add the template**

Create `app/templates/admin/help.html` with static instructions:
- 产品 → 批次 → 生成码 → 导出 → 配置
- 计数规则说明：60 秒同设备去重

**Step 5: Re-run the test**

Run: `PYTHONPATH=.deps python3 -m pytest -q tests/test_admin_auth.py`  
Expected: PASS.

**Step 6: Commit**

Run:
```bash
git add tests/test_admin_auth.py app/routes/admin_pages.py app/templates/admin/help.html
git commit -m "feat(admin): add in-app help page"
```

---

## Task 2: Create admin layout base template + CSS

**Files:**
- Create: `app/templates/admin/base.html`
- Modify: `app/templates/admin/login.html`
- Modify: `app/templates/admin/index.html`

**Step 1: Add `admin/base.html`**
- Modern white UI: background + card + table + form + button styles
- Layout: sidebar + topbar + main content
- Sidebar/topbar visible only when logged in (`request.session.admin_logged_in`)
- Sidebar includes links: `/admin`, `/admin/products`, `/admin/config`, `/admin/content`, `/admin/recommendations`, `/admin/help`
- Active state based on `request.url.path`

**Step 2: Update login and dashboard**
- Make `admin/login.html` extend `admin/base.html` and render centered login card
- Make `admin/index.html` extend `admin/base.html` and show “快速开始” blocks (optional)
- Ensure the HTML for `/admin` still contains the key links asserted by tests (links can be in sidebar)

**Step 3: Run tests**

Run: `PYTHONPATH=.deps python3 -m pytest -q`  
Expected: PASS.

**Step 4: Commit**

Run:
```bash
git add app/templates/admin/base.html app/templates/admin/login.html app/templates/admin/index.html
git commit -m "feat(admin): add modern admin base layout"
```

---

## Task 3: Update all admin templates to use the new base layout

**Files (Modify):**
- `app/templates/admin/products_list.html`
- `app/templates/admin/product_new.html`
- `app/templates/admin/product_edit.html`
- `app/templates/admin/batches_list.html`
- `app/templates/admin/batch_new.html`
- `app/templates/admin/batch_detail.html`
- `app/templates/admin/config_edit.html`
- `app/templates/admin/content_edit.html`
- `app/templates/admin/recommendations_list.html`
- `app/templates/admin/recommendation_new.html`

**Step 1: Replace `extends "base.html"`**
- Change to `extends "admin/base.html"`
- Remove duplicated “退出登录/返回后台” blocks where the sidebar/topbar already provides navigation

**Step 2: Improve list/form markup**
- Use `.page-header` + `.actions` for page titles and primary actions
- Use `<table class="table">` for desktop lists (products, batches, recommendations)
- Use `.form-grid` for forms where appropriate

**Step 3: Run tests**

Run: `PYTHONPATH=.deps python3 -m pytest -q`  
Expected: PASS.

**Step 4: Commit**

Run:
```bash
git add app/templates/admin/*.html
git commit -m "feat(admin): restyle admin pages with modern layout"
```

---

## Task 4: Deploy updated templates to production (no Docker)

**Assumption:** Production runs from `/srv/anticounterfeit` via `systemd` service `anticounterfeit.service` and proxies through nginx.

**Steps:**
1) `rsync` the repo from worktree to `/srv/anticounterfeit` (exclude `.deps/`, `uploads/`, `*.db`)
2) `systemctl restart anticounterfeit.service`
3) Smoke test:
   - `curl -sS https://1918imco.com/health`
   - Load `https://1918imco.com/admin/login`
   - Login and open `/admin/help`

