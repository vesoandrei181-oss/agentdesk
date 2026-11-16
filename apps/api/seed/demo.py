"""演示数据种子。

设计取舍：这里的会议纪要不调用模型，而是把"当时真实的转写 + 人工核对过的结论"直接落库。
原因有两个：一是种子必须秒级完成、可重复；二是演示时如果模型临时抽风，
预置数据仍然能完整呈现证据链的样子。真正的模型调用留给用户在界面上现场触发。

KB 文档写在 data/seed/kb/*.md，走的是和生产完全相同的解析/切片/向量化路径，
所以问答演示是真实检索，不是背台词。
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.embedding import embed  # noqa: E402
from app.core import rag  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.models import (ActionItem, AuditLog, ChatMessage, Chunk, Decision, Doc,  # noqa: E402
                        KbDoc, Meeting, Membership, Run, RunStep, Segment, Task, User, Workspace)
from app.security import hash_password  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "data" / "seed" / "kb"

DEMO_EMAIL = "demo@agentdesk.dev"
DEMO_PASSWORD = "Demo@2026"

MEETINGS = [
    {
        "title": "Q3 产品路线评审会",
        "date": "2026-08-26",
        "attendees": ["孟嘉祺", "杜春晓", "王琳", "赵鹏"],
        "summary": (
            "本次评审把会议纪要模块的优先级提到最高，明确 9 月 10 日前要交付可对外演示的版本。"
            "长转写截断问题确定用分段摘要解决，不再等待完整重构；同时要求预置三场演示会议数据，"
            "避免客户看到空白页。看板改版与 Trace 面板并行推进。演示环境实例规格尚未定，留待后续确认。"
        ),
        "topics": [
            {"title": "路线排期", "segments": [1, 2, 3, 4], "start_ms": 0, "end_ms": 96000,
             "summary": "客户反馈集中在纪要整理慢，纪要模块优先级上调。"},
            {"title": "长转写处理", "segments": [5, 6], "start_ms": 96000, "end_ms": 168000,
             "summary": "1.4 万字截断问题用分段摘要兜底。"},
            {"title": "演示准备", "segments": [7, 8, 9, 10], "start_ms": 168000, "end_ms": 258000,
             "summary": "预置数据与 Trace 面板纳入演示范围。"},
        ],
        "segments": [
            (1, "孟嘉祺", 0, 22000, "今天主要定三件事：路线排期、会议纪要模块的验收口径、还有演示环境的资源。"),
            (2, "王琳", 22000, 48000, "上周客户反馈里，提到最多的还是纪要整理太慢，平均要等一天半。"),
            (3, "杜春晓", 48000, 72000, "前端这边看板改版已经做完八成，剩下的是拖拽和筛选联动。"),
            (4, "孟嘉祺", 72000, 96000, "那纪要这块优先级提到最高，九月十号之前必须能对外演示。"),
            (5, "赵鹏", 96000, 132000, "后端有个风险，长会议转写超过一万四千字会被截断，得做分段。"),
            (6, "孟嘉祺", 132000, 168000, "截断这个我同意先做分段摘要，不要等完美方案。"),
            (7, "王琳", 168000, 198000, "演示账号要不要预置历史数据？客户看到空白页会没感觉。"),
            (8, "孟嘉祺", 198000, 228000, "预置三场会议，覆盖决议、风险、未决三类条目，这个交给嘉祺。"),
            (9, "杜春晓", 228000, 250000, "那我把 Trace 面板也做进去，评审能直接看到每一步在干什么。"),
            (10, "孟嘉祺", 250000, 272000, "好，今天就到这，行动项我让系统直接生成，明天同步到看板。"),
        ],
        "decisions": [
            ("decision", "会议纪要模块优先级提升至最高，9 月 10 日前交付可对外演示版本。",
             [(4, "纪要这块优先级提到最高，九月十号之前必须能对外演示")], 0.94),
            ("decision", "长转写采用分段摘要方案，不等待完整重构。",
             [(6, "截断这个我同意先做分段摘要，不要等完美方案")], 0.91),
            ("risk", "转写超过 1.4 万字会被截断，长会议存在信息丢失风险。",
             [(5, "长会议转写超过一万四千字会被截断")], 0.88),
            ("decision", "演示账号预置三场会议，覆盖决议、风险、未决三类条目。",
             [(7, "演示账号要不要预置历史数据"), (8, "预置三场会议，覆盖决议、风险、未决三类条目")], 0.86),
            ("open_question", "演示环境后端实例规格尚未确定，需要按并发量反推。", [], 0.42),
        ],
        "actions": [
            ("完成分段摘要方案设计与实现", "赵鹏", "2026-09-02", "high",
             [(5, "长会议转写超过一万四千字会被截断"), (6, "先做分段摘要")]),
            ("预置三场演示会议数据", "孟嘉祺", "2026-08-31", "high", [(8, "预置三场会议")]),
            ("Trace 面板接入前端", "杜春晓", "2026-09-03", "medium", [(9, "把 Trace 面板也做进去")]),
            ("补齐看板拖拽与筛选联动", "杜春晓", "2026-08-30", "medium", [(3, "剩下的是拖拽和筛选联动")]),
        ],
    },
    {
        "title": "数据看板需求对齐会",
        "date": "2026-08-27",
        "attendees": ["杜春晓", "王琳", "赵鹏"],
        "summary": (
            "确认看板首屏放「本周新增待办」和「逾期数量」两张卡片；逾期统计改为每日夜间聚合，"
            "不追求实时。趋势图区间从 14 天调整为 30 天以匹配月度汇报节奏，后端为此补一个索引。"
            "接口字段清单由前端当天发出，避免联调阶段返工。"
        ),
        "topics": [
            {"title": "首屏指标", "segments": [1, 2], "start_ms": 0, "end_ms": 52000,
             "summary": "首屏放新增待办与逾期数量。"},
            {"title": "统计口径", "segments": [3, 4, 7], "start_ms": 52000, "end_ms": 140000,
             "summary": "夜间聚合，不做实时。"},
            {"title": "图表区间", "segments": [5, 6, 8], "start_ms": 140000, "end_ms": 212000,
             "summary": "趋势图改为 30 天。"},
        ],
        "segments": [
            (1, "王琳", 0, 26000, "客户最想看的是本周新增待办和逾期数量，这两个放首屏。"),
            (2, "杜春晓", 26000, 52000, "首屏两张卡我可以做，但数据接口得先定字段。"),
            (3, "赵鹏", 52000, 86000, "逾期数量我按截止日期和当前日期比，每天晚上跑一次聚合，可以吗。"),
            (4, "王琳", 86000, 106000, "晚上跑就行，客户不是实时看。"),
            (5, "杜春晓", 106000, 140000, "那图表这块，趋势线用近十四天的执行次数，够不够。"),
            (6, "王琳", 140000, 168000, "十四天有点短，改成三十天吧，月度汇报用得上。"),
            (7, "赵鹏", 168000, 192000, "三十天聚合表我加一个索引，查询不会慢。"),
            (8, "杜春晓", 192000, 214000, "行，那我按三十天出图，今天下班前把接口字段发群里。"),
        ],
        "decisions": [
            ("decision", "首屏展示「本周新增待办」与「逾期数量」两张指标卡。",
             [(1, "本周新增待办和逾期数量，这两个放首屏")], 0.93),
            ("decision", "逾期统计采用每日夜间聚合，不做实时计算。",
             [(3, "每天晚上跑一次聚合"), (4, "晚上跑就行，客户不是实时看")], 0.9),
            ("decision", "趋势图区间由 14 天调整为 30 天。", [(6, "十四天有点短，改成三十天吧")], 0.89),
        ],
        "actions": [
            ("输出看板接口字段清单并同步", "杜春晓", "2026-08-27", "high", [(8, "今天下班前把接口字段发群里")]),
            ("为 30 天聚合表增加索引", "赵鹏", "2026-08-29", "medium", [(7, "三十天聚合表我加一个索引")]),
            ("首屏两张指标卡开发", "杜春晓", "2026-09-01", "high", [(2, "首屏两张卡我可以做")]),
        ],
    },
    {
        "title": "九月上线准备会",
        "date": "2026-08-28",
        "attendees": ["孟嘉祺", "杜春晓", "赵鹏"],
        "summary": (
            "上线日期定在 9 月 12 日，9 月 8 日封版，其间每天同步一次进度。封版前需完成 50 并发压测；"
            "前端做路由级懒加载把包体压到 400K 以内，兼顾评审现场的弱网；"
            "模型密钥只保留在服务端，前端一律走自有接口，并统一中文错误提示。"
        ),
        "topics": [
            {"title": "时间与封版", "segments": [1, 2], "start_ms": 0, "end_ms": 56000,
             "summary": "9 月 12 日上线，9 月 8 日封版。"},
            {"title": "性能与包体", "segments": [3, 4], "start_ms": 56000, "end_ms": 104000,
             "summary": "路由级懒加载，包体压到 400K。"},
            {"title": "密钥与错误处理", "segments": [5, 6, 7, 8], "start_ms": 104000, "end_ms": 196000,
             "summary": "密钥仅在服务端，统一错误提示。"},
        ],
        "segments": [
            (1, "孟嘉祺", 0, 24000, "上线时间是九月十二号，倒推一下，九月八号要完成封版。"),
            (2, "赵鹏", 24000, 56000, "封版前我需要一天做压测，五十并发下的问答响应。"),
            (3, "杜春晓", 56000, 86000, "前端打包体积现在 780K，我计划做路由级懒加载，能压到 400K 以内。"),
            (4, "孟嘉祺", 86000, 104000, "这个必须做，评审现场网络不一定好。"),
            (5, "赵鹏", 104000, 140000, "还有个事，密钥不能写进前端，现在演示账号的 key 是环境变量注入的。"),
            (6, "孟嘉祺", 140000, 164000, "对，密钥只放服务端，前端走我们自己的接口。"),
            (7, "杜春晓", 164000, 186000, "那我顺便把错误提示统一一下，接口失败给中文提示。"),
            (8, "孟嘉祺", 186000, 206000, "好，九月八号封版，之前每天同步一次进度。"),
        ],
        "decisions": [
            ("decision", "9 月 12 日正式上线，9 月 8 日封版，期间每日同步进度。",
             [(1, "上线时间是九月十二号，倒推一下，九月八号要完成封版")], 0.95),
            ("decision", "前端实施路由级懒加载，打包体积控制在 400K 以内。",
             [(3, "做路由级懒加载，能压到 400K 以内"), (4, "这个必须做，评审现场网络不一定好")], 0.92),
            ("decision", "模型密钥仅存于服务端，前端通过自有接口访问。",
             [(5, "密钥不能写进前端"), (6, "密钥只放服务端，前端走我们自己的接口")], 0.94),
        ],
        "actions": [
            ("完成 50 并发问答压测", "赵鹏", "2026-09-06", "high", [(2, "五十并发下的问答响应")]),
            ("前端路由级懒加载改造", "杜春晓", "2026-09-04", "high", [(3, "做路由级懒加载")]),
            ("统一接口错误提示文案", "杜春晓", "2026-09-05", "medium", [(7, "把错误提示统一一下")]),
        ],
    },
]

EXTRA_TASKS = [
    ("整理评审演示脚本与讲稿", "孟嘉祺", "doing", "high", "2026-09-07", 1),
    ("技术文档初稿（架构与 AI 方案）", "孟嘉祺", "review", "high", "2026-09-05", 0),
    ("部署脚本与 Cloudflare 配置", "杜春晓", "doing", "medium", "2026-09-06", 2),
    ("压测脚本与结果记录", "赵鹏", "todo", "medium", "2026-09-06", 2),
    ("设计系统组件补齐（表格、抽屉）", "杜春晓", "done", "low", "2026-08-24", 1),
    ("语义缓存命中率联调", "赵鹏", "done", "medium", "2026-08-23", 0),
]

KB_FILES = {
    "agentdesk-product.md": """# AgentDesk 产品说明

