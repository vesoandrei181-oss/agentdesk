"""模型接入层。

所有 Provider 实现同一个 Protocol，编排核只认 `chat()`：
换 DeepSeek、OpenAI 兼容网关、本地 Ollama 都不用改上层代码。

内置 MockProvider 用于无密钥演示：它按 Agent 名字返回构造好的结构化结果，
保证流水线在任何网络条件下都能跑通（评审现场最怕的就是"AI 那步转圈"）。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from ..config import settings


@dataclass
class Completion:
    text: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    raw: dict = field(default_factory=dict)

    @property
    def cost_usd(self) -> float:
        # DeepSeek 量级：输入 $0.27/M、输出 $1.10/M（按官方定价折算，用于成本看板）
        return self.tokens_in / 1_000_000 * 0.27 + self.tokens_out / 1_000_000 * 1.10


class LLMProvider(Protocol):
    name: str

    def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        json_mode: bool = False,
        timeout: float = 120.0,
        thinking: str = "on",
    ) -> Completion: ...


class OpenAICompatProvider:
    """OpenAI 兼容协议（DeepSeek 官方、各类中转、vLLM 都是这套）。"""

    name = "openai-compat"

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key or settings.llm_api_key

    def chat(self, messages, *, model=None, temperature=0.3, max_tokens=2000, json_mode=False,
             timeout=120.0, thinking="on"):
        model = model or settings.llm_model_fast
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if thinking == "off":
            # DeepSeek 的扩展参数：显式关闭思维链，抽取类任务可直接省掉数十秒
            payload["thinking"] = {"type": "disabled"}

        started = time.time()
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        usage = data.get("usage", {}) or {}
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        details = usage.get("completion_tokens_details") or {}
        return Completion(
            text=message.get("content") or "",
            model=data.get("model", model),
            tokens_in=int(usage.get("prompt_tokens", 0)),
            tokens_out=int(usage.get("completion_tokens", 0)),
            latency_ms=int((time.time() - started) * 1000),
            raw={
                "id": data.get("id"),
                "finish_reason": choice.get("finish_reason"),
                "reasoning_tokens": int(details.get("reasoning_tokens", 0) or 0),
                "cache_hit_tokens": int(usage.get("prompt_cache_hit_tokens", 0) or 0),
                "has_reasoning": bool(message.get("reasoning_content")),
            },
        )


    def stream_chat(self, messages, *, model=None, temperature=0.3, max_tokens=1600, timeout=180.0):
        """SSE 逐字流。浏览器端用 EventSource 拿，断线自动重连。"""
        model = model or settings.llm_model_fast
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        data = json.loads(chunk)
                        delta = data["choices"][0].get("delta", {}).get("content")
                    except Exception:
                        continue
                    if delta:
                        yield delta


class OllamaProvider(OpenAICompatProvider):
    """本地模型，走 Ollama 的 OpenAI 兼容端点。"""

    name = "ollama"

    def __init__(self):
        super().__init__(base_url="http://127.0.0.1:11434/v1", api_key="ollama")


class MockProvider:
    """无密钥兜底：按 system prompt 里的 AGENT 标记返回结构化假数据。"""

    name = "mock"

    def stream_chat(self, messages, *, model=None, temperature=0.3, max_tokens=1600, timeout=5.0):
        text, _ = self.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)
        for i in range(0, len(text), 6):
            yield text[i : i + 6]

    def chat(self, messages, *, model=None, temperature=0.3, max_tokens=2000, json_mode=False,
             timeout=5.0, thinking="on"):
        from .mock_fixtures import mock_reply

        system = messages[0]["content"] if messages else ""
        user = messages[-1]["content"] if messages else ""
        text = mock_reply(system, user)
        return Completion(
            text=text,
            model="mock-local",
            tokens_in=max(1, len(user) // 2),
            tokens_out=max(1, len(text) // 2),
            latency_ms=120,
        )


_provider: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """按配置构造单例。mock 只在没有 key 或显式指定时启用。"""
    global _provider
    if _provider is not None:
        return _provider

    provider_name = settings.provider_name.lower()
    if provider_name == "mock" or not settings.llm_api_key:
        _provider = MockProvider()
    elif provider_name == "ollama":
        _provider = OllamaProvider()
    else:
        _provider = OpenAICompatProvider()
    return _provider


def reset_provider() -> None:
    global _provider
    _provider = None


def chat_safe(messages: list[dict], **kwargs) -> tuple[Completion, str]:
    """调用当前 Provider；网络/额度异常时自动降级到 Mock，并留下痕迹。

    现场演示最怕上游抽风，所以宁可返回一份"结构正确的兜底结果"并在 Trace 里标注降级，
    也不要让整个页面报错。
    """
    provider = get_provider()
    try:
        return provider.chat(messages, **kwargs), provider.name
    except Exception as exc:  # noqa: BLE001
        comp = MockProvider().chat(messages, **kwargs)
        comp.raw = {"fallback": True, "from": provider.name, "error": str(exc)[:240]}
        return comp, f"mock(fallback:{provider.name})"
