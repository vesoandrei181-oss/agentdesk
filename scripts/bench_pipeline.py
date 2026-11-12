"""端到端链路计时：建会议 → 写转写 → 同步分析 → 读 trace。

用法：python scripts/bench_pipeline.py
输出：每个 Agent 的耗时与 token，用于文档里的性能表格。
"""
from __future__ import annotations

import json
import time

import httpx

BASE = "http://127.0.0.1:8000"

TRANSCRIPT = [
    ("孟嘉祺", "今天主要过一下知识库问答的上线标准，先把结论定下来。"),
    ("杜春晓", "前端这边流式输出已经通了，首字延迟压到 1.1 秒左右，但引用面板还在做。"),
    ("赵鹏", "后端检索现在是 BM25 加向量，两路结果用 RRF 融合，精排再走一次小模型。"),
    ("孟嘉祺", "那召回率怎么样，有没有做评测集？"),
    ("赵鹏", "建了 60 条问题，目前命中率 82%，主要是长文档跨页的问题答不准。"),
    ("杜春晓", "跨页这个是不是切片的问题，之前一段只有 300 字，太碎了。"),
    ("赵鹏", "对，我打算把切片调到 520 字，重叠 80 字，再看一遍命中率。"),
    ("孟嘉祺", "行，那这周先把切片调完，命中率目标定 88%，达不到就先不上线。"),
    ("杜春晓", "引用面板我周五前给到可点跳转，右上角显示支撑强度。"),
    ("孟嘉祺", "还有合规，问答里如果出现身份证、手机号，一律打码，别直接进模型。"),
    ("赵鹏", "脱敏网关已经有了，返回的时候再还原，日志里只留掩码后的内容。"),
    ("孟嘉祺", "好，那决议就是三条：切片调整、命中率 88%、引用面板周五交付。散会。"),
]


def main() -> None:
    client = httpx.Client(base_url=BASE, trust_env=False, timeout=300)
    token = client.post("/api/auth/login", json={"email": "demo@agentdesk.dev", "password": "Demo@2026"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    meeting = client.post(
        "/api/meetings",
        headers=headers,
        json={
            "title": "知识库上线标准评审",
            "meeting_date": "2026-09-02",
            "attendees": ["孟嘉祺", "杜春晓", "赵鹏"],
            "source_type": "transcript",
        },
    ).json()
    mid = meeting["id"]

    segs = []
    t = 0
    for i, (speaker, text) in enumerate(TRANSCRIPT):
        segs.append({"idx": i, "speaker": speaker, "start_ms": t, "end_ms": t + 12000, "text": text})
        t += 12000
    client.post(f"/api/meetings/{mid}/segments", headers=headers, json={"segments": segs})

    t0 = time.time()
    client.post(f"/api/meetings/{mid}/analyze?sync=1", headers=headers)
    elapsed = time.time() - t0

    detail = client.get(f"/api/meetings/{mid}", headers=headers).json()
    trace = client.get(f"/api/meetings/{mid}/trace", headers=headers).json()

    print(f"meeting_id={mid} elapsed={elapsed:.1f}s status={detail['status']}")
    print(f"decisions={len(detail['decisions'])} actions={len(detail['action_items'])} topics={len(detail.get('topics') or [])}")
    run = trace["run"]
    print(f"run tokens={run['tokens_in']}/{run['tokens_out']} cost=${run['cost_usd']} latency={run['latency_ms']}ms model={run['model']}")
    for s in trace["steps"]:
        print(f"  {s['idx']}. {s['agent']:<10} {s['status']:<5} {s['latency_ms']:>6}ms tok={s['tokens_in']}/{s['tokens_out']} ev={s['evidence_count']}")
    grounded = sum(1 for d in detail["decisions"] if d["grounded"])
    print(f"grounded={grounded}/{len(detail['decisions'])}")
    print("summary:", (detail.get("summary") or "")[:120])

    with open("data/bench_pipeline.json", "w", encoding="utf-8") as fh:
        json.dump({"elapsed": elapsed, "meeting_id": mid, "trace": trace, "detail_status": detail["status"]}, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
