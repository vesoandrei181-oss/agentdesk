"""Diff 级 AI 写作。

和"让模型整篇重写"的做法不同，这里只让模型产出修订稿，然后用序列比对算出最小编辑块，
前端逐块显示"改了什么、为什么改"，用户可以单块接受或拒绝。

之所以值得这么做：办公文档里 80% 的句子是对的，模型整篇重排会把好的改坏、把语气改得陌生。
块级 diff 让改动可审计、可回滚，也让"AI 帮了多少忙"变成可量化的数字。

规划里的三件事在这里落地：句式改写、语气统一、术语一致；另外加一层规则化润色检查
（中英混排空格、重复标点、长句、语气词密度），这些不靠模型也能查出，成本为零。
"""

from __future__ import annotations

import difflib
import re

from . import prompts
from .guard import mask, unmask
from .routing import runtime
from .structured import LLMFormatError, call_json
from .trace import Recorder

_CN = re.compile(r"[\u4e00-\u9fff]")
_LONG_SENT = re.compile(r"[^。！？\n]{45,}[。！？]")


def style_report(text: str) -> dict:
    """规则化文本体检，不花 token。"""
    sentences = [s for s in re.split(r"[。！？\n]", text) if s.strip()]
    lens = [len(s) for s in sentences] or [0]
    zh_chars = len(_CN.findall(text))
    fillers = text.count("非常") + text.count("十分") + text.count("极其") + text.count("针对")
    issues = []
    if fillers > 3:
        issues.append(f"程度副词偏多（{fillers} 处），建议替换为具体描述")
    if len(_LONG_SENT.findall(text)) > 2:
        issues.append(f"存在 {len(_LONG_SENT.findall(text))} 个 45 字以上长句")
    if re.search(r"[。，][。，]", text):
        issues.append("存在重复标点")
    if re.search(r"[\u4e00-\u9fff][A-Za-z]", text) or re.search(r"[A-Za-z][\u4e00-\u9fff]", text):
        issues.append("中英文之间缺少空格")
    mixed = re.findall(r"\b[A-Za-z]{3,}\b", text)
    if len(mixed) and len(mixed) / max(1, zh_chars / 100) > 6:
        issues.append("英文缩写密度偏高，首次出现建议补中文释名")
    if "被" in text:
        issues.append("出现被动句，公文语气下可改主动")
    return {
        "chars": len(text),
        "zh_chars": zh_chars,
        "sentences": len(sentences),
        "avg_sentence": round(sum(lens) / len(lens), 1),
        "max_sentence": max(lens),
        "fillers": fillers,
        "issues": issues,
    }


def _blocks(original: str, revised: str, context: int = 1) -> list[dict]:
    """SequenceMatcher 逐行比对 → 可渲染的编辑块。"""
    # 用 split("\n") 而不是 splitlines()：后者会吞掉末尾换行，
    # 导致「不勾选任何块」重建出来的文本比原文少一个换行，保存时反复丢格式。
    a = original.split("\n")
    b = revised.split("\n")
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    out: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            # 长段未改动的行折叠成一块，中间用省略号占位（省略的行仍保留，应用补丁时要用回）
            segment = a[i1:i2]
            if len(segment) > context * 2 + 2:
                out.append({"type": "equal", "lines": segment[:context]})
                out.append({"type": "skip", "count": len(segment) - context * 2,
                            "lines": segment[context:len(segment) - context]})
                out.append({"type": "equal", "lines": segment[-context:]})
            elif segment:
                out.append({"type": "equal", "lines": segment})
            continue
        out.append(
            {
                "type": "replace" if tag == "replace" else tag,
                "old": a[i1:i2],
                "new": b[j1:j2],
                "lines": b[j1:j2],
                "a_range": [i1 + 1, i2],
                "b_range": [j1 + 1, j2],
            }
        )
    return out


def _apply_patches(original: str, patches: list[dict]) -> tuple[str, list[dict]]:
    """把模型给的补丁逐条落到原文上。

    模型只负责「改哪一句、改成什么、为什么改」，它不改动整篇文本；
    这样即使某条补丁的 target 在原文里找不到，也只丢这一条，不会污染其余内容。
    """
    text = original
    applied: list[dict] = []
    for p in patches or []:
        target = (p.get("target") or "").strip()
        op = (p.get("op") or "replace").strip()
        new_text = p.get("new_text") or ""
        if not target:
            continue
        idx = text.find(target)
        if idx < 0:
            applied.append({**p, "ok": False, "note": "原文中未找到该片段，已跳过"})
            continue
        if op == "delete":
            text = text[:idx] + text[idx + len(target):]
        elif op == "insert_after":
            text = text[:idx + len(target)] + new_text + text[idx + len(target):]
        else:
            text = text[:idx] + new_text + text[idx + len(target):]
        applied.append({**p, "ok": True})
    return text, applied


