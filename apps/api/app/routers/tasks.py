"""任务看板：AI 抽取的待办落成卡片，带 P50/P90 工期与风险标记。"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import current_workspace
from ..models import ActionItem, Meeting, Task, Workspace
from ..core import prompts, predict
from ..core.routing import runtime
from ..core.structured import call_json
from ..core.trace import Recorder

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
COLUMNS = [("todo", "待开始"), ("doing", "进行中"), ("review", "待验收"), ("done", "已完成")]


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str = ""
    status: str = "todo"
    priority: str = "medium"
    owner_name: str = ""
    due_date: str = ""
    tags: list[str] = []


class TaskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    owner_name: str | None = None
    due_date: str | None = None
    position: int | None = None
    tags: list[str] | None = None


class EstimateIn(BaseModel):
    text: str = Field(min_length=2)
    priority: str = "medium"
    owner_name: str = ""
    due_date: str = ""


def _days_to(due: str) -> float | None:
    if not due:
        return None
    try:
        d = datetime.strptime(due, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (d - date.today()).days


def _load_owner(db: Session, ws_id: int, owner: str) -> int:
    return (db.query(Task).filter(Task.workspace_id == ws_id, Task.owner_name == owner,
                                  Task.status.in_(["todo", "doing", "review"])).count() if owner else 0)


def _enrich(db: Session, ws: Workspace, t: Task) -> dict:
    est = predict.estimate(t.title + " " + (t.description or ""), t.priority,
                           owner_load=_load_owner(db, ws.id, t.owner_name),
                           days_to_due=_days_to(t.due_date))
    return {
        "id": t.id, "title": t.title, "description": t.description, "status": t.status,
        "priority": t.priority, "owner_name": t.owner_name, "due_date": t.due_date,
        "p50_days": t.p50_days or est["p50_days"], "p90_days": t.p90_days or est["p90_days"],
        "risk": est["risk"], "slack_days": est["slack_days"], "factors": est["factors"],
        "source_meeting_id": t.source_meeting_id, "ai_generated": t.ai_generated,
        "tags": t.tags or [], "position": t.position,
    }


@router.get("")
def board(view: str = "board", q: str = "", owner: str = "",
          ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    query = db.query(Task).filter(Task.workspace_id == ws.id)
    if q:
        query = query.filter(Task.title.like(f"%{q}%"))
    if owner:
        query = query.filter(Task.owner_name == owner)
    rows = query.order_by(Task.position, Task.id).all()
    items = [_enrich(db, ws, t) for t in rows]
    if view == "list":
        return {"items": items}
    cols = [{"key": k, "name": n, "items": [i for i in items if i["status"] == k]} for k, n in COLUMNS]
    owners = sorted({t.owner_name for t in rows if t.owner_name})
    return {"columns": cols, "owners": owners, "total": len(items)}


@router.post("", status_code=201)
def create(body: TaskIn, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    est = predict.estimate(body.title + " " + body.description, body.priority,
                           owner_load=_load_owner(db, ws.id, body.owner_name),
                           days_to_due=_days_to(body.due_date))
    t = Task(workspace_id=ws.id, title=body.title, description=body.description, status=body.status,
             priority=body.priority, owner_name=body.owner_name, due_date=body.due_date,
             p50_days=est["p50_days"], p90_days=est["p90_days"],
             risk_score=0.8 if est["risk"] == "high" else 0.4 if est["risk"] == "watch" else 0.1,
             tags=body.tags)
    db.add(t)
    db.commit()
    db.refresh(t)
    return _enrich(db, ws, t)


@router.patch("/{tid}")
def update(tid: int, body: TaskPatch, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    t = db.get(Task, tid)
    if t is None or t.workspace_id != ws.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(t, field, value)
    if body.priority or body.owner_name is not None or body.due_date is not None:
        est = predict.estimate(t.title + " " + (t.description or ""), t.priority,
                               owner_load=_load_owner(db, ws.id, t.owner_name),
                               days_to_due=_days_to(t.due_date))
        t.p50_days, t.p90_days = est["p50_days"], est["p90_days"]
        t.risk_score = 0.8 if est["risk"] == "high" else 0.4 if est["risk"] == "watch" else 0.1
    db.commit()
    db.refresh(t)
    return _enrich(db, ws, t)


@router.delete("/{tid}", status_code=204)
def remove(tid: int, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    t = db.get(Task, tid)
    if t is None or t.workspace_id != ws.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    db.delete(t)
    db.commit()
    return None


@router.post("/estimate")
def estimate(body: EstimateIn, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    est = predict.estimate(body.text, body.priority, owner_load=_load_owner(db, ws.id, body.owner_name),
                           days_to_due=_days_to(body.due_date))
    return est


@router.post("/from-meeting/{mid}")
def from_meeting(mid: int, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    m = db.get(Meeting, mid)
    if m is None or m.workspace_id != ws.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会议不存在")
    acts = db.query(ActionItem).filter(ActionItem.meeting_id == mid).all()
    created = []
    for a in acts:
        if a.task_id:
            continue
        est = predict.estimate(a.text, a.priority, owner_load=_load_owner(db, ws.id, a.owner_name),
                               days_to_due=_days_to(a.due_date))
        t = Task(workspace_id=ws.id, title=a.text[:200], description=f"来源：{m.title}", status="todo",
                 priority=a.priority, owner_name=a.owner_name, due_date=a.due_date,
                 p50_days=est["p50_days"], p90_days=est["p90_days"],
                 risk_score=0.8 if est["risk"] == "high" else 0.4 if est["risk"] == "watch" else 0.1,
                 source_meeting_id=mid, ai_generated=True, tags=["会议生成"])
        db.add(t)
        db.flush()
        a.task_id = t.id
        created.append(t.id)
    db.commit()
    return {"created": len(created), "task_ids": created}


@router.get("/weekly")
def weekly(generate: int = 0, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    tasks = db.query(Task).filter(Task.workspace_id == ws.id).all()
    meetings = db.query(Meeting).filter(Meeting.workspace_id == ws.id, Meeting.status == "ready").all()
    digest = predict.weekly_digest(
        [{"title": t.title, "status": t.status, "owner_name": t.owner_name, "p50_hours": (t.p50_days or 0) * 8,
          "risk": "high" if t.risk_score >= 0.7 else "normal", "meeting_id": t.source_meeting_id} for t in tasks],
        [{"id": m.id, "title": m.title, "meeting_date": m.meeting_date} for m in meetings],
    )

    # 周报正文单独落盘缓存：页面首屏拿数据面板，正文点「生成」再调模型，避免每次进入都等 40 秒
    cache_file = Path(settings.upload_path).parent / "cache" / f"weekly_{ws.id}.json"
    report: dict | None = None
    if not generate and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if cached.get("digest_key") == _digest_key(digest):
                report = cached.get("report")
        except Exception:  # noqa: BLE001 - 缓存坏了就当没有
            report = None

    trace_id = None
    if report is None and generate:
        rec = Recorder(db, ws.id, "weekly", "本周周报", model=runtime.model_for("composer")[0])
        try:
            report, meta = call_json("weekly", prompts.WEEKLY,
                                     "数据：\n" + json.dumps(digest, ensure_ascii=False, indent=2),
                                     temperature=0.4, max_tokens=1600)
            rec.add("weekly", input_summary=f"{len(tasks)} 条任务 / {len(meetings)} 场会议",
                    output_summary=str(report.get("headline", ""))[:120], meta=meta)
        except Exception as exc:  # noqa: BLE001
            rec.add("weekly", status="error", output_summary=str(exc)[:200])
            report = {"headline": "本周周报（规则版）", "sections": [], "fallback": True}
        rec.finish("done")
        trace_id = rec.id
        if not report.get("fallback"):
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps({"digest_key": _digest_key(digest), "report": report},
                                             ensure_ascii=False, indent=1), encoding="utf-8")

    return {"digest": digest, "report": report, "text": _report_text(report, digest),
            "trace_id": trace_id}


def _digest_key(digest: dict) -> str:
    """用关键计数做缓存键：任务数或完成数变了就重新生成。"""
    t = digest.get("totals", {})
    return f"{t.get('tasks', 0)}-{t.get('done', 0)}-{t.get('doing', 0)}-{t.get('todo', 0)}"


def _report_text(report: dict | None, digest: dict) -> str:
    tot = digest.get("totals", {})
    if not report or not report.get("sections"):
        return (f"本周共跟踪 {tot.get('tasks', 0)} 项任务，完成 {tot.get('done', 0)} 项，"
                f"进行中 {tot.get('doing', 0)} 项，待办 {tot.get('todo', 0)} 项。")
    lines = [f"# {report.get('headline', '本周周报')}", ""]
    for sec in report["sections"]:
        lines.append(f"## {sec.get('title', '')}")
        lines.append(str(sec.get("content", "")).strip())
        lines.append("")
    return "\n".join(lines).strip()
