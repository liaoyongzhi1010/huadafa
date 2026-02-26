# 防伪查询功能（防伪码扫码验证）系统设计

日期：2026-02-26  
范围：单产品/单账号后台（可扩展多产品/多账号）

## 1. 背景与目标

### 目标
- 针对一款产品（例如打火机），按批次批量生成 **16 位随机数字**防伪码（数量可控，单批 < 1 万）。
- 每个防伪码对应一个二维码，二维码内容为验证页 URL：`/verify?code=xxxxxxxxxxxxxxxx`。
- 用户扫码进入 H5 验证页，展示“正品验证信息”、扫码次数/时间记录、产品信息、品牌溯源、关于我们，以及“联系我们”跳转官网。

### 非目标（本期不做）
- 线下标签印刷流程/打样对接（只提供可导出数据与二维码素材）。
- 高强度对抗（例如专业团伙爬虫/撞库）下的强风控体系（本期提供基础限流与去重）。

## 2. 角色与权限
当前：后台 **单账号**（管理员），拥有全部权限。  
可扩展：后续可拆分“管理员/运营”两种角色权限。

## 3. 核心业务规则

### 3.1 防伪码生成
- 防伪码：**16 位随机数字**（建议首位不为 0，便于展示/避免被截断）。
- 唯一性：数据库唯一索引，若碰撞自动重试。
- 批次：每次生成代表一个批次，批次的“生产日期”默认为该批次生成日期（满足“再次生成一批码=第二批次”的需求）。

### 3.2 扫码成功一次的定义（计数规则）
说明：系统无法获得“相机扫到码”的底层事件，因此以“打开验证页并完成一次有效校验”作为一次扫码成功。

计数规则采用你确认的 **B**：
- 同一防伪码在同一设备上 **60 秒**内重复打开/刷新 **只计 1 次**。
- 设备识别优先用 Cookie（`visitor_id`），无 Cookie 时降级用 `ip_hash + ua_hash`。
- 推荐实现为：H5 页面加载后由 JS 调用 `POST /api/public/verify/track` 触发计数（可降低微信预拉取/爬虫只抓 HTML 带来的误计数）。

### 3.3 重复扫码展示规则
- 第 1 次：显示“官方正品防伪码”提示，展示扫码时间。
- 第 2 次及以后：仍显示“正品”，但明显提示“已被查询过”，展示累计次数与最近 N 条验证时间。
- 当累计次数 ≥ 阈值（默认 5）：显示红色风险提醒（文案可配置）。

### 3.4 防伪码显隐
- 后台可配置是否在页面顶部明文展示防伪码。
- 不展示时，顶部显示“对号/ZIPPO 风格图标”占位（参考：`docx_media/image1.png`、`docx_media/image2.png`）。

### 3.5 商品推荐位
- 后台可配置推荐图 + 跳转链接。
- **无图片则不展示**；点击跳转链接由后台配置。

## 4. 页面与交互

### 4.1 H5 验证页（`/verify?code=...`）
结构（与参考图一致）：
- 顶部区：对号/品牌 + 正品提示文案 +（可选）防伪码明文
- 次数区：`此防伪码已验证 X 次` +（X>1）“已被查询过”提示
- 风险提示：X ≥ 阈值显示红字提醒
- 时间列表：展示最近 N 条验证时间（默认 5 条，可配置）
- 推荐区：有图才显示（图 + 点击跳链接）
- 底部 Tab：产品信息 / 品牌溯源 / 关于我们
- 底部固定按钮：联系我们（跳转官网指定 URL）

异常场景：
- code 不存在：显示“未查询到/疑似非官方防伪码”，不展示产品详情（避免枚举探测）。
- code 已作废/批次作废：显示“该码已作废，请联系官方”。

### 4.2 后台管理（PC）
页面清单：
- 仪表盘：今日/7 天扫码数、多次验证 Top、批次数量、防伪码总量
- 产品管理：产品名称、详情文字、详情图片列表（按顺序展示）
- 批次管理：创建批次（生产日期/备注）、生成防伪码（输入数量）、作废批次、导出
- 防伪码查询：按码/批次搜索、查看扫码记录、作废单码（需原因）
- 内容配置：品牌溯源（图文）、关于我们（图文）、联系我们 URL
- 验证页配置：正品/未查到文案、防伪码显隐、阈值（默认 5）、时间列表条数（默认 5）
- 推荐管理：推荐图、跳转链接、启用开关（可按产品绑定）

