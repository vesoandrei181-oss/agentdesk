# 智协台 AgentDesk · 任务清单 v2（Web 版）

> 选题：AI 协同办公工具 —— 利用 AI 技术提升办公效率的 **Web 工具**
> 形态：浏览器访问的 SaaS 协同办公台（桌面优先，响应式兼容平板）
> 定位：把「会议 → 决议 → 任务 → 文档 → 复盘」这条办公主线，交给一支可审计的 AI 协作小队

---

## 0. 一句话产品定义

**AgentDesk = 多智能体会议纪要 + 可溯源知识问答 + Diff 级 AI 写作 + 自动任务排程**，
四件事共用一个「证据链」，每条 AI 结论都能点回原始录音时间戳 / 文档页码 / 原文片段。

核心差异：市面上 90% 的办公 AI 是「一个输入框 + 一段总结」，我们做的是
**有角色分工、有自检、有证据、有成本账本**的 AI 流水线，并且把这条流水线的执行轨迹
（每步 token / 耗时 / 证据）直接做成可视化面板给用户和评委看。

---

## 1. 对标评分表 · 抢分策略

| 维度 | 权重 | 我们的落点 | 可验收证据 |
|---|---|---|---|
| AI 技术深度 | 35% | 自研轻量编排核（非黑盒框架）+ 6 Agent 协作 + 证据链 + 混合检索 RRF/Rerank + 语义缓存 + 模型路由 + 结构化输出契约 | 自建评测集跑出的对比表：幻觉率、groundedness、Hit@5、MRR、token 成本、P95 延迟、缓存命中率 |
| 创新性 | 25% | 证据链纪要、Agent Trace 可视化、Diff 级写作、P50/P90 工期预测、隐私脱敏网关、办公闭环 | 7 个创新点逐条对应到可点击的功能与文档章节 |
| 前端工程质量 | 10% | Vite+React18+TS 严格模式、分层组件库、设计 token、虚拟列表、路由懒加载、Vitest+Playwright、ESLint/Prettier/Husky/commitlint、CI | Lighthouse ≥ 95、单测覆盖率 ≥ 70%、E2E 全绿、bundle 分析报告 |
| 实用性 | 10% | 真实办公动线：录完会 3 分钟出纪要并自动派活；问答带页码引用；周报自动出 | 端到端演示脚本（3 条真实业务场景） |
| 用户体验 | 10% | 键盘流（⌘K 命令面板）、流式输出、骨架屏、乐观更新、暗色模式、可访问性 | 交互走查清单 + 录屏 |
| 社会价值与商业潜力 | 10% | 中小企业/高校团队低门槛用上 AI 办公；隐私脱敏 + 本地模型可选；按量计费成本模型 | 成本模型表（每人每月成本）+ 目标客户画像 + 可持续性论证 |

---

## 2. 创新点（技术 6 + 应用 4，均带证据）

### 技术侧
1. **证据链纪要（Evidence-Chained Minutes）**
   每条决议/待办强制携带 `evidence = {segment_id, start_ms, end_ms, quote, confidence}`，
   前端点击任意结论即跳转播放对应录音片段。无证据的结论不入库。
2. **6 角色 Agent 协作 + Critic 自检回环**
   `Scribe`（转写清洗/说话人归并）→ `Segmenter`（议题切分）→ `Decider`（决议抽取）→
   `Planner`（待办/负责人/截止）→ `Critic`（groundedness 打分，< 阈值打回重生成，最多 2 轮）→
   `Composer`（成稿）。实测目标：幻觉率相对单 Agent 下降 ≥ 60%。
3. **Diff 级 AI 写作**：不做「整篇重写」，输出段落级 patch（`op: insert|replace|delete` + 理由 + 引用），
   用户逐条采纳/拒绝，编辑器内联 diff 高亮；配合**风格指纹**（句长、术语表、语气向量）做个性化迁移。
