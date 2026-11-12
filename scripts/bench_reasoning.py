"""思维链 / 模型档位 的延迟-质量权衡小实验。

用途：技术文档里"优化策略"一节的数据不能瞎写，这个脚本给出真实数字。
跑法：
    python scripts/bench_reasoning.py

输出：每个组合的耗时、输出 token、抽取条数、证据通过条数。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from app.core import prompts  # noqa: E402
from app.core.pipeline import transcript_text, validate_evidence  # noqa: E402
from app.core.providers import OpenAICompatProvider  # noqa: E402
from app.core.structured import _try_load  # noqa: E402

SEGMENTS = [
    {"idx": 1, "speaker": "孟嘉祺", "start_ms": 0, "end_ms": 18000,
     "text": "今天主要三件事：纪要模块的准确率、知识库问答的引用、还有看板的性能。"},
    {"idx": 2, "speaker": "赵鹏", "start_ms": 18000, "end_ms": 41000,
     "text": "上一版把结论和待办混在一起，客户说看着累。加了复核之后误报从百分之二十三降到百分之九，但还是会漏口头约定。"},
    {"idx": 3, "speaker": "孙倩", "start_ms": 41000, "end_ms": 62000,
     "text": "漏的基本都是没说「决定」两个字的，比如「那就这么办」，得靠上下文判断。"},
    {"idx": 4, "speaker": "孟嘉祺", "start_ms": 62000, "end_ms": 80000,
     "text": "那就把判定口径改成三类：决策、风险、未决问题，未决问题允许没有证据但必须标出来。赵鹏你来改提示词。"},
    {"idx": 5, "speaker": "赵鹏", "start_ms": 80000, "end_ms": 95000,
     "text": "行，我周五之前改完，顺便把证据回查的阈值也调一下。"},
    {"idx": 6, "speaker": "孙倩", "start_ms": 95000, "end_ms": 118000,
     "text": "引用这块我担心答非所问。现在只做向量检索，问上线时间会返回讲部署流程的，得加关键词混合。"},
    {"idx": 7, "speaker": "孟嘉祺", "start_ms": 118000, "end_ms": 140000,
     "text": "混合检索可以，但引用必须能点回原文页码。这个优先级最高，孙倩负责。"},
    {"idx": 8, "speaker": "孙倩", "start_ms": 140000, "end_ms": 155000,
     "text": "好，我下周一把引用校验做出来，先用重合度算，后面再换模型打分。"},
]

COMBOS = [
    ("deepseek-flash", "off"),
    ("deepseek-flash", "on"),
    ("deepseek-v4-pro", "off"),
    ("deepseek-v4-pro", "on"),
]


def main() -> int:
    tx = transcript_text(SEGMENTS)
    seg_map = {s["idx"]: s for s in SEGMENTS}
    provider = OpenAICompatProvider()
    rows = []

    for model, thinking in COMBOS:
        started = time.time()
        try:
            comp = provider.chat(
                [{"role": "system", "content": prompts.DECIDER},
                 {"role": "user", "content": f"会议日期：2026-09-02\n转写稿：\n{tx}"}],
                model=model,
                temperature=0.1,
                max_tokens=4000,
                json_mode=True,
                thinking=thinking,
                timeout=300,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"{model:16s} thinking={thinking:3s} 失败：{exc}")
            continue
        elapsed = time.time() - started
        obj = _try_load(comp.text)
        items = (obj or {}).get("items", []) if isinstance(obj, dict) else []
        kept, stats = validate_evidence([dict(i) for i in items], seg_map)
        row = {
            "model": model,
            "thinking": thinking,
            "elapsed_s": round(elapsed, 1),
            "tokens_in": comp.tokens_in,
            "tokens_out": comp.tokens_out,
            "reasoning_tokens": comp.raw.get("reasoning_tokens", 0),
            "items": len(items),
            "kept": len(kept),
            "grounded_rate": stats["grounded_rate"],
            "kinds": sorted({str(i.get("kind")) for i in kept}),
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))

    out = Path(__file__).resolve().parents[1] / "data" / "bench_reasoning.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
