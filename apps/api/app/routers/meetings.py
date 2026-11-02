"""会议：上传转写 → 六步分析 → 证据链纪要 → 导出。

分析放在后台线程里跑（一次完整链路要调用 6 次模型，20-90 秒），
前端拿 status 轮询即可看到"处理中/已就绪"，不用挂一个长连接等到超时。
"""

from __future__ import annotations

import io
import re
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_db
from ..deps import current_user, current_workspace
from ..models import ActionItem, Decision, Meeting, Segment, User, Workspace
from ..core.pipeline import run_meeting_pipeline
from ..core.routing import runtime
from ..core.trace import Recorder

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


class MeetingIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    meeting_date: str = ""
    attendees: list[str] = []
    source_type: str = "upload"


class SegmentIn(BaseModel):
    idx: int
    speaker: str = ""
    start_ms: int = 0
    end_ms: int = 0
    text: str


class SegmentsIn(BaseModel):
    segments: list[SegmentIn]
    duration_ms: int = 0


def _seg_dict(s: Segment) -> dict:
    return {"idx": s.idx, "speaker": s.speaker, "start_ms": s.start_ms, "end_ms": s.end_ms,
            "text": s.text, "confidence": s.confidence}


def meeting_brief(m: Meeting, db: Session) -> dict:
    n_dec = db.query(Decision).filter(Decision.meeting_id == m.id).count()
    n_act = db.query(ActionItem).filter(ActionItem.meeting_id == m.id).count()
    n_seg = db.query(Segment).filter(Segment.meeting_id == m.id).count()
    return {
        "id": m.id, "title": m.title, "status": m.status, "source_type": m.source_type,
        "meeting_date": m.meeting_date or (m.created_at.strftime("%Y-%m-%d") if m.created_at else ""),
        "created_at": m.created_at.isoformat() if m.created_at else "",
        "duration_ms": m.duration_ms, "attendees": m.attendees or [],
        "summary": m.summary, "counts": {"decisions": n_dec, "actions": n_act, "segments": n_seg},
        "trace_id": m.trace_id,
    }


def meeting_detail(m: Meeting, db: Session) -> dict:
    segs = db.query(Segment).filter(Segment.meeting_id == m.id).order_by(Segment.idx).all()
    decs = db.query(Decision).filter(Decision.meeting_id == m.id).order_by(Decision.id).all()
    acts = db.query(ActionItem).filter(ActionItem.meeting_id == m.id).order_by(ActionItem.id).all()
    data = meeting_brief(m, db)
    data.update(
        {
            "segments": [_seg_dict(s) for s in segs],
            "decisions": [
                {"id": d.id, "text": d.text, "kind": d.kind, "evidence": d.evidence or [],
                 "confidence": d.confidence, "grounded": d.grounded, "status": d.status}
                for d in decs
            ],
            "action_items": [
                {"id": a.id, "text": a.text, "owner_name": a.owner_name, "due_date": a.due_date,
                 "priority": a.priority, "evidence": a.evidence or [], "confidence": a.confidence,
                 "task_id": a.task_id}
                for a in acts
            ],
            "topics": m.topics or [],
        }
    )
    return data


@router.get("")
def list_meetings(ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db),
                  q: str = "", limit: int = 50):
    query = db.query(Meeting).filter(Meeting.workspace_id == ws.id)
    if q:
        query = query.filter(Meeting.title.like(f"%{q}%"))
    rows = query.order_by(Meeting.id.desc()).limit(min(limit, 100)).all()
    return {"items": [meeting_brief(m, db) for m in rows], "total": query.count()}


