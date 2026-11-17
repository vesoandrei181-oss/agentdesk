#!/usr/bin/env bash
# AgentDesk 服务器一键部署（Ubuntu / Debian，root 或 sudo 用户执行）
#
#   bash deploy/deploy.sh            # 首次部署或更新
#   bash deploy/deploy.sh --reset    # 清空演示数据后重新生成
#
# 做四件事：装 Docker（若缺）→ 拉代码 → 写 deploy/.env（若缺）→ 构建并启动
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/vesoandrei181-oss/agentdesk.git}"
APP_DIR="${APP_DIR:-/opt/agentdesk}"
DOMAIN="${SITE_ADDRESS:-durkmo.eu.cc}"

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
  say "生成 deploy/.env（请立刻填入 LLM_API_KEY 与 SECRET_KEY）"
  cp deploy/.env.example deploy/.env
  SECRET=$(head -c 32 /dev/urandom | base64 | tr -d '=+/' | cut -c1-40)
  sed -i "s|^SITE_ADDRESS=.*|SITE_ADDRESS=${DOMAIN}|" deploy/.env
  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET}|" deploy/.env
  if [ -n "${LLM_API_KEY:-}" ]; then
    sed -i "s|^LLM_API_KEY=.*|LLM_API_KEY=${LLM_API_KEY}|" deploy/.env
  else
    echo "!! 还没填 LLM_API_KEY：编辑 $APP_DIR/deploy/.env 后重新执行本脚本"
    exit 1
  fi
fi

# 4. 前端产物：镜像里用 node 阶段现构建（多阶段 Dockerfile），服务器不需要装 node。
#    若服务器拉 npm 很慢，执行时带上镜像源：NPM_REGISTRY=https://registry.npmmirror.com bash deploy/deploy.sh

# 5. 演示数据
mkdir -p data
if [ "${1:-}" = "--reset" ] || [ ! -f data/agentdesk.db ]; then
  say "初始化演示数据（3 场会议 / 16 条任务 / 3 份知识资料 / 14 天运行记录）"
  docker compose -f deploy/docker-compose.yml run --rm --entrypoint python api apps/api/seed/demo.py --force
fi

# 6. 启动
say "构建并启动"
docker compose -f deploy/docker-compose.yml up -d --build ${BUILD_ARGS:-}

say "等待健康检查"
for i in $(seq 1 40); do
  if curl -fsS http://127.0.0.1/api/health >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -fsS "https://${DOMAIN}/api/health" || curl -fsS http://127.0.0.1/api/health
cat <<EOF

部署完成。
  站点：https://${DOMAIN}
  账号：demo@agentdesk.dev / Demo@2026
  日志：docker compose -f deploy/docker-compose.yml logs -f --tail=100
  重启：docker compose -f deploy/docker-compose.yml restart
EOF