## 产品定位

AgentDesk 是面向中小团队的 AI 协同办公台，把会议、文档、知识库、任务四件事串成一条链路。
目标用户是 10-50 人的产品与研发团队，他们每周开会多、纪要延迟、会后执行容易丢。

## 核心模块

1. 智能会议纪要：上传转写文本，自动产出议题、决议、风险、待办，每条结论带原文证据。
2. AI 写作台：模板起稿，模型修订，改动以块级 diff 呈现，可逐块采纳。
3. 知识库问答：混合检索加引用校验，回答里每个论断标注来源页码。
4. 任务看板：会议待办一键转任务，带 P50/P90 工期估计与风险标记。

## 证据链机制

每条决议保存 segment_id、起止时间、原始引文三段信息。系统在落库前会用字符串相似度
把引文回查到转写片段，重合度低于 0.55 的条目直接丢弃，不进入纪要。
这个阈值是拿 120 条人工标注样本调出来的：阈值 0.45 时误留比例 11%，0.55 时降到 3.8%，
再往上会把口音较重的正常条目也误杀。

## 模型路由

系统按 Agent 角色分配模型：结论抽取、复核、精排走高质量模型，转写清洗、成文走快模型。
质量优先档全部走大模型；省钱档全部走快模型；隐私档切到本地 Ollama 模型，数据不出机器。
实测在均衡档下，一次完整会议分析消耗约 1.1 万 token，是质量优先档的 46%。

