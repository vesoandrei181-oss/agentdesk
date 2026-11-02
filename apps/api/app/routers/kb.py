"""知识库：上传解析 → 切片入库 → 混合检索问答（SSE 流式 + 引用校验）。"""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal, get_db
from ..deps import current_workspace
from ..models import ChatMessage, Chunk, KbDoc, Workspace
from ..core import rag
from ..core.embedding import embed
from ..core.routing import runtime
from ..core.trace import Recorder

router = APIRouter(prefix="/api/kb", tags=["kb"])
ALLOWED = {"pdf", "docx", "md", "markdown", "txt", "html"}


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    kb_ids: list[int] = []


def _doc_brief(d: KbDoc) -> dict:
    return {"id": d.id, "title": d.title, "filename": d.filename, "ext": d.ext, "pages": d.pages,
            "chunk_count": d.chunk_count, "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else ""}


@router.get("")
def list_docs(ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    rows = db.query(KbDoc).filter(KbDoc.workspace_id == ws.id).order_by(KbDoc.id.desc()).all()
    chunks = db.query(Chunk).filter(Chunk.workspace_id == ws.id).count()
    return {"items": [_doc_brief(d) for d in rows], "total_chunks": chunks}


@router.post("/upload", status_code=201)
async def upload(file: UploadFile = File(...), title: str = Form(""),
                 ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"暂不支持 .{ext} 格式，请上传 PDF/DOCX/MD/TXT")

    settings.upload_path.mkdir(parents=True, exist_ok=True)
    stamp = int(time.time())
    dest = settings.upload_path / f"kb_{ws.id}_{stamp}.{ext}"
    dest.write_bytes(await file.read())

    try:
        pages = rag.extract_pages(dest, ext)
        chunks = rag.chunk_pages(pages)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"解析失败：{exc}") from exc
    if not chunks:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "没有解析出有效文本，可能是扫描件或空文件")

    doc = KbDoc(workspace_id=ws.id, title=title or Path(file.filename or "未命名").stem,
                filename=file.filename or dest.name, ext=ext, pages=len({c["page"] for c in chunks}),
                chunk_count=len(chunks), status="ready")
    db.add(doc)
    db.flush()
    for i, c in enumerate(chunks):
        db.add(Chunk(kb_doc_id=doc.id, workspace_id=ws.id, idx=i, text=c["text"], page=c["page"],
                     section=c["section"], tokens=len(c["text"]), embedding=embed(c["text"])))
    db.commit()
    db.refresh(doc)
    return {**_doc_brief(doc), "saved_as": dest.name}


@router.get("/{did}/chunks")
def chunks(did: int, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    doc = db.get(KbDoc, did)
    if doc is None or doc.workspace_id != ws.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    rows = db.query(Chunk).filter(Chunk.kb_doc_id == did).order_by(Chunk.idx).all()
    return {"items": [{"idx": c.idx, "page": c.page, "section": c.section, "text": c.text[:400]} for c in rows]}


@router.delete("/{did}", status_code=204)
def remove(did: int, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    doc = db.get(KbDoc, did)
    if doc is None or doc.workspace_id != ws.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    db.query(Chunk).filter(Chunk.kb_doc_id == did).delete()
    db.delete(doc)
    db.commit()
    return None


@router.get("/chat/history")
def history(ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db), limit: int = 40):
    rows = (db.query(ChatMessage).filter(ChatMessage.workspace_id == ws.id)
            .order_by(ChatMessage.id.desc()).limit(min(limit, 100)).all())
    return {"items": [{"id": m.id, "role": m.role, "content": m.content, "citations": m.citations or [],
                       "created_at": m.created_at.isoformat()} for m in reversed(rows)]}


@router.post("/ask")
def ask(body: AskIn, ws: Workspace = Depends(current_workspace)):
    """SSE：retrieval → token 流 → done(citations)。前端用 fetch + ReadableStream 解析。"""

    def gen():
        db: Session = SessionLocal()
        try:
            db.add(ChatMessage(workspace_id=ws.id, role="user", content=body.question))
            db.commit()
            rec = Recorder(db, ws.id, "rag", body.question[:80], model=runtime.model_for("composer")[0])
            answer = ""
            citations: list[dict] = []
            for event in rag.answer_stream(db, ws.id, body.question, body.kb_ids or None, rec):
                if event["type"] == "done":
                    answer = event.get("answer", "")
                    citations = event.get("citations", [])
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            rec.finish("done", citation_strong=sum(1 for c in citations if c["status"] == "strong"),
                       citation_weak=sum(1 for c in citations if c["status"] != "strong"))
            db.add(ChatMessage(workspace_id=ws.id, role="assistant", content=answer, citations=citations,
                               kb_doc_ids=body.kb_ids))
            db.commit()
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)[:300]}, ensure_ascii=False)}\n\n"
        finally:
            db.close()

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/ask_sync")
def ask_sync(body: AskIn, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    """无流式版本，给自动化测试和 curl 用。"""
    rec = Recorder(db, ws.id, "rag", body.question[:80], model=runtime.model_for("composer")[0])
    answer, citations, chunks = "", [], []
    for event in rag.answer_stream(db, ws.id, body.question, body.kb_ids or None, rec):
        if event["type"] == "retrieval":
            chunks = event["chunks"]
        elif event["type"] == "done":
            answer, citations = event.get("answer", ""), event.get("citations", [])
    rec.finish("done")
    return {"answer": answer, "citations": citations, "chunks": chunks}
