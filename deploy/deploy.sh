#!/usr/bin/env bash
# AgentDesk 服务器一键部署（Ubuntu / Debian，root 或 sudo 用户执行）
#
# 两种模式：
#   bash deploy/deploy.sh                 # 公网 IP + 域名：Caddy 直接签 HTTPS（要 80/443 开放）
#   MODE=tunnel bash deploy/deploy.sh     # 服务器在内网 / 无法开放端口：走 Cloudflare Tunnel
#
# 可选环境变量：
#   SITE_ADDRESS        域名，默认 agentdesk.2007116.xyz；tunnel 模式下留空不影响
#   LLM_API_KEY         必填（DeepSeek Key）
#   CLOUDFLARE_TUNNEL_TOKEN  tunnel 模式下必填（Zero Trust 里创建的隧道 token）
#   NPM_REGISTRY        前端依赖源，境内建议 https://registry.npmmirror.com
#   --reset             清空并重建演示数据
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/vesoandrei181-oss/agentdesk.git}"
APP_DIR="${APP_DIR:-/opt/agentdesk}"
DOMAIN="${SITE_ADDRESS:-agentdesk.2007116.xyz}"
MODE="${MODE:-standalone}"
TUNNEL_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN:-}"

if [ "$MODE" = "tunnel" ]; then
  COMPOSE="deploy/docker-compose.tunnel.yml"
else
  COMPOSE="deploy/docker-compose.yml"
fi

say() { printf '\033[1;36m== %s\033[0m\n' "$*"; }

# 1. Docker
if ! command -v docker >/dev/null 2>&1; then
  say "安装 Docker"
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
else
  say "Docker 已安装：$(docker --version)"
fi
if ! docker compose version >/dev/null 2>&1; then
  say "安装 compose 插件"
  apt-get update -y && apt-get install -y docker-compose-plugin
fi

# 2. 代码
if [ -d "$APP_DIR/.git" ]; then
  say "更新代码"
  git -C "$APP_DIR" fetch --all --prune
  git -C "$APP_DIR" reset --hard origin/main
else
  say "克隆代码到 $APP_DIR"
  mkdir -p "$(dirname "$APP_DIR")"
  git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

# 3. 环境变量
if [ ! -f deploy/.env ]; then
  say "生成 deploy/.env"
  cp deploy/.env.example deploy/.env
  SECRET=$(head -c 32 /dev/urandom | base64 | tr -d '=+/' | cut -c1-40)
  sed -i "s|^SITE_ADDRESS=.*|SITE_ADDRESS=${DOMAIN}|" deploy/.env
  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET}|" deploy/.env
  sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=https://${DOMAIN}|" deploy/.env
  if [ -n "${LLM_API_KEY:-}" ]; then
    sed -i "s|^LLM_API_KEY=.*|LLM_API_KEY=${LLM_API_KEY}|" deploy/.env
  else
    echo "!! 还没填 LLM_API_KEY：编辑 $APP_DIR/deploy/.env 后重新执行本脚本"
    exit 1
  fi
fi

# 4. 前端产物在镜像的 node 阶段构建，服务器不需要 node。
#    境内拉 npm 慢就加：NPM_REGISTRY=https://registry.npmmirror.com

# 5. 演示数据
mkdir -p data
if [ "${1:-}" = "--reset" ] || [ ! -f data/agentdesk.db ]; then
  say "初始化演示数据（3 场会议 / 16 条任务 / 3 份知识资料 / 14 天运行记录）"
  docker compose -f "$COMPOSE" run --rm --entrypoint python api apps/api/seed/demo.py --force
fi

# 6. 启动
say "构建并启动（$MODE 模式）"
docker compose -f "$COMPOSE" up -d --build

say "等待健康检查"
HEALTH_URL="http://127.0.0.1:8000/api/health"
for _ in $(seq 1 90); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -fsS "$HEALTH_URL" || { echo "!! /api/health 没起来，看日志：docker compose -f $COMPOSE logs -f --tail=100"; exit 1; }

# 7. tunnel 模式：装 cloudflared 并常驻
if [ "$MODE" = "tunnel" ]; then
  if ! command -v cloudflared >/dev/null 2>&1; then
    say "安装 cloudflared"
    ARCH=$(uname -m); case "$ARCH" in x86_64) CF=amd64 ;; aarch64) CF=arm64 ;; *) CF=amd64 ;; esac
    URL="${CF_DEB_URL:-https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF}.deb}"
    curl -fsSL "$URL" -o /tmp/cloudflared.deb || {
      echo "!! 下载 cloudflared 失败，可手动上传 deb 后执行：dpkg -i /tmp/cloudflared.deb"
      echo "   境内可试：https://gh-proxy.com/${URL#https://}"
      exit 1
    }
    dpkg -i /tmp/cloudflared.deb || apt-get install -f -y
  fi
  if [ -z "$TUNNEL_TOKEN" ]; then
    echo "!! tunnel 模式需要 CLOUDFLARE_TUNNEL_TOKEN（Zero Trust → Networks → Tunnels 里复制）"
    echo "   API 已在 127.0.0.1:8000 跑起来，拿到 token 后执行："
    echo "   cloudflared service install <TOKEN>"
    exit 0
  fi
  say "注册 cloudflared 系统服务"
  cloudflared service install "$TUNNEL_TOKEN"
  systemctl enable --now cloudflared
  sleep 3
  systemctl --no-pager --lines=5 status cloudflared || true
fi

cat <<EOF

部署完成。
  访问：$([ "$MODE" = "tunnel" ] && echo "https://${DOMAIN}（Cloudflare 隧道，需已在 Zero Trust 配好 Public Hostname）" || echo "https://${DOMAIN}")
  账号：demo@agentdesk.dev / Demo@2026
  日志：docker compose -f $COMPOSE logs -f --tail=100
  重启：docker compose -f $COMPOSE restart
  本机自检：curl -s $HEALTH_URL
EOF
