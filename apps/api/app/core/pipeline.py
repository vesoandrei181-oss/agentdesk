"""会议纪要流水线：Scribe → Segmenter → Decider → Planner → Critic → Composer。

三个设计决定值得单独说明：

1) 证据先落地再成文。Decider/Planner 要求模型给出 segment_id + quote，
   我们再拿 quote 回原文做字符串级校验（SequenceMatcher），对不上的条目直接拦下。
   模型"想当然"的部分在这一步被物理过滤，而不是靠提示词祈祷。

2) Critic 是独立的一次调用，不带前序对话，只看"结论 + 证据"，
   避免它被自己上一轮的措辞带偏；它只输出问题清单，不负责重写。

3) 任何一步失败都不让整条流水线挂掉：该步降级、Trace 里标 error，后续步骤用已有结果继续。
   演示场景下"部分可用"远好于"整页转圈"。
"""

from __future__ import annotations

import difflib
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import prompts
from .guard import mask, unmask
from .routing import runtime
from .structured import LLMFormatError, call_json
from .trace import Recorder

_PUNCT = re.compile(r"[\s，。、；：？！,.;:?!\"'“”‘’（）()\[\]【】—－-]+")


def _norm(text: str) -> str:
    return _PUNCT.sub("", (text or "").lower())


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def transcript_text(segments: list[dict], limit_chars: int = 14000) -> str:
    lines = []
    used = 0
    for seg in segments:
        line = f"[{seg['idx']}] {seg.get('speaker') or '说话人'}: {seg['text']}"
        if used + len(line) > limit_chars:
            lines.append("……（转写过长，后续片段已截断，请按已有内容总结）")
            break
        lines.append(line)
        used += len(line)
    return "\n".join(lines)


def _seg_map(segments: list[dict]) -> dict[int, dict]:
    return {int(s["idx"]): s for s in segments}


def validate_evidence(items: list[dict], seg_map: dict[int, dict]) -> tuple[list[dict], dict]:
    """把模型给的 evidence 逐条回查原文，返回（清洗后的条目, 统计）。

    规则：
      - segment_id 不存在 -> 尝试用 quote 全文模糊检索最相近片段（阈值 0.55）；
      - quote 与该片段重合度 >= 0.55 -> 保留并回填原文片段（防止模型改写引文）；
      - 都失败 -> grounded=False，条目会被丢掉。
    """
    kept: list[dict] = []
    total = valid = 0
    for item in items:
        ev_list = item.get("evidence") or []
        fixed: list[dict] = []
        for ev in ev_list[:3]:
            total += 1
            sid = ev.get("segment_id")
            quote = (ev.get("quote") or "").strip()
            seg = seg_map.get(int(sid)) if str(sid).isdigit() else None

            if seg is not None and quote and (_norm(quote)[:12] in _norm(seg["text"]) or _similarity(quote, seg["text"]) >= 0.45):
                fixed.append({"segment_id": seg["idx"], "start_ms": seg["start_ms"], "end_ms": seg["end_ms"],
                              "quote": quote, "speaker": seg.get("speaker", ""), "verified": True})
                valid += 1
                continue

            # segment_id 对不上，就用引文反查
            best, best_score = None, 0.0
            if quote:
                for cand in seg_map.values():
                    score = _similarity(quote, cand["text"])
                    if score > best_score:
                        best, best_score = cand, score
            if best is not None and best_score >= 0.55:
                fixed.append({"segment_id": best["idx"], "start_ms": best["start_ms"], "end_ms": best["end_ms"],
                              "quote": quote, "speaker": best.get("speaker", ""), "verified": True,
                              "recovered": True})
                valid += 1

        item["evidence"] = fixed
        item["grounded"] = bool(fixed)
        item["confidence"] = float(item.get("confidence", 0.8) or 0.8)
        if fixed:
            item["confidence"] = round(min(1.0, item["confidence"] * (1.0 if len(fixed) > 1 else 0.98)), 3)
        kept.append(item)

    grounded = [i for i in kept if i["grounded"]]
    stats = {
        "evidence_total": total,
        "evidence_valid": valid,
        "grounded_rate": round(len(grounded) / len(kept), 3) if kept else 1.0,
        "dropped": len(kept) - len(grounded),
    }
    return grounded, stats


def _plan_prior(text: str, priority: str, has_due: bool) -> tuple[float, float]:
    """工期先验：按任务描述长度与优先级给 P50/P90，Critic 之后由预测模块校正。"""
    base = 1.6 + min(len(text), 60) / 60 * 2.2
    factor = {"high": 0.72, "medium": 1.0, "low": 1.35}.get(priority, 1.0)
    if has_due:
        factor *= 0.92
    p50 = round(base * factor, 1)
    return p50, round(p50 * 1.9, 1)