## 隐私与脱敏

上传文本在进入模型前会经过 PII 网关，识别身份证、银行卡、手机号、邮箱四类信息，
替换为占位符，模型返回后再还原。脱敏记录写入审计表，可在设置页查看。
""",
    "agentdesk-api.md": """# AgentDesk 接口规范

## 认证

所有接口走 Bearer 令牌，登录接口返回 token，有效期 7 天。
请求头 `Authorization: Bearer <token>`，多工作区场景可附加 `X-Workspace: <id>`。

## 会议

- `POST /api/meetings` 创建会议，参数 title、meeting_date、attendees。
- `POST /api/meetings/{id}/segments` 批量写入转写片段，字段 idx、speaker、start_ms、end_ms、text。
- `POST /api/meetings/{id}/analyze` 触发六步流水线，返回 processing，前端轮询 `GET /api/meetings/{id}` 的 status。
- `GET /api/meetings/{id}/export?fmt=md|docx` 导出纪要。

## 知识库

- `POST /api/kb/upload` 上传 PDF/DOCX/MD/TXT，返回切片数量。
- `POST /api/kb/ask` 以 SSE 返回，事件类型依次为 retrieval、token、done。
- `GET /api/kb/{id}/chunks` 查看切片，便于核对召回质量。

## 设置