4. **混合检索 + 引用校验**：`BM25(pgvector tsvector) ⊕ 向量(bge-m3)` → RRF 融合 → `bge-reranker` 精排 →
   生成后做 **citation verification**（回答中每个引用句回查切片，不匹配则降级为「未找到依据」）。
5. **语义缓存 + 三级模型路由**：embedding 相似度 ≥ 0.95 命中缓存（跨用户脱敏后共享）；
   路由档位 `质量 / 均衡 / 省钱 / 隐私本地(Ollama)`，前端可切换并实时显示成本与延迟差异。
6. **结构化输出契约 + 自愈重试**：JSON Schema 强约束 + Pydantic 校验 + 失败自动修复提示重试（≤2 次），
   结构化成功率目标 ≥ 99%；编排核自研（~1.5k 行），零 LangChain 依赖，Provider 可插拔。

### 应用 / 模式侧
7. **会议→任务→周报自动闭环**：纪要里的待办直接落成任务卡（负责人/DDL/依赖），
   周末自动聚合生成周报（含逾期风险与工时统计），无需人工搬运。
8. **Agent Trace 透明面板**：把上述流水线每一步的输入摘要、耗时、token、命中缓存、证据条数做成时间轴，
   用户可点开任意一步看原始 prompt/输出 —— 把「AI 黑盒」变成「可审计流水线」。
9. **隐私脱敏网关**：入模前做 PII 识别（正则 + 小模型）→ 占位符替换 → 模型输出后做 format-preserving 回填，
   敏感词命中可强制走本地模型，全程留审计日志。
10. **任务工期预测 + 风险重排**：LLM 给先验、历史任务训练轻量回归给校正，输出 P50/P90 区间；
   对逾期风险 > 阈值的任务自动给出重排建议（约束满足 + 贪心）。

---

## 3. 功能范围

### P0（必须全通，构成演示主线）
| 模块 | 关键能力 |
|---|---|
| 账号与团队 | 邮箱/演示账号登录、团队空间、RBAC（Owner/Admin/Member/Viewer）、邀请码 |
| 会议中心 | 上传音视频 / 浏览器录音 → ASR → 说话人分离 → 议题切分 → 证据链纪要 → 决议 & 待办 → 一键成任务 → 导出 MD/PDF |
| AI 写作台 | 块编辑器（标题/正文/列表/表格/代码）、选区或全文 AI 指令、Diff 采纳、风格校准、版本历史 |
| 文档分析（RAG） | 上传 PDF/DOCX/MD/TXT → 解析切分 → 混合检索 → 流式问答 + 页码级引用跳转 + 多文档对照 |
| 项目看板 | Kanban 拖拽、优先级、AI 工期预测 P50/P90、逾期风险徽标、任务详情抽屉 |
| 周报与洞察 | 自动周报、会议/任务热力图、AI 使用量与成本看板 |
| 设置 | 模型路由、脱敏开关、API Key 管理、用量与成本、审计日志 |
| Agent Trace | 流水线可视化时间轴 + 单步详情 |

### P1（时间允许则做，作为加分）
实时协作在线状态与评论锚点（WebSocket）· 模板市场 · 自定义 Agent（Prompt 编排 UI）· 邮件/飞书 Webhook 通知

### P2（文档里写"规划中"）
移动端 PWA 离线 · 日历双向同步 · 企业微信/钉钉集成

### 页面清单（12 个路由）
`/login` `/` 工作台 `/meetings` `/meetings/:id` `/write/:docId` `/docs`(知识库) `/chat/:kbId`
`/board` `/insights` `/settings` `/team` `/trace/:runId`

---

## 4. 技术架构