@router.post("", status_code=201)
def create_meeting(body: MeetingIn, user: User = Depends(current_user),
                   ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    m = Meeting(workspace_id=ws.id, title=body.title, attendees=body.attendees,
                source_type=body.source_type, meeting_date=body.meeting_date,
                created_by=user.id, status="draft")
    db.add(m)
    db.commit()
    db.refresh(m)
    return meeting_brief(m, db)


@router.get("/{mid}")
def get_meeting(mid: int, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    m = db.get(Meeting, mid)
    if m is None or m.workspace_id != ws.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会议不存在")
    return meeting_detail(m, db)


@router.post("/{mid}/segments")
def save_segments(mid: int, body: SegmentsIn, ws: Workspace = Depends(current_workspace),
                  db: Session = Depends(get_db)):
    m = db.get(Meeting, mid)
    if m is None or m.workspace_id != ws.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会议不存在")
    db.query(Segment).filter(Segment.meeting_id == mid).delete()
    for s in body.segments:
        db.add(Segment(meeting_id=mid, idx=s.idx, speaker=s.speaker, start_ms=s.start_ms,
                       end_ms=s.end_ms, text=s.text))
    m.duration_ms = body.duration_ms or max([s.end_ms for s in body.segments] or [0])
    db.commit()
    return {"ok": True, "saved": len(body.segments)}


@router.post("/{mid}/analyze")
def analyze(mid: int, background: BackgroundTasks, sync: bool = False,
            ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    m = db.get(Meeting, mid)
    if m is None or m.workspace_id != ws.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会议不存在")
    if db.query(Segment).filter(Segment.meeting_id == mid).count() == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该会议还没有转写内容")
    if m.status == "processing":
        return {"status": "processing", "meeting_id": mid}

    m.status = "processing"
    db.commit()
    if sync:
        _run_analysis(mid, ws.id)
        db.refresh(m)
        return meeting_detail(m, db)
    background.add_task(_run_analysis, mid, ws.id)
    return {"status": "processing", "meeting_id": mid, "model": runtime.model_for("decider")[0]}


def _run_analysis(mid: int, ws_id: int) -> None:
    db = SessionLocal()
    try:
        m = db.get(Meeting, mid)
        if m is None:
            return
        segs = [_seg_dict(s) for s in db.query(Segment).filter(Segment.meeting_id == mid).order_by(Segment.idx).all()]
        rec = Recorder(db, ws_id, "meeting", m.title, model=runtime.model_for("decider")[0])
        result = run_meeting_pipeline(
            {"id": m.id, "title": m.title}, segs, rec,
            meeting_date=m.meeting_date or (m.created_at.strftime("%Y-%m-%d") if m.created_at else datetime.now().strftime("%Y-%m-%d")),
        )

        db.query(Decision).filter(Decision.meeting_id == mid).delete()
        db.query(ActionItem).filter(ActionItem.meeting_id == mid).delete()
        for d in result["decisions"]:
            db.add(Decision(meeting_id=mid, text=d["text"], kind=d.get("kind", "decision"),
                            evidence=d.get("evidence", []), confidence=d.get("confidence", 0.0),
                            grounded=d.get("grounded", True)))
        for a in result["action_items"]:
            db.add(ActionItem(meeting_id=mid, text=a["text"], owner_name=a.get("owner_name", ""),
                              due_date=a.get("due_date", ""), priority=a.get("priority", "medium"),
                              evidence=a.get("evidence", []), confidence=a.get("confidence", 0.0)))
        m.summary = result["summary"]
        m.topics = result["topics"]
        m.status = "ready"
        m.trace_id = rec.id
        db.commit()
        rec.finish("done", metrics=result["metrics"], warnings=result["warnings"][:5])
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        m = db.get(Meeting, mid)
        if m:
            m.status = "failed"
            db.commit()
        print(f"[analyze] meeting={mid} failed: {exc}")
    finally:
        db.close()


# ------------------------------------------------------------------ 导出
@router.get("/{mid}/export")
def export(mid: int, fmt: str = "md", ws: Workspace = Depends(current_workspace),
           db: Session = Depends(get_db)):
    m = db.get(Meeting, mid)
    if m is None or m.workspace_id != ws.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会议不存在")
    data = meeting_detail(m, db)
    md = render_markdown(data)
    safe = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", m.title)[:40]

    if fmt == "docx":
        from docx import Document
        from docx.shared import Pt

        doc = Document()
        style = doc.styles["Normal"]
        style.font.name = "宋体"
        style.font.size = Pt(10.5)
        doc.add_heading(m.title, level=1)
        doc.add_paragraph(f"会议时间：{data.get('meeting_date') or ''}　参会人：{'、'.join(data.get('attendees') or []) or '—'}")
        doc.add_heading("一、会议摘要", level=2)
        doc.add_paragraph(data.get("summary") or "（暂无）")
        doc.add_heading("二、决议与风险", level=2)
        for i, d in enumerate(data["decisions"], 1):
            label = {"decision": "决议", "risk": "风险", "open_question": "未决"}.get(d["kind"], "条目")
            p = doc.add_paragraph(f"{i}. [{label}] {d['text']}")
            for ev in d.get("evidence", [])[:2]:
                r = p.add_run(f"　依据：{ev.get('speaker', '')}「{ev.get('quote', '')[:60]}」")
                r.italic = True
                r.font.size = Pt(9)
        doc.add_heading("三、行动项", level=2)
        table = doc.add_table(rows=1, cols=4)
        table.style = "Light Grid Accent 1"
        for i, h in enumerate(["任务", "负责人", "截止", "优先级"]):
            table.rows[0].cells[i].text = h
        for a in data["action_items"]:
            cells = table.add_row().cells
            cells[0].text = a["text"]
            cells[1].text = a["owner_name"] or "待指派"
            cells[2].text = a["due_date"] or "—"
            cells[3].text = {"high": "高", "medium": "中", "low": "低"}.get(a["priority"], "中")
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{safe}.docx"'},
        )

    return StreamingResponse(
        io.BytesIO(md.encode("utf-8")),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe}.md"'},
    )


def render_markdown(data: dict) -> str:
    lines = [f"# {data['title']}", ""]
    lines.append(f"- 会议时间：{data.get('meeting_date') or '—'}")
    lines.append(f"- 参会人：{'、'.join(data.get('attendees') or []) or '—'}")
    lines.append(f"- 转写片段：{data['counts']['segments']} 条　生成方式：AgentDesk 多 Agent 流水线")
    lines += ["", "## 会议摘要", "", data.get("summary") or "（暂无）", ""]
    lines += ["## 议题", ""]
    for t in data.get("topics", []):
        lines.append(f"- **{t.get('title', '')}**：{t.get('summary', '')}")
    lines += ["", "## 决议与风险", ""]
    for i, d in enumerate(data["decisions"], 1):
        label = {"decision": "决议", "risk": "风险", "open_question": "未决"}.get(d["kind"], "条目")
        lines.append(f"{i}. **[{label}]** {d['text']}　`置信度 {d['confidence']:.2f}`")
        for ev in d.get("evidence", [])[:2]:
            lines.append(f"   > {ev.get('speaker', '')}：{ev.get('quote', '')}")
    lines += ["", "## 行动项", "", "| # | 任务 | 负责人 | 截止 | 优先级 |", "|---|---|---|---|---|"]
    for i, a in enumerate(data["action_items"], 1):
        lines.append(f"| {i} | {a['text']} | {a['owner_name'] or '待指派'} | {a['due_date'] or '—'} | "
                     f"{ {'high': '高', 'medium': '中', 'low': '低'}.get(a['priority'], '中') } |")
    lines += ["", "---", "由 AgentDesk 生成，每条结论均可回溯到上方转写片段。"]
    return "\n".join(lines)


@router.get("/{mid}/trace")
def meeting_trace(mid: int, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    m = db.get(Meeting, mid)
    if m is None or m.workspace_id != ws.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会议不存在")
    from ..models import Run, RunStep

    run = db.get(Run, m.trace_id) if m.trace_id else None
    if run is None:
        return {"run": None, "steps": []}
    steps = db.query(RunStep).filter(RunStep.run_id == run.id).order_by(RunStep.idx).all()
    return {
        "run": {"id": run.id, "status": run.status, "tokens_in": run.tokens_in, "tokens_out": run.tokens_out,
                "cost_usd": run.cost_usd, "latency_ms": run.latency_ms, "cache_hits": run.cache_hits,
                "model": run.model, "meta": run.meta or {}},
        "steps": [{"idx": s.idx, "agent": s.agent, "status": s.status, "input": s.input_summary,
                   "output": s.output_summary, "tokens_in": s.tokens_in, "tokens_out": s.tokens_out,
                   "latency_ms": s.latency_ms, "cache_hit": s.cache_hit,
                   "evidence_count": s.evidence_count, "payload": s.payload or {}} for s in steps],
    }
