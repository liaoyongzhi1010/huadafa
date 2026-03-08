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

如果环境没有 `python3-venv`，可用 `.deps` 方式：

```bash
python3 -m pip install -r requirements.txt -t .deps

PYTHONPATH=.deps python3 -m uvicorn app.main:app --reload
```

打开：
- `http://127.0.0.1:8000/health`

## 测试

```bash
. .venv/bin/activate
pytest -q
PYTHONPATH=.deps pytest -q
```

## 线上部署与目录约定（唯一代码源）

- 唯一真实代码目录：`/srv/anticounterfeit`
- `/root/code` 现在是软链接（alias）并指向：`/srv/anticounterfeit`
- 线上服务：`anticounterfeit.service`
  - `WorkingDirectory=/srv/anticounterfeit`
  - `ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8001`
  - 环境变量：`/etc/anticounterfeit/anticounterfeit.env`

### 日常开发规则（防止再乱）

1. 可以在 `/root/code` 或 `/srv/anticounterfeit` 任一路径改代码，本质是同一份文件。
2. 不再做 `/root/code` 与 `/srv/anticounterfeit` 之间的手工同步、拷贝、`rsync`。
3. 每次改动后直接重启服务并回查页面。

### 快速自检

```bash
# 必须输出 /srv/anticounterfeit
readlink -f /root/code

# 服务状态
systemctl is-active anticounterfeit.service
```

### 如果以后发现 /root/code 不再是软链接（修复命令）

```bash
tar -C /root -czf /tmp/root_code_backup_$(date +%Y%m%d_%H%M%S).tar.gz code
rm -rf /root/code
ln -s /srv/anticounterfeit /root/code
readlink -f /root/code
```

### 发布最小检查清单

1. `PYTHONPATH=.deps python3 -m pytest -q`（或跑本次变更相关测试）。
2. `systemctl restart anticounterfeit.service`。
3. 线上回查 `/verify` 与 `/verify/general`。

### 品牌文案规则（禁止再踩坑）

- 不要在模板里写死品牌文案。
  - `verify.html` / `verify_generic.html` 必须使用：`brand_mark`、`brand_name`、`brand_sub`。
- 配置读取优先级：
  - 防伪页：`product:{id}:verify_page_settings`
  - 通用页：`product:{id}:generic_settings`（缺省可回退到 `verify_page_settings`）
- 通用页设置保存时，必须合并已有 `content_json`，不能整块覆盖导致字段丢失。
