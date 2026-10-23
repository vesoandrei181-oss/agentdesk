"""Mock 模式下的结构化假数据。

只在没有配置密钥、或显式 LLM_PROVIDER=mock 时使用。
目的不是"假装有 AI"，而是保证评委打开演示时，页面上的每个区块都有内容可看。
"""

from __future__ import annotations

import json
import re

_AGENT_RE = re.compile(r"AGENT=([a-z_]+)")


def _agent_of(system: str) -> str:
    m = _AGENT_RE.search(system or "")
    return m.group(1) if m else "generic"


_FIXTURES: dict[str, dict] = {
    "scribe": {
        "speakers": ["刘畅", "王雪", "陈拓"],
        "cleaned_note": "本轮讨论围绕 Q3 版本排期展开，涉及接口联调、灰度范围与测试资源三件事。",
        "filler_removed": 37,
    },
    "segmenter": {
        "topics": [
            {"title": "Q3 版本排期", "segments": [1, 2, 3, 4], "summary": "确认 9 月 8 日提测，9 月 15 日灰度 20%。"},
            {"title": "接口联调阻塞", "segments": [5, 6, 7], "summary": "支付侧回调鉴权字段缺失，需本周内补齐。"},
            {"title": "测试资源与灰度", "segments": [8, 9, 10], "summary": "测试同学 9 月 1 日起投入两人，灰度先内测团队。"},
        ]
    },
    "decider": {
        "items": [
            {
                "kind": "decision",
                "text": "Q3 版本定在 9 月 8 日提测，9 月 15 日对 20% 用户灰度。",
                "evidence": [{"segment_id": 2, "quote": "那就定 9 月 8 号提测，15 号灰度两成用户"}],
                "confidence": 0.93,
            },
            {
                "kind": "risk",
                "text": "支付回调鉴权字段缺失会阻塞联调，当前无兜底方案。",
                "evidence": [{"segment_id": 6, "quote": "回调里的鉴权字段现在还没有，联调过不去"}],
                "confidence": 0.88,
            },
            {
                "kind": "open_question",
                "text": "灰度放量节奏（20% → 50%）尚未确定评估口径。",
                "evidence": [{"segment_id": 9, "quote": "放量到一半怎么评估，这个还没说"}],
                "confidence": 0.72,
            },
        ]
    },
    "planner": {
        "items": [
            {"text": "补齐支付回调鉴权字段并联调通过", "owner_name": "陈拓", "due_date": "2026-09-02",
             "priority": "high", "evidence": [{"segment_id": 6, "quote": "这周我把字段补上，下周一联调"}]},
            {"text": "输出灰度放量评估口径文档", "owner_name": "王雪", "due_date": "2026-09-05",
             "priority": "medium", "evidence": [{"segment_id": 9, "quote": "评估口径我来写一版"}]},
            {"text": "9 月 1 日起投入两名测试同学", "owner_name": "刘畅", "due_date": "2026-09-01",
             "priority": "medium", "evidence": [{"segment_id": 10, "quote": "测试这边九月一号能出两个人"}]},
        ]
    },
    "critic": {
        "score": 0.86,
        "verdict": "pass",
        "issues": [{"target": "open_question:3", "problem": "证据只覆盖了提问，未包含结论", "action": "keep_low_confidence"}],
        "rewrite": [],
    },
    "composer": {
        "summary": "会议确认了 Q3 的提测与灰度节奏，同时暴露支付回调鉴权字段缺失这一阻塞项；"
                   "测试资源已落实两人，但灰度放量的评估口径仍待明确。",
        "highlights": ["9 月 8 日提测、9 月 15 日灰度 20%", "支付回调鉴权字段本周补齐", "灰度评估口径待补"],
    },
    "writer": {
        "patches": [
            {"op": "replace", "target": "本周完成了接口联调工作", "new_text": "本周完成支付、订单两条链路的联调，回调鉴权字段已补齐并回归通过",
             "reason": "把笼统表述替换为可验证的具体进展"},
            {"op": "insert_after", "target": "下周计划推进灰度", "new_text": "灰度首轮控制在 20%，同时观察下单成功率与客诉量两个指标。",
             "reason": "补充可量化的放量口径"},
        ],
        "style_note": "原文偏口语、缺少量化信息，已按团队周报习惯补上指标与时间点。",
    },
    "verifier": {"supported": True, "score": 0.84, "reason": "引用片段与结论语义一致"},
    "reranker": {"order": [1, 3, 2, 4], "reason": "按与问题的直接相关性排序"},
    "weekly": {
        "headline": "本周推进 3 个里程碑，1 项阻塞已解除",
        "sections": [
            {"title": "本周进展", "content": "支付回调鉴权字段补齐并完成回归，Q3 提测排期确认，知识库补齐接口文档 4 篇。"},
            {"title": "风险", "content": "灰度评估口径未定，若 9 月 5 日前仍未产出，将影响 9 月 15 日放量。"},
            {"title": "下周重点", "content": "完成 20% 灰度、输出放量评估报告、补齐压测脚本。"},
        ],
    },
}


def mock_reply(system: str, user: str) -> str:
    agent = _agent_of(system)
    data = _FIXTURES.get(agent)
    if data is None:
        return json.dumps({"note": "mock 模式：未配置模型密钥，返回占位结果。", "agent": agent}, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)