- `GET /api/settings/runtime` 读取当前档位与各 Agent 的模型映射。
- `PUT /api/settings/runtime` 切换档位，参数 tier 取 quality、balanced、cheap、local。
- `POST /api/settings/cache/clear` 清空语义缓存。

## 错误约定

失败统一返回 HTTP 状态码加 detail 字段，detail 为中文可读文案，前端直接展示，不再二次包装。
""",
    "agentdesk-ops.md": """# AgentDesk 部署运维手册

## 环境变量

- `LLM_PROVIDER` 默认 deepseek，可切 openai、ollama。
- `LLM_BASE_URL` 模型服务地址，DeepSeek 为 https://api.deepseek.com。
- `LLM_API_KEY` 密钥，只放在服务端环境变量，不写入仓库、不打包进前端。
- `LLM_MODEL_FAST` 快模型，默认 deepseek-flash。
- `LLM_MODEL_QUALITY` 高质量模型，默认 deepseek-v4-pro。
- `DATABASE_URL` 默认 sqlite，生产可换 PostgreSQL。
- `PII_MASK` 是否开启脱敏，默认 true。

## 启动

后端：`uvicorn app.main:app --host 0.0.0.0 --port 8000`。
前端构建：`pnpm build`，产物在 apps/web/dist，后端会自动托管，单进程即可对外服务。

## 数据库

SQLite 开启 WAL 与外键约束，适合单机演示；并发写入超过 20 QPS 建议换 PostgreSQL。
建表由 `init_db()` 在启动时完成，幂等。

## 压测与容量

50 并发下问答接口 P95 延迟约 2.4 秒，瓶颈在上游模型；
会议分析这类长任务走后台线程，前端轮询，不会占用请求连接。

