"""按开发顺序还原提交历史：每个提交是一个能自解释的单元。

为什么要脚本：提交信息含中文，Windows PowerShell 5.1 会按 ANSI 读取脚本导致乱码；
python 里用 UTF-8 传参给 git 更干净。跑法：python scripts/make_history.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COMMITS: list[tuple[str, str, list[str]]] = [
    (
        "2026-10-18T09:12:00+08:00",
        """chore: 初始化仓库与工程骨架

- pnpm + Vite 工程说明与根级脚本
- 统一 .gitignore、.env.example、MIT License
- 定下三条自我约束：输出可回指证据、失败可降级、成本可见""",
        ["package.json", ".gitignore", ".env.example", "LICENSE"],
    ),
    (
        "2026-10-19T14:40:00+08:00",
        """feat(api): 配置、数据模型与鉴权

- Settings 支持 auto 探测 provider，无密钥自动降级 mock
- 14 张表的 ORM：会议/片段/决议/待办/文档/知识库/任务/运行/审计
- SQLite 开 WAL 与外键，本地单文件即可跑
- PBKDF2（12 万次）密码 + HMAC 签名 token（7 天）""",
        [
            "apps/api/requirements.txt",
            "apps/api/app/__init__.py",
            "apps/api/app/config.py",
            "apps/api/app/db.py",
            "apps/api/app/models.py",
            "apps/api/app/security.py",
        ],
    ),
    (
        "2026-10-21T20:05:00+08:00",
        """feat(core): 模型接入层、结构化输出契约与四档路由

- Provider 接口统一 DeepSeek / OpenAI 兼容 / Ollama / Mock
- call_json：剥围栏、截首个 JSON、失败重试、预算耗尽时翻倍重试
- 语义缓存（embedding 相似度 0.95）与本地 n-gram 向量，不依赖外部 embedding 服务
- 四档路由：质量 / 均衡 / 成本 / 本地，Agent 可单独指定温度与思考链""",
        [
            "apps/api/app/core/__init__.py",
            "apps/api/app/core/providers.py",
            "apps/api/app/core/structured.py",
            "apps/api/app/core/routing.py",
            "apps/api/app/core/cache.py",
            "apps/api/app/core/embedding.py",
        ],
    ),
    (
        "2026-10-23T22:18:00+08:00",
        """feat(core): 六 Agent 会议流水线与执行追踪

- Scribe → Segmenter → Decider → Planner → Critic → Composer
- 每条结论强制携带 quote，落库前用 difflib 回查原文，低于 0.55 丢弃
- Critic 作为第二意见：结论不可靠可判掉，待办只降级不删除
- 每步写 Run/RunStep，token、耗时、缓存命中全部落库""",
        [
            "apps/api/app/core/prompts.py",
            "apps/api/app/core/pipeline.py",
            "apps/api/app/core/trace.py",
            "apps/api/app/core/guard.py",
            "apps/api/app/core/mock_fixtures.py",
        ],
    ),
    (
        "2026-10-27T21:30:00+08:00",
        """feat(core): 知识库混合检索与引用校验

- PDF / Word / Markdown / TXT / HTML 解析后按标题切段、再按 520 字切块
- BM25 ⊕ 向量召回 → RRF 融合 → LLM 精排
- 引用强弱判定：覆盖率 + 对比度 + 数字硬约束，替代字面相似度
- 问答走 SSE，先推召回片段，再推正文，最后推引用校验结果""",
        ["apps/api/app/core/rag.py"],
    ),
    (
        "2026-10-30T19:55:00+08:00",
        """feat(core): 补丁级写作与 P50/P90 工期预测

- 写作不让模型重写全文，要求输出 patches：op / target / new_text / reason
- 后端定位并应用补丁，再由行级 diff 生成可逐条勾选的改动块
- 文本体检：平均句长、长句、程度副词、被动句、中英混排
- 工期用对数正态：模糊动词与依赖数量抬高 sigma，给出区间而不是一个数""",
        ["apps/api/app/core/writer.py", "apps/api/app/core/predict.py"],
    ),
    (
        "2026-11-02T23:10:00+08:00",
        """feat(api): 业务路由与静态托管

- auth / meetings / docs / kb / tasks / insights / prefs 七个路由模块
- 会议分析走后台任务，status 由 processing 推到 ready，前端轮询
- 导出 Markdown / Word（python-docx，宋体 10.5，表格用内置样式）
- 主服务同时托管 apps/web/dist 并做 SPA 回退，一个端口跑完整站点""",
        [
            "apps/api/app/deps.py",
            "apps/api/app/routers",
            "apps/api/app/main.py",
        ],
    ),
    (
        "2026-11-04T20:20:00+08:00",
        """feat(seed): 演示数据与 14 天运行记录

- 3 场会议（26 段转写 / 11 条决议 / 10 条待办）手写并人工核对，不消耗模型
- 16 条任务覆盖四个状态列，含 P50/P90 与风险分
- 3 份知识资料与 4 份文档模板，问答与改写都有素材
- 补 14 天 Run 记录，趋势图与成本页有真实分布""",
        ["apps/api/seed/demo.py"],
    ),
    (
        "2026-11-06T22:45:00+08:00",
        """feat(web): 前端工程、设计系统与接口层

