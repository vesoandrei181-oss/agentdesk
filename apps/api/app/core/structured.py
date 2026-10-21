"""结构化输出契约。

LLM 返回的不是"一段话"，而是业务可以直接入库的对象。所以这里做三件事：
1. 强制 JSON（response_format=json_object）+ 容错解析（代码块、前后缀噪声）；
2. 解析失败时把错误原文回灌给模型做一次自愈重试（默认最多 2 次）；
3. 统一记账：token、耗时、成本、是否命中缓存，供 Trace 与成本看板使用。

实测（见 docs/评测报告）结构化成功率 99.2%，自愈重试是其中关键的一环。
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from .cache import cache
from .providers import chat_safe
from .routing import runtime

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)


class LLMFormatError(RuntimeError):
    pass


def _try_load(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        return None
    m = _FENCE.search(text)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except Exception:
        pass
    # 退一步：截取第一个完整的 {...} 或 [...]
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                continue
    return None


def _meta(comp, extra: dict | None = None) -> dict:
    meta = {
        "model": comp.model,
        "tokens_in": comp.tokens_in,
        "tokens_out": comp.tokens_out,
        "latency_ms": comp.latency_ms,
        "cost_usd": round(comp.cost_usd, 6),
        "cache_hit": False,
    }
    if extra:
        meta.update(extra)
    return meta


def call_json(
    agent: str,
    system: str,
    user: str,
    *,
    temperature: float | None = None,
    max_tokens: int = 2400,
    retries: int = 2,
    cache_ns: str | None = None,
    use_cache: bool = False,
) -> tuple[Any, dict]:
    """返回 (对象, 记账信息)。失败抛 LLMFormatError，由上层决定降级策略。"""
    model, default_temp = runtime.model_for(agent)
    thinking = runtime.thinking_for(agent)

    if use_cache and cache_ns:
        cached = cache.lookup(cache_ns, user)
        if cached is not None:
            payload = cached.pop("_payload", None)
            if payload is not None:
                return payload, {"model": "semantic-cache", "tokens_in": 0, "tokens_out": 0,
                                 "latency_ms": 0, "cost_usd": 0.0, "cache_hit": True,
                                 "similarity": cached.get("_cache_similarity")}

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    total_in = total_out = total_ms = 0
    last_text = ""
    budget = max_tokens

    for attempt in range(retries + 1):
        comp, used = chat_safe(
            messages,
            model=model,
            temperature=default_temp if temperature is None else temperature,
            max_tokens=budget,
            json_mode=True,
            thinking=thinking,
        )
        total_in += comp.tokens_in
        total_out += comp.tokens_out
        total_ms += comp.latency_ms
        last_text = comp.text
        over_budget = (comp.raw or {}).get("finish_reason") == "length" or not comp.text.strip()

        obj = _try_load(comp.text)
        if obj is not None:
            if use_cache and cache_ns:
                cache.store(cache_ns, user, {**obj, "_payload": obj} if isinstance(obj, dict) else {"data": obj})
            meta = _meta(comp)
            meta.update({"tokens_in": total_in, "tokens_out": total_out, "latency_ms": total_ms,
                         "attempts": attempt + 1, "agent": agent, "provider": used,
                         "max_tokens": budget, "thinking": thinking})
            if comp.raw.get("fallback"):
                meta["fallback"] = comp.raw.get("from")
            return obj, meta

        if over_budget:
            # 推理型模型的思考 token 也算在 max_tokens 里，给太少就会"只思考不回答"。
            # 这里把预算翻倍重试，而不是把空输出当成模型说错话。
            budget = min(int(budget * 2.2), 8000)
            continue

        # 自愈：把模型自己的错误输出和格式要求一起回灌
        messages.append({"role": "assistant", "content": comp.text[:2000]})
        messages.append(
            {
                "role": "user",
                "content": "上面的输出不是合法 JSON，无法解析。请只返回一个合法 JSON 对象，不要任何解释、不要代码块标记。",
            }
        )

    raise LLMFormatError(f"{agent} 连续 {retries + 1} 次未返回合法 JSON；最后输出前缀：{last_text[:200]}")


def call_text(
    agent: str,
    system: str,
    user: str,
    *,
    temperature: float | None = None,
    max_tokens: int = 1600,
) -> tuple[str, dict]:
    model, default_temp = runtime.model_for(agent)
    thinking = runtime.thinking_for(agent)
    started = time.time()
    comp, used = chat_safe(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=model,
        temperature=default_temp if temperature is None else temperature,
        max_tokens=max_tokens,
        thinking=thinking,
    )
    meta = _meta(comp)
    meta["agent"] = agent
    meta["provider"] = used
    meta["wall_ms"] = int((time.time() - started) * 1000)
    return comp.text, meta
