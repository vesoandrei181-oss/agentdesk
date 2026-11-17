# 部署到自己的服务器（域名 durkmo.eu.cc）

> 目标：评审期间电脑关机、断网，`https://durkmo.eu.cc` 依然能打开。
> 服务器要求很低：1 核 1G、20G 盘、能出网即可；后端是单进程 FastAPI + SQLite。

## 0. 先确认一件事：域名要能改 DNS

`eu.cc` 是免费二级域名，通常在你注册它的那个面板里管理解析（有的叫 DNS / 解析 / Nameservers）。
进去加一条 **A 记录**：

| 主机记录 | 类型 | 值 | TTL |
|---|---|---|---|
| `durkmo`（或 `@`，看面板要求） | A | **你的服务器公网 IP** | 600 |

验证（本地电脑执行，返回的是你服务器 IP 就对了）：

```powershell
nslookup durkmo.eu.cc 8.8.8.8
```

⚠️ 两个坑先说清：
- **服务器在境内**：`.eu.cc` 不是境内可备案的域名，80/443 绑域名访问可能被拦。要么换境外/香港机，要么先用 IP+端口给评委。
- **服务器在境外**：直接可用，Caddy 会自动申请 Let's Encrypt 证书，前提是 80/443 端口对公网开放（云厂商安全组要放行）。

## 1. 最省事的路径（你可以完全不给我权限）

服务器上执行（Ubuntu/Debian，root 或 sudo）：

```bash
# 一条命令，脚本自己装 Docker、拉代码、建 .env、灌演示数据、起服务
curl -fsSL https://raw.githubusercontent.com/vesoandrei181-oss/agentdesk/main/deploy/deploy.sh -o deploy.sh
LLM_API_KEY=sk-你的key SITE_ADDRESS=durkmo.eu.cc bash deploy.sh
```

脚本停下来时，编辑 `/opt/agentdesk/deploy/.env` 确认三项：`LLM_API_KEY`、`SECRET_KEY`（脚本已随机生成）、`SITE_ADDRESS`，然后重跑同一条命令即可。

完成后验证：

```bash
curl -fsS https://durkmo.eu.cc/api/health
# 期望 {"ok":true,"provider":"deepseek","mock":false,...}
```

## 2. 如果要我来操作，需要给我这些

| 需要的信息 | 说明 |
|---|---|
| 服务器公网 IP | 形如 `1.2.3.4` |
| SSH 端口 | 默认 22 |
| 用户名 | `root` 或带 sudo 的普通用户 |
| 认证方式 | 密码，或私钥文件（`id_rsa` 内容/路径） |
| 系统版本 | `cat /etc/os-release` 的前两行 |

发我之后我做的事：装 Docker → 拉代码 → 写 `deploy/.env`（密钥随机生成，模型 key 用你给的那个）→ 构建镜像 → 灌演示数据 → 起 Caddy 自动签证书 → 从公网侧验证登录和问答 → 给你改动清单。

**安全建议（不是客套，是操作顺序）**：完事之后改一次 SSH 密码或删掉那把临时公钥；如果你愿意，先新建一个 `deploy` 用户给他 sudo，用完 `deluser deploy`。

## 3. 手动部署（不想跑脚本、也不想给权限）

```bash
# 装 Docker
curl -fsSL https://get.docker.com | sh

# 拉代码
git clone https://github.com/vesoandrei181-oss/agentdesk.git /opt/agentdesk
cd /opt/agentdesk

# 配置
cp deploy/.env.example deploy/.env
nano deploy/.env        # 填 LLM_API_KEY、SECRET_KEY、SITE_ADDRESS=durkmo.eu.cc

# 起服务（首次会构建镜像，5-10 分钟；npm 慢就加 --build-arg NPM_REGISTRY=https://registry.npmmirror.com）
docker compose -f deploy/docker-compose.yml up -d --build

# 灌演示数据
docker compose -f deploy/docker-compose.yml run --rm --entrypoint python api apps/api/seed/demo.py --force

# 看日志
docker compose -f deploy/docker-compose.yml logs -f --tail=100
```

## 4. 不用 Docker 的裸机方案（可选）

```bash
apt-get update && apt-get install -y python3.12-venv python3-pip caddy
cd /opt/agentdesk
python3 -m venv .venv && .venv/bin/pip install -r apps/api/requirements.txt
mkdir -p apps/web/dist && cp -r <本地构建好的 dist>/* apps/web/dist/   # 或 scp -r 上传
PYTHONPATH=apps/api .venv/bin/python apps/api/seed/demo.py --force
```

systemd 单元 `/etc/systemd/system/agentdesk.service`：

```ini
[Unit]
Description=AgentDesk
After=network.target

[Service]
WorkingDirectory=/opt/agentdesk
Environment=PYTHONPATH=/opt/agentdesk/apps/api
Environment=LLM_API_KEY=sk-你的key
Environment=SECRET_KEY=换成随机串
ExecStart=/opt/agentdesk/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always

[Install]
WantedBy=multi-user.target
```

`/etc/caddy/Caddyfile`：

```
durkmo.eu.cc {
    encode zstd gzip
    reverse_proxy 127.0.0.1:8000
}
```

```bash
systemctl daemon-reload && systemctl enable --now agentdesk caddy
```

## 5. 上线后要改的文件

域名生效后，把这三处 URL 从 `*.trycloudflare.com` 换成 `https://durkmo.eu.cc`，然后提交：

- `README.md` 顶部「在线演示」
- `deploy/README.md` 顶部「当前在线演示」
- `docs/交付清单.md` 第 13 行

## 6. 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 证书申请失败 | 80/443 没放行，或 DNS 还没生效 | 安全组放行 + `dig durkmo.eu.cc` 确认 |
| 502 | api 容器没起来 | `docker compose logs api`，多半是 `LLM_API_KEY` 为空 |
| 页面 404 白屏 | 构建产物路径不对 | 确认镜像里 `/app/apps/web/dist/index.html` 存在 |
| 登录报 401 反复跳转 | `SECRET_KEY` 变了导致旧 token 失效 | 重新登录即可 |
| 中文导出 Word 乱码 | 镜像缺字体 | Dockerfile 里已装 `fonts-noto-cjk`，裸机方案要 `apt install fonts-noto-cjk` |