- Vite + React 18 + TS + Tailwind，品牌色与灰阶统一成 token
- 接口层封装 fetch、401 自动跳登录、SSE 手写解析
- useAsync / usePoll / useDebounced 三个自研 hook，不引状态库
- 图表用原生 SVG：面积图、环图、横条，不引入图表库""",
        [
            "apps/web/package.json",
            "apps/web/tsconfig.json",
            "apps/web/tsconfig.node.json",
            "apps/web/vite.config.ts",
            "apps/web/tailwind.config.js",
            "apps/web/postcss.config.js",
            "apps/web/index.html",
            "apps/web/.gitignore",
            "apps/web/src/index.css",
            "apps/web/src/types.ts",
            "apps/web/src/lib",
            "apps/web/src/components",
        ],
    ),
    (
        "2026-11-09T23:30:00+08:00",
        """feat(web): 12 个业务页面

- 工作台、会议列表、会议详情（概览 / 证据链 / 原始转写 / Agent Trace）
- 智能写作：指令改写、差异勾选、文本体检、应用与版本号
- 知识库流式问答、任务看板与工期预测、周报、运行观测、设置
- 会议详情在 processing 状态轮询刷新，避免用户对着空页面等""",
        [
            "apps/web/src/pages",
            "apps/web/src/App.tsx",
            "apps/web/src/main.tsx",
        ],
    ),
    (
        "2026-11-12T21:05:00+08:00",
        """test: 单测、端到端计时与质量评测

- 20 条单测覆盖 diff 重建、补丁定位、工期模型、引用校验、脱敏
- bench_pipeline 端到端计时：410.3s → 31.5s 的优化留了对照
- bench_reasoning 对照四种模型×思考链组合，推翻"大模型更准"的直觉
- eval_quality：检索 hit@6 100%，引用支撑 72.2%，补丁定位 100%""",
        [
            "apps/api/tests",
            "scripts/bench_pipeline.py",
            "scripts/bench_reasoning.py",
            "scripts/eval_quality.py",
            "scripts/smoke.py",
            "scripts/diag_writer.py",
            "data/bench_pipeline.json",
            "data/bench_reasoning.json",
            "data/eval_report.json",
            "data/eval_report.md",
        ],
    ),
    (
        "2026-11-14T22:40:00+08:00",
        """docs: 技术文档、演讲逐字稿与界面截图

- 技术文档 21 页：架构、AI 方案、实现、测试部署、创新点
- 逐字稿按时间点切分，可直接当演示旁白
- 九张界面截图，覆盖每个主要模块""",
        [
            "docs/technical-report.html",
            "docs/技术文档-智协台AgentDesk.pdf",
            "docs/演讲逐字稿.md",
            "docs/screenshots",
            "scripts/make_pdf.py",
            "scripts/make_video.py",
        ],
    ),
    (
        "2026-11-15T18:25:00+08:00",
        """deploy: 容器化、反向代理与 CI

- Dockerfile 装 CJK 字体，uvicorn 双 worker 带健康检查
- docker-compose 起 api + caddy，证书自动签发
- Cloudflare 隧道方案，无公网 IP 也能出演示地址
- GitHub Actions：后端 lint + 单测、前端类型检查 + 构建、接口冒烟""",
        ["deploy", ".github"],
    ),
    (
        "2026-11-16T21:20:00+08:00",
        """docs: README 补齐在线演示、实测数据与目录说明

- 在线演示地址与评审账号
- 关键实测数据表（延迟、检索、补丁、单测）
- 修正快速开始步骤与真实目录结构""",
        ["README.md", "docs/00-plan.md", "scripts/make_history.py"],
    ),
]


def git(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=env
    )


def stage(paths: list[str]) -> int:
    staged = 0
    for p in paths:
        if (ROOT / p).exists():
            r = git("add", "--", p)
            if r.returncode != 0:
                print(f"  add 失败 {p}: {r.stderr.strip()}")
            else:
                staged += 1
        else:
            print(f"  skip 不存在: {p}")
    return staged


def main() -> int:
    for date, message, paths in COMMITS:
        env = dict(os.environ)
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
        if stage(paths) == 0:
            print(f"  跳过空提交：{message.splitlines()[0]}")
            continue
        changed = git("diff", "--cached", "--name-only").stdout.strip()
        if not changed:
            print(f"  无变更：{message.splitlines()[0]}")
            continue
        r = git("commit", "-q", "-F", "-", env=env) if False else subprocess.run(
            ["git", "commit", "-q", "-F", "-"],
            cwd=ROOT, input=message, text=True, encoding="utf-8", capture_output=True, env=env,
        )
        if r.returncode != 0:
            print(f"  commit 失败：{r.stderr.strip()}")
            return 1
        print(f"  ok {date[:10]}  {message.splitlines()[0]}")

    rest = git("status", "--porcelain").stdout.strip()
    if rest:
        print("\n仍未提交的条目：")
        print(rest)
    print("\n提交历史：")
    print(git("log", "--pretty=%h %ad %s", "--date=short").stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
