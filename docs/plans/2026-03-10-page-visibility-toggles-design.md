# 防伪页与通用页独立显示开关设计

日期：2026-03-10

## 背景

当前后台已经有“防伪页设置”和“通用页设置”两个独立入口，但它们主要只控制顶部品牌文案。页面中的核心区块，例如产品名称、生产日期、产品信息、品牌溯源、官方推荐等，还不能按页面类型分别控制显示与隐藏。

业务需求是：

- 防伪页和通用页各自独立配置一套显示开关
- 开关以区块为单位控制，不做过细的元素级碎片化配置
- 对已有产品默认保持现状，不因为新增开关导致页面内容突然消失

## 目标

- 为防伪页新增一套独立显示开关
- 为通用页新增一套独立显示开关
- 后台两个设置页各自维护自己的可见性配置
- 预览页与实际页面渲染保持一致

## 非目标

- 不把每一张图片、每一段文字拆成单独开关
- 不改动内容编辑器的数据结构
- 不引入新的数据库表或结构化 section 权限模型

## 方案选择

### 方案 A：两个设置页各自维护布尔开关

推荐方案。把每个页面类型的显示开关直接存进各自现有的 `PageContent.content_json` 中。优点是结构直观、兼容现有数据、实现风险低。

### 方案 B：统一使用 “visible_sections” 列表

不采用。虽然字段数量更少，但“产品名大标题”“生产日期”“最近验证时间”“官方推荐”等并不天然属于同一类 section，最终会形成半列表半布尔的混合模型。

### 方案 C：超细粒度元素开关

不采用。后台会很快变得难用，用户理解成本和维护成本都过高。

## 数据设计

### 防伪页设置存储

继续使用键：

- `product:{id}:verify_page_settings`

新增布尔字段：

- `show_result_product_name`
- `show_batch_date`
- `show_recent_events`
- `show_recommendations`
- `show_product_info`
- `show_brand_traceability`
- `show_about_us`

原有字段继续保留：

- `brand_mark`
- `brand_name`
- `brand_sub`

### 通用页设置存储

继续使用键：

- `product:{id}:generic_settings`

新增或继续使用布尔字段：

- `show_product_name`
- `show_batch_date`
- `show_recommendations`
- `show_product_info`
- `show_brand_traceability`
- `show_about_us`

原有字段继续保留：

- `generic_message`
- `brand_mark`
- `brand_name`
- `brand_sub`

### 兼容策略

- 旧数据中没有这些字段时，一律按 `True` 处理
- 因为配置存储在 JSON 中，不需要 Alembic 迁移

## 页面行为

### 防伪页

- `show_result_product_name=false`
  - 隐藏结果卡片中的产品名大标题
  - 顶部品牌头区域不受影响
- `show_batch_date=false`
  - 隐藏生产日期整块
- `show_recent_events=false`
  - 隐藏“最近验证时间”整块
- `show_recommendations=false`
  - 隐藏“官方推荐”标题和推荐内容
  - 也不显示“暂无推荐”
- `show_product_info=false`
  - 隐藏“产品信息” tab 和内容
- `show_brand_traceability=false`
  - 隐藏“品牌溯源” tab 和内容
- `show_about_us=false`
  - 隐藏“关于我们” tab 和内容

### 通用页

- `show_product_name=false`
  - 隐藏产品名称整行
- `show_batch_date=false`
  - 隐藏生产日期整行
- `show_recommendations=false`
  - 隐藏“官方推荐”标题和推荐内容
  - 也不显示“暂无推荐”
- `show_product_info=false`
  - 隐藏“产品信息” tab 和内容
- `show_brand_traceability=false`
  - 隐藏“品牌溯源” tab 和内容
- `show_about_us=false`
  - 隐藏“关于我们” tab 和内容

### 通用规则

- 关闭某个区块后，不保留空标题或空白占位
- tab 列表由最终可见 section 动态生成
- 预览页和正式页面使用同一套显示逻辑

## 管理后台交互

### 防伪页设置页

在现有品牌头文案字段下新增“显示内容”复选框组：

- 显示结果产品名
- 显示生产日期
- 显示最近验证时间
- 显示官方推荐
- 显示产品信息
- 显示品牌溯源
- 显示关于我们

### 通用页设置页

在现有品牌头文案和主标题字段下新增“显示内容”复选框组：

- 显示产品名称
- 显示生产日期
- 显示官方推荐
- 显示产品信息
- 显示品牌溯源
- 显示关于我们

## 实现思路

- 在 `admin_verify_page_settings.py` 中扩展读取和保存逻辑
- 在 `admin_generic_settings.py` 中扩展读取和保存逻辑
- 在 `public_pages.py` 中新增两个过滤层：
  - 防伪页可见性过滤
  - 通用页可见性过滤
- 通过过滤后的结果驱动模板渲染，而不是在模板中写大量硬编码判断

## 测试策略

- 后台设置页测试：
  - 页面能看到新增复选框
  - 提交后配置只影响当前产品
  - 未提交的旧字段不会丢失
- 页面渲染测试：
  - 防伪页关闭某个区块后不再渲染对应标题与内容
  - 通用页关闭某个区块后不再渲染对应标题与内容
  - tab 顺序与剩余可见 section 保持一致
  - 推荐区关闭后，“官方推荐”和“暂无推荐”都不显示

## 风险

- 防伪页模板目前把产品名大标题直接绑定在 `message` 上，隐藏时需要谨慎处理，避免影响异常状态文案
- section 过滤后，tab 默认激活逻辑必须基于过滤结果重新计算，否则会出现首个 tab 为空或激活错位

## 结论

采用“两个设置页各自维护布尔开关”的方案，以最小改动实现防伪页和通用页的独立显示控制，并保持与现有数据结构和后台交互一致。