```
浏览器 (React 18 + TS + Vite)
  ├─ 设计系统 @agentdesk/ui (tokens + 40+ 组件, 暗色模式)
  ├─ 状态: Zustand(客户端) + TanStack Query(服务端缓存/乐观更新)
  ├─ 编辑器: TipTap/ProseMirror(块模型 + 内联 diff 装饰器)
  ├─ 可视化: Recharts(图表) + 自绘 Trace 时间轴
  └─ 通信: REST(OpenAPI 生成客户端) + SSE(AI 流式) + WS(协作/队列进度)
        │
FastAPI (Python 3.12)  ── 编排核 agentdesk_core (自研)
  ├─ providers: openai-compatible / deepseek / qwen / ollama (统一 Protocol)
  ├─ pipeline: scribe → segmenter → decider → planner → critic → composer
  ├─ rag: parser(pdf/docx/md) → chunker(标题层级+语义) → bm25+vec → rrf → rerank → verify
  ├─ cache: 语义缓存(Redis + 向量索引) · prompt 压缩 · token 预算
  ├─ guard: PII 脱敏网关 · 引用校验 · 结构化输出校验/自愈
  └─ 任务队列: arq(异步 ASR/解析/批处理) · 进度回推 WS
        │
PostgreSQL 16 + pgvector  ·  Redis 7  ·  MinIO/本地对象存储  ·  ffmpeg(faster-whisper ASR)
```

**选型理由（文档要重点写的部分）**
- 不用 LangChain：链路只有 6 个角色、需要强契约与逐步入库审计，自研 1.5k 行可控、可测、可解释，避免框架黑盒与版本漂移。
- Vite 而非 Next.js：内部工具无需 SSR/SEO，静态托管部署最简单、构建最快，评委打开即用。
- SSE 而非 WebSocket 做 AI 流式：单向流、过代理友好、断线自动重连；WS 只用于协作与队列进度。
- pgvector 而非独立向量库：单库事务一致性 + 部署成本低，HNSW 索引在万级切片下 P95 < 50ms。

**降级与韧性（三层）**
1. 真模型在线跑；2. 无 Key 时读**录制回放缓存**（真实响应的快照，演示 100% 可跑）；
3. 后端不可达时前端切**静态演示快照**（打包 JSON），核心页面仍可浏览。

---

## 5. 代码仓库

Monorepo（pnpm workspace），Public：

```
agentdesk/
├─ apps/web/                React 前端（Vite）
├─ apps/api/                FastAPI 后端 + agentdesk_core 编排核
├─ packages/shared/         TS 类型 + OpenAPI 客户端（自动生成）
├─ packages/ui/             设计系统与组件库
├─ docs/                    技术文档源（HTML→PDF）、架构图、评测报告、演示脚本
├─ deploy/                  docker-compose / Caddy / Cloudflare Pages / Fly.io
├─ scripts/                 种子数据、评测跑分、Playwright 演出录屏、TTS 合成
├─ .github/workflows/       ci( lint+test+build )、deploy、keepalive
├─ README.md  LICENSE  CONTRIBUTING.md  .env.example  Makefile
```

**Git 策略**：conventional commits，按里程碑真实提交（目标 ≥ 45 条），
分支 `main` 保护 + `feat/*` 合并，每个功能带 feat/test/docs 三次提交，保留真实演进痕迹。

---

## 6. 交付物清单（7 件，含验收标准）

| # | 交付物 | 形态 | 验收标准 |
|---|---|---|---|
| 1 | 代码仓库 | GitHub Public | README 五段（介绍/架构/运行/团队/致谢）、`.env.example`、依赖清单、CI 绿、≥45 提交、可 `make up` 一键起 |
| 2 | Web 应用 | 本地 + 公网 | 12 路由可用，P0 全通，Lighthouse ≥ 90/95 |
| 3 | 后端 API | 本地 + 公网 | OpenAPI 文档齐全，`/healthz`、限流、鉴权、错误码规范 |
| 4 | 技术文档 PDF | ≤ 30 页（控 26–28 页） | 7 章齐全 + AI 技术专项（选型/集成/优化）+ 创新点章节 + 指标表 + 架构图 |
| 5 | 演讲稿 | 6 分 30 秒版 + 4 分钟精简版 | 逐字稿 + 时间轴 + 提词卡 + 10 条 Q&A 预案 |
| 6 | 演示视频 | MP4 1080p，7 分钟 | Playwright 自动演出录屏 + 中文旁白 + SRT 字幕（可替换真人配音） |
| 7 | 评审材料包 | 单页 | 在线地址、体验账号、评分对标表、亮点一页纸、部署拓扑图 |

