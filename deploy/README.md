# AgentDesk 部署说明

三条路径，按「演示优先级」排列。第一条 5 分钟能拿到公网地址，第二三条适合长期挂着。

## 一、快速公网演示（Cloudflare 快速隧道，无需账号）

```powershell
# 1. 起后端（同时托管前端静态文件）
cd apps\api
$env:LLM_API_KEY="<你的 LLM Key>"
$env:PYTHONPATH="$PWD"
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2. 另开一个窗口，把 8000 端口暴露到公网
.\cloudflared.exe tunnel --url http://127.0.0.1:8000 --no-autoupdate

# 日志里会打印 https://xxxx.trycloudflare.com，评审直接用这个地址
```

注意：快速隧道的域名是随机的，进程一停就失效。评审期间请让它常驻
（用 `scripts\run_demo.ps1`，或把命令注册成计划任务）。

## 二、自有服务器（推荐长期方案）

准备：一台 2 核 4G 以上的 Linux、一个已解析到该服务器的域名。

```bash
git clone <仓库地址> agentdesk && cd agentdesk
cp .env.example .env && vim .env          # 填 LLM_API_KEY、SECRET_KEY
docker compose -f deploy/docker-compose.yml up -d --build
docker compose -f deploy/docker-compose.yml exec api python seed/demo.py
```

`deploy/docker-compose.yml` 里已经包含：

- `api`：FastAPI + 静态站点，8000 端口只监听内网；
- `caddy`：自动申请 Let's Encrypt 证书，反代 80/443；
- 数据卷 `./data`：SQLite、上传文件、缓存都落在这里，容器重建不丢。

## 三、Cloudflare 命名隧道 + 自有域名

不想开服务器端口时用这个，需要登录一次 Cloudflare 账号：

```powershell
.\cloudflared.exe tunnel login
.\cloudflared.exe tunnel create agentdesk
.\cloudflared.exe tunnel route dns agentdesk demo.你的域名.com
.\cloudflared.exe tunnel run --url http://127.0.0.1:8000 agentdesk
```

## 四、评审账号

| 账号 | 密码 | 角色 |
| --- | --- | --- |
| demo@agentdesk.dev | Demo@2026 | 产品负责人（演示主账号） |
| duchunxiao@agentdesk.dev | Demo@2026 | 前端负责人 |

演示数据包含 3 场会议、11 条决议、16 条任务、3 份知识库资料，登录即可看到完整看板，
不需要现场等模型跑。

## 五、环境变量

见仓库根目录 `.env.example`，关键项：

| 变量 | 说明 |
| --- | --- |
| `LLM_API_KEY` | 模型密钥，留空则自动降级为离线 Mock，界面仍可演示 |
| `LLM_BASE_URL` | 兼容 OpenAI 协议的地址，可换任何供应商或本地 Ollama |
| `LLM_MODEL_FAST` / `LLM_MODEL_QUALITY` | 快模型 / 质量模型 |
| `DATABASE_URL` | 默认 SQLite，换 PG 只改这一行 |
| `SEMANTIC_CACHE_THRESHOLD` | 语义缓存阈值，默认 0.95 |
| `PII_MASK` | 是否开启脱敏网关，默认 1 |
