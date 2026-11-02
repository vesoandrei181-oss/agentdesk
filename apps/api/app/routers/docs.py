"""写作台：模板 → 初稿 → AI 修订（块级 diff）→ 逐块采纳 → 落库。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, current_workspace
from ..models import Doc, User, Workspace
from ..core.routing import runtime
from ..core.trace import Recorder
from ..core.writer import apply_blocks, run_writer

router = APIRouter(prefix="/api/docs", tags=["docs"])

TEMPLATES = [
    {
        "id": "weekly",
        "name": "项目周报",
        "desc": "按「进展 / 问题 / 下周计划」三段式，适合向管理层同步",
        "content": """# 项目周报（第 34 周）

## 一、本周进展

1. 完成会议纪要多 Agent 流水线的联调，决议抽取准确率从 71% 提升到 88%。
2. 知识库检索接入混合召回，问答首字响应时间稳定在 1.1 秒以内。
3. 与设计确认了看板与 Trace 面板的交互稿，进入开发。

## 二、存在问题

1. 转写稿过长时（超过 1.4 万字），后段内容会被截断，需要补分段摘要策略。
2. 演示环境的后端实例内存偏小，长文档解析偶发超时。

## 三、下周计划

1. 补齐分段摘要，解决长会议的信息丢失。
2. 把文档解析挪到后台队列，前端改为轮询进度。
3. 准备评审用的演示数据与讲解脚本。
""",
    },
    {
        "id": "minutes",
        "name": "会议纪要",
        "desc": "结论优先，附责任人与时间点",
        "content": """# 产品评审会纪要

时间：2026 年 8 月 27 日 14:00-15:10　地点：三楼小会议室

## 参会人

孟嘉祺、杜春晓、王琳、赵鹏

## 结论

1. 本期只做「会议 → 任务」单向打通，暂不做任务回写会议。
2. 首页默认展示待办看板，数据概览下沉到第二屏。
3. 演示账号预置三场会议，覆盖决议、风险、未决三类条目。

## 待办

| 事项 | 负责人 | 截止 |
| --- | --- | --- |
| 首页改版走查 | 杜春晓 | 8 月 30 日 |
| 演示数据准备 | 孟嘉祺 | 8 月 31 日 |
| 部署脚本整理 | 孟嘉祺 | 9 月 2 日 |
""",
    },
    {
        "id": "proposal",
        "name": "项目方案",
        "desc": "背景、目标、路径、风险四段结构",
        "content": """# 智能会议纪要模块方案

## 一、背景

团队每周平均 6 场会议，纪要依赖人工整理，平均延迟 1.5 天，会后执行项丢失率约三成。

## 二、目标

把「开会」到「有责任人、有截止时间的任务」之间的时间压缩到 3 分钟以内，
并且每条结论都能点回原话，便于事后核对。

## 三、实现路径

1. 转写文本按议题切分，保留时间戳与说话人。
2. 用独立的抽取与复核 Agent 分别产出结论、待办，交叉校验证据。
3. 结论落库后一键转任务，进入看板，进入周报。

## 四、风险

1. 模型对口语化表达的理解偏差，需靠证据回查兜底。
2. 长会议超出上下文，需要分段处理。
""",
    },
    {
        "id": "notice",
        "name": "通知公告",
        "desc": "公文语气，标题 + 正文 + 落款",
        "content": """# 关于启用智能会议纪要系统的通知

各部门：

为提高会议效率、减少会后整理成本，自 2026 年 9 月 1 日起，公司内部会议纪要通过智能会议纪要系统统一生成。

一、会议结束后，由会议发起人上传转写文本，系统自动生成结论与待办。
二、生成结果需由发起人在一个工作日内确认，确认后自动同步至任务看板。
三、涉及敏感信息的会议，请在系统中开启脱敏开关后再行处理。

特此通知。

综合管理部
2026 年 8 月 28 日
""",
    },
]


class DocIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = ""
    style_profile: dict = {}


class DocPatch(BaseModel):
    title: str | None = None
    content: str | None = None
    style_profile: dict | None = None


class WriteIn(BaseModel):
    instruction: str = Field(min_length=2, max_length=400)


class ApplyIn(BaseModel):
    blocks: list[dict]
    accepted: list[int] = []
    instruction: str = ""


def _brief(d: Doc) -> dict:
    return {"id": d.id, "title": d.title, "word_count": d.word_count, "version": d.version,
            "updated_at": d.updated_at.isoformat() if d.updated_at else "", "preview": (d.content or "")[:120]}


@router.get("/templates")
def templates():
    return {"items": TEMPLATES}


@router.get("")
def list_docs(ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db), q: str = ""):
    query = db.query(Doc).filter(Doc.workspace_id == ws.id)
    if q:
        query = query.filter(Doc.title.like(f"%{q}%"))
    return {"items": [_brief(d) for d in query.order_by(Doc.updated_at.desc()).all()]}


@router.post("", status_code=201)
def create_doc(body: DocIn, user: User = Depends(current_user), ws: Workspace = Depends(current_workspace),
               db: Session = Depends(get_db)):
    d = Doc(workspace_id=ws.id, title=body.title, content=body.content,
            style_profile=body.style_profile or {}, word_count=len(body.content), created_by=user.id)
    db.add(d)
    db.commit()
    db.refresh(d)
    return {**_brief(d), "content": d.content}


@router.get("/{did}")
def get_doc(did: int, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    d = db.get(Doc, did)
    if d is None or d.workspace_id != ws.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    return {**_brief(d), "content": d.content, "style_profile": d.style_profile or {}}


@router.put("/{did}")
def update_doc(did: int, body: DocPatch, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    d = db.get(Doc, did)
    if d is None or d.workspace_id != ws.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    if body.content is not None:
        d.content = body.content
        d.word_count = len(body.content)
    if body.title is not None:
        d.title = body.title
    if body.style_profile is not None:
        d.style_profile = body.style_profile
    db.commit()
    db.refresh(d)
    return {**_brief(d), "content": d.content}


@router.post("/{did}/write")
def write(did: int, body: WriteIn, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    d = db.get(Doc, did)
    if d is None or d.workspace_id != ws.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    rec = Recorder(db, ws.id, "write", f"{d.title} · {body.instruction[:40]}", model=runtime.model_for("writer")[0])
    out = run_writer(d.content or "", body.instruction, d.title, rec)
    rec.finish("done", stats=out["stats"], notes=out["notes"][:5])
    return {**out, "trace_id": rec.id, "current_content": d.content}


@router.post("/{did}/apply")
def apply(did: int, body: ApplyIn, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    d = db.get(Doc, did)
    if d is None or d.workspace_id != ws.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    merged = apply_blocks(d.content or "", body.blocks, body.accepted)
    d.content = merged
    d.word_count = len(merged)
    d.version += 1
    db.commit()
    return {"ok": True, "version": d.version, "word_count": d.word_count, "content": merged}


@router.delete("/{did}", status_code=204)
def delete_doc(did: int, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    d = db.get(Doc, did)
    if d is None or d.workspace_id != ws.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    db.delete(d)
    db.commit()
    return None
