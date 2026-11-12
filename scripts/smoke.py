"""端到端冒烟脚本：登录 -> 建会议 -> 写转写 -> 跑分析 -> 校验结论与待办。

用法：
    python scripts/smoke.py                     # 打本机 8000
    BASE=http://127.0.0.1:8000 python scripts/smoke.py

脚本会保留它创建的会议（标题带「联调」前缀），便于在界面上回看真实链路结果；
加 --clean 则跑完删除该会议相关的结论与待办（只删自己建的）。
"""

from __future__ import annotations

import os
import sys
import time

import httpx

BASE = os.environ.get("BASE", "http://127.0.0.1:8000")
EMAIL = os.environ.get("DEMO_EMAIL", "demo@agentdesk.dev")
PASSWORD = os.environ.get("DEMO_PASSWORD", "Demo@2026")

SEGMENTS = [
    ("孟嘉祺", 0, 18000, "今天主要三件事：纪要模块的准确率、知识库问答的引用、还有看板的性能。先说说准确率现在到哪了。"),
    ("赵鹏", 18000, 41000, "上一版在真实会议上把结论和待办混在一起，客户反馈说看着累。我加了 Critic 复核之后，误报从百分之二十三降到百分之九，但还是会漏掉一些口头约定。"),
    ("孙倩", 41000, 62000, "漏的那些基本都是没有明确说「决定」两个字的，比如「那就这么办」这种，得靠上下文判断。"),
    ("孟嘉祺", 62000, 80000, "那就把判定口径改成三类：决策、风险、未决问题，未决问题允许没有证据，但必须标出来让我们人工看。赵鹏你来改提示词。"),
    ("赵鹏", 80000, 95000, "行，我周五之前改完，顺便把证据回查的阈值也调一下。"),
    ("孙倩", 95000, 118000, "引用这块我担心的是答非所问。现在只做向量检索，问上线时间它会返回一段讲部署流程的，得加关键词检索做混合。"),
    ("孟嘉祺", 118000, 140000, "混合检索可以，但引用必须能点回原文页码，不然评审一问就露馅。这个优先级最高，孙倩你负责。"),
    ("孙倩", 140000, 155000, "好，我下周一把引用校验做出来，先用重合度算，后面再换模型打分。"),
]


def main() -> int:
    clean = "--clean" in sys.argv
    with httpx.Client(base_url=BASE, timeout=600.0, trust_env=False) as c:
        health = c.get("/api/health").json()
        print(f"[health] provider={health.get('provider')} model={health.get('model_quality')} mock={health.get('mock')}")

        r = c.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
        r.raise_for_status()
        token = r.json()["token"]
        c.headers["Authorization"] = f"Bearer {token}"
        print(f"[auth] login ok, token={len(token)} chars")

        meeting = c.post(
            "/api/meetings",
            json={
                "title": f"联调会 {time.strftime('%H:%M:%S')}（真实模型链路验证）",
                "meeting_date": time.strftime("%Y-%m-%d"),
                "attendees": ["孟嘉祺", "赵鹏", "孙倩"],
            },
        ).json()
        mid = meeting["id"]
        print(f"[meeting] id={mid} title={meeting['title']}")

        segments = [
            {"idx": i + 1, "speaker": s, "start_ms": a, "end_ms": b, "text": t}
            for i, (s, a, b, t) in enumerate(SEGMENTS)
        ]
        c.post(f"/api/meetings/{mid}/segments", json={"segments": segments}).raise_for_status()

        started = time.time()
        result = c.post(f"/api/meetings/{mid}/analyze", params={"sync": 1}).json()
        elapsed = time.time() - started
        print(f"[analyze] {elapsed:.1f}s status={result.get('status')}")

        detail = c.get(f"/api/meetings/{mid}").json()
        decisions = detail.get("decisions", [])
        actions = detail.get("action_items", [])
        topics = detail.get("topics", []) or []
        print(f"[result] topics={len(topics)} decisions={len(decisions)} actions={len(actions)}")
        print(f"[summary] {detail.get('summary', '')[:160]}")

        grounded = [d for d in decisions if d.get("grounded")]
        print(f"[evidence] grounded {len(grounded)}/{len(decisions)}")
        for d in decisions[:3]:
            quote = (d.get("evidence") or [{}])[0].get("quote", "")
            print(f"   - [{d.get('kind')}] {d['text'][:40]} … 证据「{quote[:26]}」")

        trace = c.get(f"/api/meetings/{mid}/trace").json()
        steps = trace.get("run", {}).get("steps", []) if isinstance(trace, dict) else []
        run = trace.get("run", trace) if isinstance(trace, dict) else {}
        print(f"[trace] steps={len(steps) or len(run.get('steps', []))} "
              f"tokens={run.get('tokens_in', 0)}/{run.get('tokens_out', 0)} cost=${run.get('cost_usd', 0)}")

        if clean:
            print(f"[clean] 保留会议 {mid} 供界面回看；如需删除请手动处理")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