def run_writer(original: str, instruction: str, doc_title: str, recorder: Recorder) -> dict:
    masked = mask(original) if runtime.pii_mask else None
    safe = masked.text if masked else original
    before = style_report(original)

    revised = original
    notes: list[str] = []
    patches: list[dict] = []
    applied: list[dict] = []
    style_note = ""
    try:
        obj, meta = call_json(
            "writer",
            prompts.WRITER,
            f"文档标题：{doc_title}\n修改要求：{instruction}\n\n原文：\n{safe}",
            temperature=0.35,
            max_tokens=3000,
        )
        patches = obj.get("patches", []) or []
        style_note = obj.get("style_note", "") or ""
        revised, applied = _apply_patches(safe, patches)
        notes = [f"{p.get('reason', '')}（{p.get('op', 'replace')}）" for p in applied if p.get("ok")]
        missed = [p for p in applied if not p.get("ok")]
        if missed:
            notes.append(f"{len(missed)} 条建议定位失败已跳过")
        recorder.add("writer", input_summary=f"{len(original)} 字 / 要求：{instruction[:60]}",
                     output_summary=f"{len(notes)} 条修改建议，命中 {len(applied) - len(missed)}/{len(applied)}",
                     meta=meta, evidence_count=len(applied),
                     payload={"patches": [{k: v for k, v in p.items() if k != "ok"} for p in applied[:6]]})
    except (LLMFormatError, Exception) as exc:  # noqa: BLE001
        recorder.add("writer", status="error", output_summary=str(exc)[:200])
        notes = [f"模型调用失败，返回原文：{exc}"]

    if masked:
        revised = unmask(revised, masked.mapping)
        notes = [unmask(n, masked.mapping) for n in notes]

    blocks = _blocks(original, revised)
    added = sum(len(x.get("new", [])) for x in blocks if x["type"] in {"insert", "replace"})
    removed = sum(len(x.get("old", [])) for x in blocks if x["type"] in {"delete", "replace"})
    after = style_report(revised)

    # 第二意见：让 verifier 复核「有没有改到事实」，输出结构是 supported/score/unsupported
    risks: list[str] = []
    if added + removed:
        try:
            changed = "\n".join(f"- {x['type']}: {' / '.join(x.get('old', []))[:80]} → {' / '.join(x.get('new', []))[:80]}"
                                for x in blocks if x["type"] != "equal")
            obj, meta = call_json("verifier", prompts.VERIFIER,
                                  f"原始要求：{instruction}\n以下是改写前后的差异，请判断是否改动了事实或数字：\n{changed[:2500]}",
                                  temperature=0.0, max_tokens=600)
            if obj.get("supported") is False:
                risks.append(f"复核认为有改动缺少依据（可信度 {obj.get('score', 0)}）：{obj.get('reason', '')}")
            risks.extend(str(x) for x in (obj.get("unsupported") or [])[:3])
            recorder.add("verifier", input_summary=f"{added + removed} 行改动",
                         output_summary=f"风险提示 {len(risks)} 条", meta=meta, evidence_count=len(risks))
        except (LLMFormatError, Exception) as exc:  # noqa: BLE001
            recorder.add("verifier", status="error", output_summary=str(exc)[:160])

    total_lines = max(1, len(original.splitlines()))
    return {
        "revised": revised,
        "blocks": blocks,
        "notes": notes,
        "patches": applied[:8],
        "style_note": style_note,
        "risks": risks,
        "style_before": before,
        "style_after": after,
        "stats": {
            "lines_changed": added + removed,
            "added": added,
            "removed": removed,
            "edit_ratio": round((added + removed) / (2 * total_lines), 3),
            "avg_sentence_delta": round(after["avg_sentence"] - before["avg_sentence"], 1),
            "issue_delta": len(before["issues"]) - len(after["issues"]),
        },
    }


def apply_blocks(original: str, blocks: list[dict], accepted: list[int]) -> str:
    """按用户勾选的块序号重建文本；未勾选的块保留原样。"""
    lines: list[str] = []
    for i, blk in enumerate(blocks):
        if blk["type"] == "equal":
            lines.extend(blk["lines"])
        elif blk["type"] == "skip":
            lines.extend(blk.get("lines", []))
        elif i in accepted:
            if blk["type"] == "delete":
                continue
            lines.extend(blk.get("new", []))
        else:
            lines.extend(blk.get("old", []))
    return "\n".join(lines)
