"""诊断 writer：直接看模型返回什么，以及 apply 的还原是否精确。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from app.core import prompts  # noqa: E402
from app.core.providers import chat_safe  # noqa: E402
from app.core.routing import runtime  # noqa: E402
from app.core.writer import _blocks, apply_blocks, style_report  # noqa: E402

ORIGINAL = """# 项目周报（第 34 周）

## 一、本周进展

1. 完成会议纪要多 Agent 流水线的联调，决议抽取准确率从 71% 提升到 88%。
2. 知识库检索接入混合召回，问答首字响应时间稳定在 1.1 秒以内。
3. 与设计确认了看板与 Trace 面板的交互稿，进入开发。

## 二、存在问题

1. 转写稿过长时（超过 1.4 万字），后段内容会被截断，需要补分段摘要策略。
2. 演示环境的后端实例内存偏小，长文档解析偶发超时。
"""

INSTRUCTION = "把语言改得更口语、更像人写的，去掉「赋能、闭环」这类词"


def main() -> None:
    model, temp = runtime.model_for("writer")
    print(f"model={model} temp={temp} thinking={runtime.thinking_for('writer')}")
    user = f"文档标题：项目周报\n修改要求：{INSTRUCTION}\n\n原文：\n{ORIGINAL}"
    comp, prov = chat_safe(
        [{"role": "system", "content": prompts.WRITER}, {"role": "user", "content": user}],
        model=model, temperature=temp, max_tokens=3000, json_mode=True,
        thinking=runtime.thinking_for("writer"),
    )
    text = comp.text or ""
    print("provider:", prov, "finish:", comp.raw.get("finish_reason"), "out_tokens:", comp.tokens_out)
    print("RAW:", text[:800].replace("\n", "\\n"))
    try:
        obj = json.loads(text)
        print("keys:", list(obj))
        revised = obj.get("revised", "") or ""
        print("revised_len:", len(revised), "orig_len:", len(ORIGINAL))
        print("same_lines:", sum(1 for a, b in zip(revised.splitlines(), ORIGINAL.splitlines()) if a == b))
        print("notes:", obj.get("notes"))
    except Exception as exc:  # noqa: BLE001
        print("json parse failed:", exc)

    blocks = _blocks(ORIGINAL, ORIGINAL.replace("项目周报（第 34 周）", "项目周报 · 第 34 周"))
    restored = apply_blocks(ORIGINAL, blocks, [])
    print("no-accept restore exact:", restored.strip() == ORIGINAL.strip())
    acc = [i for i, b in enumerate(blocks) if b["type"] not in {"equal", "skip"}]
    applied = apply_blocks(ORIGINAL, blocks, acc)
    print("all-accept first line:", applied.splitlines()[0])
    print("style avg_sentence:", style_report(ORIGINAL)["avg_sentence"])


if __name__ == "__main__":
    main()
