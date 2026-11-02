"""运行记录（Agent Trace）与运营指标。

Trace 是本项目最核心的"可解释性"载体：评审点开任意一次执行，
能看到每个 Agent 的输入摘要、输出摘要、耗时、token、是否命中缓存、证据条数。
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_workspace
from ..models import Decision, Meeting, Run, RunStep, Task, Workspace
from ..core.cache import cache
from ..core.routing import runtime

router = APIRouter(prefix="/api", tags=["insights"])

AGENT_LABEL = {
    "scribe": "转写清洗", "segmenter": "议题切分", "decider": "结论抽取", "planner": "待办抽取",
    "critic": "独立复核", "composer": "纪要成文", "writer": "文本修订", "verifier": "改动复核",
    "retriever": "混合召回", "reranker": "精排", "weekly": "周报生成",
}


def _run_brief(r: Run) -> dict:
    return {"id": r.id, "kind": r.kind, "title": r.title, "status": r.status, "model": r.model,
            "tokens_in": r.tokens_in, "tokens_out": r.tokens_out, "cost_usd": r.cost_usd,
            "latency_ms": r.latency_ms, "cache_hits": r.cache_hits,
            "created_at": r.created_at.isoformat() if r.created_at else ""}


@router.get("/runs")
def list_runs(ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db),
              kind: str = "", limit: int = 40):
    q = db.query(Run).filter(Run.workspace_id == ws.id)
    if kind:
        q = q.filter(Run.kind == kind)
    rows = q.order_by(Run.id.desc()).limit(min(limit, 200)).all()
    return {"items": [_run_brief(r) for r in rows]}


@router.get("/runs/{rid}")
def get_run(rid: int, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    r = db.get(Run, rid)
    if r is None or r.workspace_id != ws.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "记录不存在")
    steps = db.query(RunStep).filter(RunStep.run_id == rid).order_by(RunStep.idx).all()
    return {
        "run": {**_run_brief(r), "meta": r.meta or {}},
        "steps": [{"idx": s.idx, "agent": s.agent, "label": AGENT_LABEL.get(s.agent, s.agent),
                   "status": s.status, "input": s.input_summary, "output": s.output_summary,
                   "tokens_in": s.tokens_in, "tokens_out": s.tokens_out, "latency_ms": s.latency_ms,
                   "cache_hit": s.cache_hit, "evidence_count": s.evidence_count,
                   "payload": s.payload or {}} for s in steps],
    }


@router.get("/insights/overview")
def overview(ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    meetings = db.query(Meeting).filter(Meeting.workspace_id == ws.id).all()
    ready = [m for m in meetings if m.status == "ready"]
    tasks = db.query(Task).filter(Task.workspace_id == ws.id).all()
    decisions = (db.query(Decision).join(Meeting, Meeting.id == Decision.meeting_id)
                 .filter(Meeting.workspace_id == ws.id).all())
    runs = db.query(Run).filter(Run.workspace_id == ws.id).all()

    grounded = [d for d in decisions if d.grounded]
    done = [t for t in tasks if t.status == "done"]
    risky = [t for t in tasks if t.risk_score >= 0.7]
    tokens = sum(r.tokens_in + r.tokens_out for r in runs)
    cost = round(sum(r.cost_usd for r in runs), 4)
    # 人工整理一场会议约 45 分钟；AI 链路按实测平均耗时计，差额即节省时间
    ai_minutes = round(sum(r.latency_ms for r in runs if r.kind == "meeting") / 60000, 1)
    saved_minutes = max(0, len(ready) * 45 - int(ai_minutes))

    per_day: Counter = Counter()
    for r in runs:
        if r.created_at:
            per_day[r.created_at.strftime("%Y-%m-%d")] += 1
    today = datetime.now()
    timeline = []
    for i in range(13, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        timeline.append({"date": d, "runs": per_day.get(d, 0)})

    agent_steps = db.query(RunStep).join(Run, Run.id == RunStep.run_id).filter(Run.workspace_id == ws.id).all()
    agent_stats = {}
    for s in agent_steps:
        st = agent_stats.setdefault(s.agent, {"agent": s.agent, "label": AGENT_LABEL.get(s.agent, s.agent),
                                              "calls": 0, "tokens": 0, "latency": 0, "errors": 0, "cache": 0})
        st["calls"] += 1
        st["tokens"] += s.tokens_in + s.tokens_out
        st["latency"] += s.latency_ms
        st["errors"] += 1 if s.status != "ok" else 0
        st["cache"] += 1 if s.cache_hit else 0
    for st in agent_stats.values():
        st["avg_latency"] = int(st["latency"] / max(1, st["calls"]))

    return {
        "kpi": {
            "meetings": len(meetings),
            "meetings_ready": len(ready),
            "decisions": len(decisions),
            "grounded_rate": round(len(grounded) / len(decisions), 3) if decisions else 1.0,
            "avg_decisions": round(len(decisions) / len(ready), 1) if ready else 0,
            "tasks": len(tasks),
            "tasks_done": len(done),
            "completion_rate": round(len(done) / len(tasks), 3) if tasks else 0,
            "at_risk": len(risky),
            "saved_minutes": saved_minutes,
            "tokens": tokens,
            "cost_usd": cost,
            "runs": len(runs),
            "cache_hits": sum(r.cache_hits for r in runs),
        },
        "timeline": timeline,
        "agents": sorted(agent_stats.values(), key=lambda s: -s["calls"]),
        "runtime": runtime.snapshot(),
        "cache": cache.stats(),
    }


@router.get("/insights/cost")
def cost_breakdown(ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    rows = (db.query(Run.kind, func.count(Run.id), func.sum(Run.tokens_in + Run.tokens_out), func.sum(Run.cost_usd),
                     func.avg(Run.latency_ms))
            .filter(Run.workspace_id == ws.id).group_by(Run.kind).all())
    return {"items": [{"kind": k, "runs": c, "tokens": int(tok or 0), "cost_usd": round(float(cost or 0), 5),
                       "avg_latency_ms": int(avg or 0)} for k, c, tok, cost, avg in rows]}