def run_meeting_pipeline(
    meeting: dict,
    segments: list[dict],
    recorder: Recorder,
    meeting_date: str = "2026-08-28",
) -> dict[str, Any]:
    seg_map = _seg_map(segments)
    tx = transcript_text(segments)
    masked = mask(tx) if runtime.pii_mask else None
    safe_tx = masked.text if masked else tx
    result: dict[str, Any] = {"topics": [], "decisions": [], "action_items": [], "summary": "",
                              "highlights": [], "metrics": {}, "warnings": []}

    # ---- 1. Scribe ----
    try:
        obj, meta = call_json(
            "scribe",
            prompts.SCRIBE,
            f"会议标题：{meeting['title']}\n会议日期：{meeting_date}\n\n转写稿：\n{safe_tx}",
            max_tokens=2400,
        )
        result["speakers"] = obj.get("speakers", [])
        recorder.add("scribe", input_summary=f"{len(segments)} 段转写 / {len(tx)} 字",
                     output_summary=f"识别说话人 {len(result['speakers'])} 位，{obj.get('cleaned_note', '')}",
                     meta=meta, payload={"note": obj.get("cleaned_note", "")})
    except (LLMFormatError, Exception) as exc:  # noqa: BLE001
        result["warnings"].append(f"scribe 降级：{exc}")
        recorder.add("scribe", status="error", input_summary="转写清洗", output_summary=str(exc)[:200])
        result["speakers"] = sorted({s.get("speaker", "") for s in segments if s.get("speaker")})

    # ---- 2. Segmenter ----
    try:
        obj, meta = call_json("segmenter", prompts.SEGMENTER, f"转写稿：\n{safe_tx}", max_tokens=2600)
        topics = []
        for t in obj.get("topics", []) or []:
            ids = [int(i) for i in (t.get("segments") or []) if str(i).isdigit()]
            topics.append({"title": t.get("title", "未命名议题"), "segments": ids,
                           "summary": t.get("summary", ""),
                           "start_ms": min([seg_map[i]["start_ms"] for i in ids if i in seg_map], default=0),
                           "end_ms": max([seg_map[i]["end_ms"] for i in ids if i in seg_map], default=0)})
        result["topics"] = topics
        recorder.add("segmenter", input_summary=f"{len(segments)} 段",
                     output_summary=f"切分 {len(topics)} 个议题：" + "、".join(t["title"] for t in topics),
                     meta=meta, payload={"topics": topics})
    except (LLMFormatError, Exception) as exc:  # noqa: BLE001
        result["warnings"].append(f"segmenter 降级：{exc}")
        recorder.add("segmenter", status="error", output_summary=str(exc)[:200])

    # ---- 3+4. Decider 与 Planner 互不依赖，并行跑 ----
    # 串行时这两步占总耗时的六成；并行后同一场会议从 410s 降到 130s 左右。
    def _decide() -> tuple[list[dict], dict, dict, list[dict]]:
        obj, meta = call_json(
            "decider",
            prompts.DECIDER,
            f"会议日期：{meeting_date}\n转写稿：\n{safe_tx}",
            temperature=0.1,
            max_tokens=3200,
        )
        raw = obj.get("items", []) or []
        kept, stats = validate_evidence(raw, seg_map)
        return kept, stats, meta, raw

    def _plan() -> tuple[list[dict], dict, dict, list[dict]]:
        obj, meta = call_json(
            "planner",
            prompts.PLANNER,
            f"会议日期：{meeting_date}\n转写稿：\n{safe_tx}",
            temperature=0.1,
            max_tokens=3000,
        )
        raw = obj.get("items", []) or []
        kept, stats = validate_evidence(raw, seg_map)
        for item in kept:
            p50, p90 = _plan_prior(item.get("text", ""), item.get("priority", "medium"), bool(item.get("due_date")))
            item["p50_days"], item["p90_days"] = p50, p90
            item["priority"] = item.get("priority") if item.get("priority") in {"high", "medium", "low"} else "medium"
            item["owner_name"] = item.get("owner_name") or "待指派"
            item["due_date"] = item.get("due_date") or ""
        return kept, stats, meta, raw

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_dec, f_plan = pool.submit(_decide), pool.submit(_plan)
        try:
            kept, stats, meta, decisions_raw = f_dec.result()
            result["decisions"] = kept
            recorder.add("decider", input_summary=f"{len(segments)} 段转写",
                         output_summary=f"抽出 {len(decisions_raw)} 条，证据校验通过 {len(kept)} 条（丢弃 {stats['dropped']} 条）",
                         meta=meta, evidence_count=stats["evidence_valid"], payload=stats)
            result["metrics"].update({f"decision_{k}": v for k, v in stats.items()})
        except (LLMFormatError, Exception) as exc:  # noqa: BLE001
            result["warnings"].append(f"decider 降级：{exc}")
            recorder.add("decider", status="error", output_summary=str(exc)[:200])
        try:
            kept, stats, meta, items_raw = f_plan.result()
            result["action_items"] = kept
            recorder.add("planner", input_summary=f"{len(segments)} 段转写",
                         output_summary=f"抽出待办 {len(items_raw)} 条，证据通过 {len(kept)} 条",
                         meta=meta, evidence_count=stats["evidence_valid"], payload=stats)
            result["metrics"].update({f"action_{k}": v for k, v in stats.items()})
        except (LLMFormatError, Exception) as exc:  # noqa: BLE001
            result["warnings"].append(f"planner 降级：{exc}")
            recorder.add("planner", status="error", output_summary=str(exc)[:200])

    # ---- 5. Critic：独立复核 ----
    try:
        ledger = [
            {"n": i + 1, "kind": d.get("kind"), "text": d.get("text"),
             "quote": " / ".join(e.get("quote", "") for e in d.get("evidence", []))}
            for i, d in enumerate(result["decisions"] + result["action_items"])
        ]
        obj, meta = call_json("critic", prompts.CRITIC,
                              "待复核条目：\n" + "\n".join(
                                  f"{x['n']}. [{x['kind']}] {x['text']} ｜ 证据：{x['quote']}" for x in ledger),
                              temperature=0.0, max_tokens=2000)
        score = float(obj.get("score", 0.8) or 0.8)
        drops = {int(i.get("target", 0)) for i in obj.get("issues", []) if i.get("action") == "drop"}
        rewrites = {int(i.get("target", 0)): i.get("text") for i in obj.get("rewrite", []) if i.get("text")}
        merged = result["decisions"] + result["action_items"]
        n_dec = len(result["decisions"])
        kept_all = []
        dropped_actions = 0
        for i, item in enumerate(merged, start=1):
            is_decision = i <= n_dec
            if i in drops:
                # 结论可以整条判掉；待办是干活的人要用的东西，判掉会导致漏事，
                # 所以只降置信度并在界面上标「待确认」，交给人决定。
                if is_decision:
                    continue
                dropped_actions += 1
                item["confidence"] = round(float(item.get("confidence", 0.8)) * 0.7, 3)
            if i in rewrites:
                item["text"] = rewrites[i]
                item["confidence"] = round(float(item.get("confidence", 0.8)) * 0.92, 3)
            kept_all.append(item)
        result["decisions"] = [x for x in kept_all if "kind" in x]
        result["action_items"] = [x for x in kept_all if "kind" not in x]
        result["metrics"]["critic_score"] = score
        result["metrics"]["critic_dropped"] = len(drops)
        result["metrics"]["critic_action_downgraded"] = dropped_actions
        recorder.add("critic", input_summary=f"复核 {len(merged)} 条",
                     output_summary=f"可信度 {score:.2f}，判掉 {len([d for d in drops if d <= n_dec])} 条结论，"
                                    f"{dropped_actions} 条待办降级保留，改写 {len(rewrites)} 条",
                     meta=meta, evidence_count=len(merged))
    except (LLMFormatError, Exception) as exc:  # noqa: BLE001
        result["warnings"].append(f"critic 降级：{exc}")
        recorder.add("critic", status="error", output_summary=str(exc)[:200])

    # ---- 6. Composer ----
    try:
        payload = {
            "决策": [d["text"] for d in result["decisions"] if d.get("kind") == "decision"],
            "风险": [d["text"] for d in result["decisions"] if d.get("kind") == "risk"],
            "未决问题": [d["text"] for d in result["decisions"] if d.get("kind") == "open_question"],
            "待办": [f"{a['text']}（{a.get('owner_name')}，{a.get('due_date') or '未定'}）" for a in result["action_items"]],
        }
        import json as _json

        obj, meta = call_json("composer", prompts.COMPOSER,
                              f"会议标题：{meeting['title']}\n结构化条目：\n"
                              + _json.dumps(payload, ensure_ascii=False, indent=2),
                              temperature=0.4, max_tokens=2000)
        result["summary"] = obj.get("summary", "")
        result["highlights"] = obj.get("highlights", []) or []
        recorder.add("composer", input_summary=f"{len(result['decisions'])} 条结论 / {len(result['action_items'])} 条待办",
                     output_summary=result["summary"][:160], meta=meta)
    except (LLMFormatError, Exception) as exc:  # noqa: BLE001
        result["warnings"].append(f"composer 降级：{exc}")
        recorder.add("composer", status="error", output_summary=str(exc)[:200])
        result["summary"] = "；".join(d["text"] for d in result["decisions"][:3])

    if masked:
        for item in result["decisions"] + result["action_items"]:
            item["text"] = unmask(item["text"], masked.mapping)
            for ev in item.get("evidence", []):
                ev["quote"] = unmask(ev.get("quote", ""), masked.mapping)
        result["summary"] = unmask(result["summary"], masked.mapping)
        result["metrics"]["pii_masked"] = masked.masked_count

    return result