---

## 7. 执行里程碑

| 批次 | 内容 | 产出 | 预计 |
|---|---|---|---|
| M0 | 立项、仓库骨架、设计 token、API 契约、CI | 可运行空壳 + 绿 CI | 0.5 天 |
| M1 | 后端编排核 + RAG + 数据模型 + 种子数据 + 回放缓存 | 可 curl 全链路 | 1.5 天 |
| M2 | 前端框架 + 设计系统 + 工作台/登录/团队 | 可点页面 | 1 天 |
| M3 | 会议中心 + 写作台 + 文档分析 + 看板 + Trace（P0 全通） | 端到端闭环 | 2.5 天 |
| M4 | 自建评测集跑分、指标优化、消融对比 | 评测报告表 | 1 天 |
| M5 | 部署：Cloudflare Pages + Fly.io + Neon + Upstash，演示账号，保活 | 公网可访问 | 0.5 天 |
| M6 | 技术文档 PDF + 演讲稿 + 视频录制合成 | 三份材料 | 1 天 |
| M7 | 按评分表逐项自评走查、修漏 | 走查表 | 0.5 天 |

---

## 8. 在线演示（加分项 · 已纳入主计划）

- 前端：Cloudflare Pages（免费、全球 CDN、公网 HTTPS）
- 后端：Fly.io / Render（容器）+ Neon Postgres(pgvector) + Upstash Redis
- 账号：`demo@agentdesk.dev / Demo@2026`（预置团队、3 场会议、5 份文档、1 个看板）
- 保活：GitHub Actions 每 10 分钟 `/healthz` + 每日快照；静态兜底页单独托管，主站挂了也能演示
- 页面顶部展示「AI 服务：在线 / 回放 / 快照」三态徽标，评审任何时刻点开都有东西看

---

## 9. 需要你配合的 5 件事

1. **GitHub 授权**：我跑 `gh auth login` 时会给你一个浏览器授权链接，你点确认即可（或直接给我一个 PAT：`repo` + `workflow`）。
2. **部署账号**（任选，有哪个给哪个）：Cloudflare / Fly.io / Render / Vercel；或一台能 SSH 的 VPS（Docker 一把梭）。
3. **LLM API Key**（任选其一，DeepSeek 最省）：有了跑真模型；没有我就用回放缓存 + 本地 Ollama，演示照样通。
4. **比赛/团队信息**：队名、成员姓名与分工、学校/单位（写进 README「团队信息」和文档封面）。
5. **演示视频**：我出自动演出录屏 + 中文 TTS 旁白；若要真人出镜/真人配音，你给一段 7 分钟人声我替换音轨。

---

## 10. 风险与对策

| 风险 | 对策 |
|---|---|
| 评审期服务休眠/挂掉 | 三层降级（真模型/回放/静态快照）+ 定时保活 + 独立静态兜底站 |
| 无 API Key | 回放缓存内置 20 组真实响应；本地 Ollama 兜底；`DEMO_MODE` 一键切换 |
| 文档超 30 页 | 模板先定版式（A4/10.5pt/双栏图），写作时按 28 页硬控，图表用矢量 |
| 前端分数被扣 | 单测 + E2E + Lighthouse 报告 + bundle 分析，全部贴进文档 |
| 演示翻车 | 演示路径三条，全部走预置种子数据，不依赖现场网络生成 |
