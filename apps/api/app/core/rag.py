"""检索增强问答。

链路：解析 → 按标题层级切片 → BM25 ⊕ 向量 → RRF 融合 → LLM 精排 → 生成 → 引用校验。

为什么是混合检索：中文办公文档里大量专有名词（"回调鉴权字段"）向量表达不出精确匹配，
BM25 命中率高但不懂同义改写；两者互补，RRF 只依赖排名不依赖分数尺度，融合时不用调权重。

引用校验放在生成之后：模型经常在句尾标 [2]，但 [2] 未必支持这句话。
这里把回答按句切开，凡是带 [n] 的句子，回查第 n 个片段与该句的重合度，
重合度低于阈值就标为 weak，前端用黄色标注 —— 宁可显示"依据不足"，也不假装有据。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

from . import prompts
from .embedding import cosine, embed, tokenize
from .providers import get_provider
from .routing import runtime
from .structured import call_json, call_text
from .trace import Recorder

_CITE = re.compile(r"\[(\d{1,2})\]")
_SENT_SPLIT = re.compile(r"(?<=[。！？；\n])")
_NUM = re.compile(r"\d+(?:\.\d+)?%?")


# ---------------------------------------------------------------- 解析
def extract_pages(path: Path, ext: str) -> list[tuple[int, str]]:
    ext = ext.lower().lstrip(".")
    if ext == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return [(i + 1, (page.extract_text() or "")) for i, page in enumerate(reader.pages)]
    if ext == "docx":
        import docx

        d = docx.Document(str(path))
        text = "\n".join(p.text for p in d.paragraphs if p.text.strip())
        return [(1, text)]
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if ext == "html":
        raw = re.sub(r"<[^>]+>", " ", raw)
    return [(1, raw)]


# ---------------------------------------------------------------- 切片
_HEAD = re.compile(r"^(#{1,4})\s+(.*)$", re.M)


def chunk_pages(pages: list[tuple[int, str]], target: int = 520, overlap: int = 80) -> list[dict]:
    """按 Markdown 标题切段，段内按长度再切，保留页码与所属标题。"""
    chunks: list[dict] = []
    for page_no, text in pages:
        text = (text or "").strip()
        if not text:
            continue
        heads = list(_HEAD.finditer(text))
        blocks: list[tuple[str, str]] = []
        if not heads:
            blocks.append(("", text))
        else:
            if heads[0].start() > 0:
                blocks.append(("", text[: heads[0].start()]))
            for i, m in enumerate(heads):
                end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
                blocks.append((m.group(2).strip(), text[m.end() : end].strip()))

        for section, block in blocks:
            block = block.strip()
            if not block:
                continue
            if len(block) <= target:
                chunks.append({"text": block, "page": page_no, "section": section})
                continue
            start = 0
            while start < len(block):
                piece = block[start : start + target]
                chunks.append({"text": piece.strip(), "page": page_no, "section": section})
                if start + target >= len(block):
                    break
                start += target - overlap
    return [c for c in chunks if len(c["text"]) > 20]


# ---------------------------------------------------------------- BM25
class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.avgdl = sum(len(d) for d in docs) / max(1, self.n)
        self.freqs = [Counter(d) for d in docs]
        df: Counter = Counter()
        for f in self.freqs:
            for term in f:
                df[term] += 1
        self.idf = {t: math.log(1 + (self.n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def scores(self, query_tokens: list[str]) -> list[float]:
        out = []
        for i, f in enumerate(self.freqs):
            dl = len(self.docs[i]) or 1
            s = 0.0
            for t in query_tokens:
                if t not in f:
                    continue
                idf = self.idf.get(t, 0.0)
                tf = f[t]
                s += idf * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            out.append(s)
        return out


def rrf(rank_lists: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion：只看名次，不吃分数尺度差异。"""
    agg: dict[int, float] = {}
    for ranks in rank_lists:
        for pos, idx in enumerate(ranks, start=1):
            agg[idx] = agg.get(idx, 0.0) + 1.0 / (k + pos)
    return sorted(agg.items(), key=lambda kv: kv[1], reverse=True)


