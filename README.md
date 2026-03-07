# 防伪查询功能（MVP）

本项目用于生成 16 位数字防伪码并提供扫码验证 H5 页面与后台管理。

## 本地运行（开发）

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

uvicorn app.main:app --reload
```

打开：
- `http://127.0.0.1:8000/health`

## 测试

```bash
. .venv/bin/activate
pytest -q
```