## 5. 数据模型（建议）

> 字段名仅供参考，可按技术栈调整。

### 5.1 product（产品）
- `id`
- `name`
- `detail_text`（产品详情文字）
- `detail_images`（图片列表：可 JSON 数组或独立表）
- `created_at` `updated_at`

### 5.2 batch（批次）
- `id`
- `product_id`
- `production_date`（通常=生成日期）
- `note`（可选）
- `status`（active/disabled）
- `disabled_reason`（可选）
- `created_at` `updated_at`

### 5.3 anti_code（防伪码）
- `id`
- `code`（16 位数字，唯一索引）
- `product_id`
- `batch_id`
- `status`（active/disabled）
- `disabled_reason`（可选）
- `scan_count`（累计次数）
- `first_scanned_at`（可空）
- `last_scanned_at`（可空）
- `created_at` `updated_at`

### 5.4 scan_event（扫码事件）
- `id`
- `anti_code_id`
- `scanned_at`
- `visitor_id`（可空；来自 cookie）
- `ip_hash`（可空；脱敏）
- `ua_hash`（可空；脱敏）

### 5.5 recommendation（推荐位）
- `id`
- `product_id`（可空：为空表示全局推荐）
- `image_url`
- `target_url`
- `enabled`
- `sort_order`
- `created_at` `updated_at`

### 5.6 page_content（固定内容）
- `id`
- `key`（`brand_traceability` / `about_us`）
- `content_json`（图文结构化内容，或 markdown/html）
- `updated_at`

### 5.7 verify_config（验证页配置）
- `id`
- `show_code`（bool）
- `warning_threshold`（int，默认 5）
- `recent_events_limit`（int，默认 5）
- `contact_us_url`
- `text_genuine`（如：ICOM 官方正品防伪码）
- `text_not_found`
- `text_warning`（阈值触发文案）
- `updated_at`

## 6. API 设计（建议）

### 6.1 后台鉴权
- `POST /api/admin/auth/login`
- `POST /api/admin/auth/logout`
- `GET /api/admin/auth/me`

### 6.2 产品/批次/防伪码
- `GET /api/admin/products`
- `POST /api/admin/products`
- `PUT /api/admin/products/{id}`
- `POST /api/admin/batches`（创建批次）
- `GET /api/admin/batches?product_id=...`
- `PATCH /api/admin/batches/{id}/disable`
- `POST /api/admin/batches/{id}/codes:generate`（生成数量）
- `GET /api/admin/codes?code=...&batch_id=...`
- `GET /api/admin/codes/{code}/scan-events?limit=...`
- `PATCH /api/admin/codes/{code}/disable`

### 6.3 内容/配置/推荐位
- `GET/PUT /api/admin/verify-config`
- `GET/PUT /api/admin/page-content`
- `GET/POST/PUT/DELETE /api/admin/recommendations`

### 6.4 导出
- `GET /api/admin/batches/{id}/export/csv`（code + verify_url + 批次信息）
- `POST /api/admin/batches/{id}/export/qrcodes`（异步生成 ZIP）
- `GET /api/admin/export-jobs/{job_id}`（查询进度/下载）

### 6.5 公开验证（扫码用）
- `GET /api/public/verify?code=...`（返回展示数据；不计数或仅在需要时计数）
- `POST /api/public/verify/track`（触发计数：包含 `code`；实现 60 秒去重）

## 7. 导出规范

### 7.1 CSV/Excel 列建议
- `product_name`
- `batch_id` / `production_date`
- `code`
- `verify_url`（完整 URL，二维码内容）

### 7.2 二维码素材 ZIP
- 每个防伪码生成 1 张 PNG（命名 `code.png` 或 `batchId_code.png`）
- ZIP 内可按批次分文件夹

## 8. 安全与稳定性（基础版）
- 验证接口限流：按 IP/UA 做基础频控（避免被批量枚举）。
- 返回数据最小化：code 不存在时不返回产品详情/推荐位等敏感信息。
- 去重计数：按 `anti_code_id + visitor_id`（或降级 hash）+ 60 秒窗口。
- 全站 HTTPS；后台登录带会话/令牌；操作写审计日志（可选）。

## 9. 部署建议（最小可用）
- 1 台云服务器（或云托管）+ 1 个关系型数据库（MySQL/PostgreSQL 均可）。
- 绑定域名（用于二维码），例如：`https://verify.example.com/verify?code=...`