# ---------------------------------------------------------------- 检索
def search(db, workspace_id: int, query: str, kb_ids: list[int] | None = None, top_k: int = 6) -> list[dict]:
    from ..models import Chunk, KbDoc

    q = db.query(Chunk).filter(Chunk.workspace_id == workspace_id)
    if kb_ids:
        q = q.filter(Chunk.kb_doc_id.in_(kb_ids))
    rows = q.all()
    if not rows:
        return []

    titles = {d.id: d.title for d in db.query(KbDoc).filter(KbDoc.workspace_id == workspace_id).all()}
    texts = [r.text for r in rows]
    doc_tokens = [tokenize(t) for t in texts]
    bm25 = BM25(doc_tokens)
    bm_scores = bm25.scores(tokenize(query))

    qvec = embed(query)
    vec_scores = [cosine(qvec, r.embedding or []) for r in rows]

    bm_rank = [i for i in sorted(range(len(rows)), key=lambda i: bm_scores[i], reverse=True) if bm_scores[i] > 0][:20]
    vec_rank = [i for i in sorted(range(len(rows)), key=lambda i: vec_scores[i], reverse=True) if vec_scores[i] > 0.05][:20]
    if not bm_rank and not vec_rank:
        return []

    fused = rrf([bm_rank, vec_rank])[: top_k * 2]
    candidates = []
    for idx, score in fused:
        row = rows[idx]
        candidates.append(
            {
                "chunk_id": row.id,
                "kb_doc_id": row.kb_doc_id,
                "doc_title": titles.get(row.kb_doc_id, ""),
                "page": row.page,
                "section": row.section,
                "text": row.text,
                "rrf": round(score, 5),
                "bm25": round(bm_scores[idx], 3),
                "vector": round(vec_scores[idx], 4),
            }
        )

    # LLM 精排：候选不多时直接给模型看，让它按"能否回答问题"重排
    if len(candidates) > 3:
        try:
            listing = "\n".join(f"{i + 1}. [{c['doc_title']} p{c['page']}] {c['text'][:180]}"
                                for i, c in enumerate(candidates))
            obj, _ = call_json("reranker", prompts.RERANKER,
                               f"问题：{query}\n\n候选片段：\n{listing}", temperature=0.0, max_tokens=400)
            order = [int(i) for i in obj.get("order", []) if str(i).isdigit() and 1 <= int(i) <= len(candidates)]
            if order:
                candidates = [candidates[i - 1] for i in order]
        except Exception:
            pass

    return candidates[:top_k]


def build_context(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks, start=1):
        parts.append(f"[{i}] 《{c['doc_title']}》 第{c['page']}页 · {c['section'] or '正文'}\n{c['text']}")
    return "\n\n".join(parts)


def verify_citations(answer: str, chunks: list[dict]) -> list[dict]:
    """把回答里带 [n] 的句子回查片段，给出 strong/weak 判定。

    不用序列相似度：回答是改写过的，字面重合天然偏低，会把正确引用判成弱。
    改成「答案句子的字符片段有多少能在来源片段里找到」，再加上数字必须对得上
    这一条硬约束——模型编数字是引用场景里最容易出的事故。
    """
    from .embedding import tokenize

    out = []
    for sentence in _SENT_SPLIT.split(answer or ""):
        ids = [int(m) for m in _CITE.findall(sentence)]
        if not ids:
            continue
        body = _CITE.sub("", sentence).strip()
        body = body.replace("**", "").replace("*", "")
        body_tokens = set(tokenize(body))
        body_nums = set(_NUM.findall(body))
        for n in ids:
            if n < 1 or n > len(chunks):
                out.append({"n": n, "status": "missing", "score": 0.0})
                continue
            text = chunks[n - 1]["text"]
            doc_tokens = set(tokenize(text))
            cover = len(body_tokens & doc_tokens) / max(1, len(body_tokens))
            # 对比度：把「和这一段的重合」跟「和其他段落的重合」比较，
            # 只看绝对重合会把短句全判成弱，看相对差距才能区分「真引这一条」和「凑数引用」。
            others = [
                len(body_tokens & set(tokenize(c["text"]))) / max(1, len(body_tokens))
                for i, c in enumerate(chunks, start=1) if i != n
            ]
            base = sum(others) / len(others) if others else 0.0
            contrast = cover / (cover + base) if (cover + base) > 0 else 0.0
            num_ok = (not body_nums) or body_nums.issubset(set(_NUM.findall(text)))
            strong = contrast >= 0.55 and num_ok
            out.append(
                {
                    "n": n,
                    "status": "strong" if strong else "weak",
                    "support": "strong" if strong else "weak",  # 前端用的字段名，跟 status 同义
                    "score": round(cover, 3),
                    "contrast": round(contrast, 3),
                    "doc_title": chunks[n - 1]["doc_title"],
                    "doc": chunks[n - 1]["doc_title"],
                    "page": chunks[n - 1]["page"],
                    "section": chunks[n - 1].get("section", ""),
                    "text": text[:120],
                    "chunk_id": chunks[n - 1]["chunk_id"],
                }
            )
    # 同一片段多次引用只保留最差判定，前端好渲染
    merged: dict[int, dict] = {}
    for c in out:
        cur = merged.get(c["n"])
        if cur is None or (cur["status"] == "strong" and c["status"] != "strong"):
            merged[c["n"]] = c
    return list(merged.values())


