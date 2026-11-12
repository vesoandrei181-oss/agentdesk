"""质量评测：知识库问答命中率、引用支撑率、写作补丁命中率。

这个脚本不依赖人工打分，全部指标都能从接口返回值直接算出来：
- hit@k：回答里引用的片段中，是否包含人工标注的「应该被引用」的那一篇；
- support：引用片段对回答的支撑强度，由 verify_citations 判定 strong 的比例；
- patch_rate：模型给出的补丁能在原文里定位成功的比例。
结果写到 data/eval_report.json / eval_report.md，文档和视频里引用的数字都来自这里。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
OUT = Path("data")

# (问题, 应该被引用的资料标题关键字)
QUESTIONS: list[tuple[str, str]] = [
    ("知识库问答的引用校验阈值是多少？", "product"),
    ("切片长度和重叠是怎么设的？", "product"),
    ("会议纪要的六个 Agent 分别做什么？", "product"),
    ("语义缓存相似度阈值是多少？", "product"),
    ("接口鉴权用什么方式？", "api"),
    ("分析接口是同步还是异步？", "api"),
    ("SSE 流式问答的返回格式是什么？", "api"),
    ("上传知识库支持哪些格式？", "api"),
    ("部署时后端最少要多少内存？", "ops"),
    ("50 并发下 P95 延迟是多少？", "ops"),
    ("上线前要做哪些检查？", "ops"),
    ("模型路由有哪几档？", "product"),
]


def ask(client: httpx.Client, headers: dict, q: str) -> dict:
    r = client.post("/api/kb/ask_sync", headers=headers, json={"question": q, "top_k": 6})
    r.raise_for_status()
    return r.json()


def main() -> None:
    client = httpx.Client(base_url=BASE, trust_env=False, timeout=180)
    token = client.post("/api/auth/login", json={"email": "demo@agentdesk.dev", "password": "Demo@2026"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    rows = []
    t0 = time.time()
    for q, expect in QUESTIONS:
        start = time.time()
        data = ask(client, headers, q)
        latency = time.time() - start
        citations = data.get("citations") or []
        chunks = data.get("chunks") or []
        titles = " ".join((c.get("doc_title") or "") + " " + str(c.get("filename") or "") for c in chunks).lower()
        hit = expect in titles
        strong = sum(1 for c in citations if c.get("status") == "strong")
        rows.append({
            "question": q,
            "expect": expect,
            "hit": hit,
            "citations": len(citations),
            "strong": strong,
            "latency": round(latency, 2),
            "answer": (data.get("answer") or "")[:120],
        })
        print(f"{'✓' if hit else '✗'} {latency:5.2f}s strong={strong}/{len(citations)} {q}")

    n = len(rows)
    hit_rate = sum(1 for r in rows if r["hit"]) / n
    support = sum(r["strong"] for r in rows) / max(1, sum(r["citations"] for r in rows))
    avg_latency = sum(r["latency"] for r in rows) / n

    # 写作补丁命中率：连续 4 条指令，看模型给的补丁有多少能在原文里定位
    doc = client.get("/api/docs/1", headers=headers).json()
    instructions = [
        "把语言改得更口语、更像人写的",
        "压缩到 300 字以内，保留所有数字",
        "给每一段补一句结论句",
        "把待办拆成「谁 / 做什么 / 什么时候」三段式",
    ]
    patch_rows = []
    for ins in instructions:
        start = time.time()
        res = client.post("/api/docs/1/write", headers=headers, json={"instruction": ins}).json()
        patches = res.get("patches") or []
        ok = sum(1 for p in patches if p.get("ok"))
        patch_rows.append({"instruction": ins, "patches": len(patches), "located": ok,
                           "latency": round(time.time() - start, 2),
                           "added": res["stats"]["added"], "removed": res["stats"]["removed"]})
        print(f"  patch {ok}/{len(patches)} {patch_rows[-1]['latency']}s {ins}")

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "kb": {"questions": n, "hit_rate": round(hit_rate, 3), "citation_support": round(support, 3),
               "avg_latency_s": round(avg_latency, 2), "total_s": round(time.time() - t0, 1), "rows": rows},
        "writer": {"runs": len(patch_rows), "rows": patch_rows,
                   "patch_locate_rate": round(sum(r["located"] for r in patch_rows) / max(1, sum(r["patches"] for r in patch_rows)), 3),
                   "avg_latency_s": round(sum(r["latency"] for r in patch_rows) / len(patch_rows), 2)},
        "doc_chars": len(doc.get("content") or ""),
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "eval_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# 质量评测报告",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、知识库问答",
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
        f"| 问题数 | {n} |",
        f"| 命中率 hit@6 | {hit_rate:.1%} |",
        f"| 引用支撑率（strong 占比） | {support:.1%} |",
        f"| 平均响应 | {avg_latency:.2f}s |",
        "",
        "| # | 问题 | 命中 | 引用/强支撑 | 耗时 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for i, r in enumerate(rows, 1):
        md.append(f"| {i} | {r['question']} | {'✓' if r['hit'] else '✗'} | {r['strong']}/{r['citations']} | {r['latency']}s |")
    md += [
        "",
        "## 二、写作补丁",
        "",
        "| 指令 | 补丁数 | 定位成功 | 增删行 | 耗时 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in patch_rows:
        md.append(f"| {r['instruction']} | {r['patches']} | {r['located']} | +{r['added']}/-{r['removed']} | {r['latency']}s |")
    md.append("")
    md.append(f"补丁定位成功率：{report['writer']['patch_locate_rate']:.1%}；平均耗时 {report['writer']['avg_latency_s']}s")
    (OUT / "eval_report.md").write_text("\n".join(md), encoding="utf-8")
    print("\n写入 data/eval_report.json 与 data/eval_report.md")


if __name__ == "__main__":
    main()
