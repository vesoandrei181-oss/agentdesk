"""核心算法单元测试：不依赖网络，也不依赖数据库。

跑法：pytest -q
覆盖点都是「改坏了会静默出错」的地方：
- difflib 差异块必须能逐字还原原文（否则「全选应用」会吃掉内容）；
- 补丁定位失败必须被跳过而不是抛错；
- 引用校验要能区分真引用与凑数引用；
- 工期预测对模糊动词、依赖、临期要给出方向正确的调整。
"""
from __future__ import annotations

import pytest

from app.core.embedding import cosine, embed, tokenize
from app.core.guard import mask, unmask
from app.core.predict import estimate
from app.core.rag import chunk_pages, verify_citations
from app.core.routing import Runtime
from app.core.writer import _apply_patches, _blocks, apply_blocks, style_report

SAMPLE = """# 项目周报（第 34 周）

## 一、本周进展

1. 完成会议纪要多 Agent 流水线的联调，决议抽取准确率从 71% 提升到 88%。
2. 知识库检索接入混合召回，问答首字响应时间稳定在 1.1 秒以内。

## 二、存在问题

1. 转写稿过长时会被截断，需要补分段摘要策略。
"""


# ---------------------------------------------------------------- 差异块
def test_blocks_roundtrip_without_accept():
    revised = SAMPLE.replace("71%", "82%").replace("1.1 秒", "1.2 秒")
    blocks = _blocks(SAMPLE, revised)
    assert apply_blocks(SAMPLE, blocks, []) == SAMPLE


def test_blocks_apply_all_restores_revised():
    revised = SAMPLE.replace("71%", "82%")
    blocks = _blocks(SAMPLE, revised)
    accepted = [i for i, b in enumerate(blocks) if b["type"] in {"replace", "insert", "delete"}]
    assert apply_blocks(SAMPLE, blocks, accepted) == revised


def test_blocks_skip_keeps_text():
    blocks = _blocks(SAMPLE, SAMPLE + "\n附加一行。")
    skips = [b for b in blocks if b["type"] == "skip"]
    joined = "\n".join("\n".join(b["lines"]) for b in skips)
    assert "存在问题" in joined


def test_apply_patches_ops():
    text = "AA 甲乙丙 BB 丁戊己 CC"
    out, applied = _apply_patches(text, [
        {"op": "replace", "target": "甲乙丙", "new_text": "甲X丙"},
        {"op": "delete", "target": "丁戊己"},
        {"op": "insert_after", "target": "CC", "new_text": "追加"},
        {"op": "replace", "target": "不存在", "new_text": "x"},
    ])
    assert out == "AA 甲X丙 BB  CC追加"
    assert [p["ok"] for p in applied] == [True, True, True, False]


def test_style_report_counts_long_sentences():
    report = style_report("这件事我们经过反复讨论之后决定还是先把切片长度调整到五百二十个字再说，因为现在的长度确实太碎了。" * 2)
    assert report["sentences"] >= 2
    assert report["max_sentence"] > 45
    assert report["zh_chars"] > 40


# ---------------------------------------------------------------- 引用校验
CHUNKS = [
    {"text": "引用校验阈值是 0.55，低于该重合度的条目会被丢弃，阈值 0.45 时误留 11%。", "doc_title": "product", "page": 1, "chunk_id": 1},
    {"text": "鉴权使用 Bearer token，登录接口返回 HMAC 签名的令牌，有效期 7 天。", "doc_title": "api", "page": 2, "chunk_id": 2},
    {"text": "部署建议 4 核 8G，50 并发下 P95 延迟 2.4 秒。", "doc_title": "ops", "page": 3, "chunk_id": 3},
]


def test_verify_citations_marks_true_citation_strong():
    answer = "引用校验阈值是 0.55[1]。"
    res = verify_citations(answer, CHUNKS)
    assert res[0]["status"] == "strong"


def test_verify_citations_rejects_wrong_number():
    answer = "引用校验阈值是 0.72[1]。"  # 数字对不上，必须判弱
    res = verify_citations(answer, CHUNKS)
    assert res[0]["status"] == "weak"


def test_verify_citations_flags_out_of_range():
    res = verify_citations("阈值是 0.55[9]。", CHUNKS)
    assert res[0]["status"] == "missing"


# ---------------------------------------------------------------- 检索切片
def test_chunk_pages_respects_overlap():
    pages = [(1, "# 标题\n\n" + "句子。" * 400)]
    chunks = chunk_pages(pages, target=200, overlap=40)
    assert len(chunks) > 1
    assert all(len(c["text"]) <= 320 for c in chunks)


def test_tokenize_and_cosine():
    a = embed("会议纪要 证据链")
    b = embed("会议纪要 证据链 校验")
    assert cosine(a, b) > 0.8
    assert len(tokenize("引用校验")) > 0


# ---------------------------------------------------------------- 脱敏
def test_mask_and_unmask_roundtrip():
    raw = "联系人手机 13812345678，身份证 110101199003074512。"
    masked = mask(raw)
    assert "13812345678" not in masked.text
    assert unmask(masked.text, masked.mapping) == raw


# ---------------------------------------------------------------- 工期预测
def test_estimate_grows_with_fuzzy_verb():
    plain = estimate("写接口文档")
    fuzzy = estimate("调研一下接口文档怎么写")
    assert fuzzy["p50_hours"] >= plain["p50_hours"]


def test_estimate_p90_above_p50():
    r = estimate("完成看板拖拽", priority="high", deps=2)
    assert r["p90_hours"] > r["p50_hours"]
    assert isinstance(r["risk"], str) and r["risk"]


def test_estimate_overdue_shrinks_slack():
    near = estimate("上线检查", days_to_due=1)
    far = estimate("上线检查", days_to_due=10)
    assert near["slack_days"] < far["slack_days"]


# ---------------------------------------------------------------- 路由
def test_runtime_tiers():
    rt = Runtime()
    rt.set_tier("balanced")
    model, temp = rt.model_for("decider")
    assert model and 0 <= temp <= 1
    rt.set_tier("quality")
    heavy_model, _ = rt.model_for("decider")
    light_model, _ = rt.model_for("scribe")
    assert heavy_model != light_model or rt.fast_thinking is False
    rt.set_tier("balanced")


@pytest.mark.parametrize("agent", ["decider", "planner", "critic", "verifier", "scribe"])
def test_thinking_flag_shape(agent):
    rt = Runtime()
    assert rt.thinking_for(agent) in {"on", "off"}