def answer_stream(db, workspace_id: int, question: str, kb_ids: list[int] | None, recorder: Recorder):
    """生成器：先 yield 检索结果，再逐字 yield 回答，最后 yield 校验结果。"""
    chunks = search(db, workspace_id, question, kb_ids)
    recorder.add("retriever", input_summary=question[:120],
                 output_summary=f"召回 {len(chunks)} 个片段：" + "、".join(f"p{c['page']}" for c in chunks),
                 payload={"rrf": [c["rrf"] for c in chunks]}, evidence_count=len(chunks))
    # chunks 只给数量，正文片段走 sources：早先前端把整段对象数组当数字拼进文案，
    # 屏幕上直接出现「召回 [object Object]」——契约里数字就只放数字。
    yield {
        "type": "retrieval",
        "count": len(chunks),
        "chunks": len(chunks),
        "sources": [
            {"doc": c["doc_title"], "page": c["page"], "section": c["section"]}
            for c in chunks[:6]
        ],
    }

    if not chunks:
        msg = "资料库里没有检索到相关内容。可以换个说法，或先上传对应文档。"
        for i in range(0, len(msg), 8):
            yield {"type": "token", "text": msg[i : i + 8]}
        recorder.add("writer", status="empty", output_summary="无召回，直接告知用户")
        yield {"type": "done", "citations": [], "answer": msg}
        return

    context = build_context(chunks)
    system = (
        "你是企业知识库问答助手。只根据给定资料回答，不要引入外部知识。\n"
        "要求：\n"
        "1. 中文回答，先给结论，再给依据，总长 150-300 字；\n"
        "2. 每个论断后面用 [编号] 标注来源，编号对应资料片段；\n"
        "3. 资料里没有的内容，直接说「资料中未提及」，不要猜；\n"
        "4. 不要复述资料原文超过两句，用自己的话组织。"
    )
    user = f"问题：{question}\n\n资料：\n{context}"
    model, temp = runtime.model_for("composer")
    provider = get_provider()

    buffer: list[str] = []
    stream = getattr(provider, "stream_chat", None)
    if stream is None:
        text, _ = call_text("composer", system, user)
        for i in range(0, len(text), 6):
            buffer.append(text[i : i + 6])
            yield {"type": "token", "text": text[i : i + 6]}
    else:
        for delta in stream([{"role": "system", "content": system}, {"role": "user", "content": user}],
                            model=model, temperature=temp, max_tokens=900):
            buffer.append(delta)
            yield {"type": "token", "text": delta}

    answer = "".join(buffer)
    citations = verify_citations(answer, chunks)
    strong = sum(1 for c in citations if c["status"] == "strong")
    recorder.add("writer", input_summary=f"{len(chunks)} 个片段 / 约 {len(context)} 字",
                 output_summary=answer[:200],
                 evidence_count=strong,
                 payload={"citations": citations})
    yield {"type": "done", "citations": citations, "answer": answer, "chunks": chunks}