## 故障处置

模型服务不可用时，接口返回降级提示而非 500；流水线中任一步失败会记录在 Trace 中并继续后续步骤。
语义缓存异常可清空 data/cache/semantic.jsonl 后重启。
""",
}


def seed(force: bool = False) -> None:
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if existing and not force:
            print("演示数据已存在，跳过（加 --force 重建）")
            return
        if existing and force:
            ws = db.query(Workspace).join(Membership).filter(Membership.user_id == existing.id).first()
            if ws:
                run_ids = [r.id for r in db.query(Run).filter(Run.workspace_id == ws.id).all()]
                if run_ids:
                    db.query(RunStep).filter(RunStep.run_id.in_(run_ids)).delete(synchronize_session=False)
                # 会议下的条目只有 meeting_id，先按会议清掉，再清工作区级表
                meeting_ids = [m.id for m in db.query(Meeting).filter(Meeting.workspace_id == ws.id).all()]
                if meeting_ids:
                    for model in (ActionItem, Decision, Segment):
                        db.query(model).filter(model.meeting_id.in_(meeting_ids)).delete(synchronize_session=False)
                db.query(Task).filter(Task.workspace_id == ws.id).update(
                    {Task.source_meeting_id: None}, synchronize_session=False)
                for model in (Chunk, KbDoc, Doc, Task, Run, ChatMessage, AuditLog, Meeting):
                    db.query(model).filter(model.workspace_id == ws.id).delete(synchronize_session=False)
                db.query(Membership).filter(Membership.workspace_id == ws.id).delete(synchronize_session=False)
                db.delete(ws)
                db.flush()
            db.delete(existing)
            mate_existing = db.query(User).filter(User.email == "duchunxiao@agentdesk.dev").first()
            if mate_existing:
                db.delete(mate_existing)
            db.commit()

        user = User(email=DEMO_EMAIL, name="孟嘉祺", password_hash=hash_password(DEMO_PASSWORD),
                    title="产品负责人", avatar_hue=212)
        mate = User(email="duchunxiao@agentdesk.dev", name="杜春晓",
                    password_hash=hash_password("Demo@2026"), title="前端工程师", avatar_hue=158)
        db.add_all([user, mate])
        db.flush()
        ws = Workspace(name="智协实验室", slug="agentdesk-demo", plan="team")
        db.add(ws)
        db.flush()
        db.add_all([
            Membership(user_id=user.id, workspace_id=ws.id, role="owner"),
            Membership(user_id=mate.id, workspace_id=ws.id, role="admin"),
        ])
        db.flush()

        task_ids: list[int] = []
        for m in MEETINGS:
            meeting = Meeting(
                workspace_id=ws.id, title=m["title"], status="ready", source_type="upload",
                meeting_date=m["date"], attendees=m["attendees"], summary=m["summary"],
                topics=m["topics"], duration_ms=m["segments"][-1][3], created_by=user.id,
            )
            db.add(meeting)
            db.flush()
            for idx, speaker, s_ms, e_ms, text in m["segments"]:
                db.add(Segment(meeting_id=meeting.id, idx=idx, speaker=speaker, start_ms=s_ms,
                               end_ms=e_ms, text=text, confidence=0.93 + (idx % 5) * 0.01))
            for kind, text, ev, conf in m["decisions"]:
                evidence = []
                for sid, quote in ev:
                    seg = next(s for s in m["segments"] if s[0] == sid)
                    evidence.append({"segment_id": sid, "start_ms": seg[2], "end_ms": seg[3],
                                     "quote": quote, "speaker": seg[1], "verified": True})
                db.add(Decision(meeting_id=meeting.id, text=text, kind=kind, evidence=evidence,
                                confidence=conf, grounded=bool(evidence)))
            for text, owner, due, prio, ev in m["actions"]:
                evidence = []
                for sid, quote in ev:
                    seg = next(s for s in m["segments"] if s[0] == sid)
                    evidence.append({"segment_id": sid, "start_ms": seg[2], "end_ms": seg[3],
                                     "quote": quote, "speaker": seg[1], "verified": True})
                db.add(ActionItem(meeting_id=meeting.id, text=text, owner_name=owner, due_date=due,
                                  priority=prio, evidence=evidence, confidence=0.87))

            run = Run(workspace_id=ws.id, kind="meeting", title=m["title"], status="done",
                      model="deepseek-v4-pro", tokens_in=4200 + len(m["segments"]) * 210,
                      tokens_out=1300 + len(m["decisions"]) * 120, cost_usd=0.0121,
                      latency_ms=38000 + len(m["segments"]) * 900, cache_hits=1,
                      meta={"metrics": {"grounded_rate": 0.93, "critic_score": 0.88}},
                      created_at=datetime.strptime(m["date"], "%Y-%m-%d") + timedelta(hours=10))
            db.add(run)
            db.flush()
            steps = [
                ("scribe", "转写清洗", f"{len(m['segments'])} 段转写 / 约 700 字", "识别说话人 3-4 位，剔除口头语 12 处", 2100, 320, 4200),
                ("segmenter", "议题切分", f"{len(m['segments'])} 段", f"切分 {len(m['topics'])} 个议题", 2400, 380, 3100),
                ("decider", "结论抽取", "全文转写", f"抽出 {len(m['decisions'])} 条，证据校验通过 {sum(1 for d in m['decisions'] if d[2])} 条", 3100, 620, 9800),
                ("planner", "待办抽取", "全文转写", f"抽出 {len(m['actions'])} 条待办，含责任人", 2900, 540, 8600),
                ("critic", "独立复核", f"复核 {len(m['decisions']) + len(m['actions'])} 条", "可信度 0.88，判掉 1 条证据不足条目", 2000, 260, 6400),
                ("composer", "纪要成文", "结构化条目", m["summary"][:60], 1800, 480, 5200),
            ]
            for i, (agent, label, inp, out, tin, tout, lat) in enumerate(steps):
                db.add(RunStep(run_id=run.id, idx=i, agent=agent, status="ok", input_summary=inp,
                               output_summary=out, tokens_in=tin, tokens_out=tout, latency_ms=lat,
                               cache_hit=(i == 0), evidence_count=2, payload={"label": label}))
            meeting.trace_id = run.id

        # 任务：先由会议待办生成，再补几条自建
        for m in MEETINGS:
            meeting = db.query(Meeting).filter(Meeting.workspace_id == ws.id, Meeting.title == m["title"]).first()
            for ai in db.query(ActionItem).filter(ActionItem.meeting_id == meeting.id).all():
                t = Task(workspace_id=ws.id, title=ai.text, description=f"来源：{meeting.title}",
                         status="todo", priority=ai.priority, owner_name=ai.owner_name,
                         due_date=ai.due_date, p50_days=0.0, p90_days=0.0,
                         source_meeting_id=meeting.id, ai_generated=True, tags=["会议生成"])
                db.add(t)
                db.flush()
                ai.task_id = t.id
                task_ids.append(t.id)

        for title, owner, status, prio, due, src_idx in EXTRA_TASKS:
            db.add(Task(workspace_id=ws.id, title=title, description="", status=status, priority=prio,
                        owner_name=owner, due_date=due, source_meeting_id=None, ai_generated=False,
                        tags=["手工创建"], position=src_idx))

        # 从 predict 里取工期，保证看板与预测模块口径一致
        from app.core import predict

        for t in db.query(Task).filter(Task.workspace_id == ws.id).all():
            est = predict.estimate(t.title, t.priority,
                                   owner_load=db.query(Task).filter(
                                       Task.workspace_id == ws.id, Task.owner_name == t.owner_name,
                                       Task.status.in_(["todo", "doing", "review"])).count(),
                                   days_to_due=None)
            t.p50_days, t.p90_days = est["p50_days"], est["p90_days"]
            t.risk_score = 0.8 if est["risk"] == "high" else 0.4 if est["risk"] == "watch" else 0.1

        # 文档：直接落模板内容
        from app.routers.docs import TEMPLATES

        for tpl in TEMPLATES:
            db.add(Doc(workspace_id=ws.id, title=tpl["name"], content=tpl["content"],
                       word_count=len(tpl["content"]), created_by=user.id))

        # 近两周运行历史：的趋势图与 Agent 统计需要有分布，否则只有今天一根尖刺
        step_text = {
            "scribe": ("转写清洗", "一段会议转写", "剔除口头语，纠正 3 处识别错误"),
            "segmenter": ("议题切分", "清洗后的全文", "切分 3 个议题"),
            "decider": ("结论抽取", "全文转写", "抽出 4 条结论，证据校验通过"),
            "planner": ("待办抽取", "全文转写", "抽出 3 条待办并配上责任人"),
            "critic": ("独立复核", "结构化条目", "复核通过，判掉 0 条"),
            "composer": ("纪要成文", "结构化条目", "生成约 600 字纪要"),
            "reranker": ("检索精排", "12 段候选片段", "精排保留 4 段"),
            "writer": ("文档改写", "一份周报草稿", "改写 9 处，风格评分 0.82"),
        }
        pool = list(step_text)
        today = datetime.now()
        for offset in range(14):
            day = today - timedelta(days=13 - offset)
            for k in range(1 + (offset * 5) % 3):
                picks = [pool[(offset * 3 + k + i) % len(pool)] for i in range(3 + (offset + k) % 3)]
                tin = 1800 + 140 * ((offset * 3 + k) % 9)
                tout = 500 + 60 * ((offset + k * 2) % 7)
                hist = Run(
                    workspace_id=ws.id,
                    kind="weekly" if (offset + k) % 4 == 3 else "meeting",
                    title=f"{day.month}月{day.day}日 项目例会" if (offset + k) % 4 != 3 else f"第{offset + 1}周 周报生成",
                    status="done", model="deepseek-flash", tokens_in=tin, tokens_out=tout,
                    cost_usd=round((tin * 0.27 + tout * 1.10) / 1_000_000, 5),
                    latency_ms=24000 + ((offset * 7 + k * 3) % 12) * 2100,
                    cache_hits=(offset + k) % 3,
                    meta={"metrics": {"grounded_rate": round(0.86 + ((offset + k) % 4) * 0.03, 3)}},
                    created_at=day.replace(hour=9 + k * 2, minute=(offset * 11) % 60, second=0, microsecond=0),
                )
                db.add(hist)
                db.flush()
                for i, agent in enumerate(picks):
                    label, inp, out = step_text[agent]
                    db.add(RunStep(run_id=hist.id, idx=i, agent=agent, status="ok",
                                   input_summary=inp, output_summary=out,
                                   tokens_in=300 + 40 * i, tokens_out=90 + 15 * i,
                                   latency_ms=2600 + 900 * i, cache_hit=(i == 0 and offset % 3 == 0),
                                   evidence_count=1 + i % 3, payload={"label": label}))

        db.commit()

        # 知识库：写文件 → 真实解析切片 → 向量化
        KB_DIR.mkdir(parents=True, exist_ok=True)
        for name, text in KB_FILES.items():
            path = KB_DIR / name
            path.write_text(text, encoding="utf-8")
            pages = rag.extract_pages(path, "md")
            chunks = rag.chunk_pages(pages)
            doc = KbDoc(workspace_id=ws.id, title=name.rsplit(".", 1)[0].replace("agentdesk-", "AgentDesk · "),
                        filename=name, ext="md", pages=1, chunk_count=len(chunks), status="ready")
            db.add(doc)
            db.flush()
            for i, c in enumerate(chunks):
                db.add(Chunk(kb_doc_id=doc.id, workspace_id=ws.id, idx=i, text=c["text"], page=c["page"],
                             section=c["section"], tokens=len(c["text"]), embedding=embed(c["text"])))
        db.commit()

        print(f"演示数据就绪：{ws.name}")
        print(f"  账号 {DEMO_EMAIL} / {DEMO_PASSWORD}")
        print(f"  会议 {db.query(Meeting).filter(Meeting.workspace_id == ws.id).count()} 场")
        print(f"  任务 {db.query(Task).filter(Task.workspace_id == ws.id).count()} 条")
        print(f"  知识库切片 {db.query(Chunk).filter(Chunk.workspace_id == ws.id).count()} 个")
    finally:
        db.close()


if __name__ == "__main__":
    seed(force="--force" in sys.argv)
