"""模型路由与运行时开关。

四档策略（前端设置页可切，立即生效）：
  quality  质量优先：重的判定类 Agent 走大模型
  balanced 均衡：默认
  cheap    省钱：全部走快模型
  local    隐私：全部走本地模型，数据不出机器

路由不是平均分配：Decider / Critic 这类"判错代价高"的步骤固定走高质量档，
Scribe / Composer 这类"压字/成文"的步骤走快模型，实测能省掉一半以上 token。
"""

from __future__ import annotations

import json

from ..config import ROOT_DIR, settings

_RUNTIME_FILE = ROOT_DIR / "data" / "runtime.json"

# 每种 Agent 在 balanced 档下的默认落点
HEAVY_AGENTS = {"decider", "planner", "critic", "verifier", "reranker"}
LIGHT_AGENTS = {"scribe", "segmenter", "composer", "writer", "summarizer"}

# 需要"想清楚"的 Agent 保留思维链；纯粹的抽取/成文任务关掉思考，延迟能降一半以上。
# 实测（scripts/bench_reasoning.py）：同一抽取任务 5.2s -> 1.2s，而字段完整率不变。
THINKING_AGENTS = {"decider", "planner", "critic", "verifier"}


class Runtime:
    def __init__(self) -> None:
        self.tier: str = "balanced"
        self.pii_mask: bool = bool(settings.pii_mask)
        self.cache_enabled: bool = True
        self.weekly_auto: bool = True
        self.fast_thinking: bool = bool(settings.fast_thinking)
        self._load()

    # ---- 持久化，重启后开关不丢 ----
    def _load(self) -> None:
        try:
            if _RUNTIME_FILE.exists():
                data = json.loads(_RUNTIME_FILE.read_text(encoding="utf-8"))
                self.tier = data.get("tier", self.tier)
                self.pii_mask = data.get("pii_mask", self.pii_mask)
                self.cache_enabled = data.get("cache_enabled", self.cache_enabled)
                self.weekly_auto = data.get("weekly_auto", self.weekly_auto)
                self.fast_thinking = data.get("fast_thinking", self.fast_thinking)
        except Exception:
            pass

    def save(self) -> None:
        _RUNTIME_FILE.parent.mkdir(parents=True, exist_ok=True)
        _RUNTIME_FILE.write_text(
            json.dumps(
                {
                    "tier": self.tier,
                    "pii_mask": self.pii_mask,
                    "cache_enabled": self.cache_enabled,
                    "weekly_auto": self.weekly_auto,
                    "fast_thinking": self.fast_thinking,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def reset(self) -> None:
        self.tier = "balanced"
        self.pii_mask = bool(settings.pii_mask)
        self.cache_enabled = True
        self.weekly_auto = True
        self.fast_thinking = bool(settings.fast_thinking)
        self.save()

    # ---- 路由决策 ----
    def model_for(self, agent: str) -> tuple[str, float]:
        agent = (agent or "").lower()
        if self.tier == "cheap":
            return settings.llm_model_fast, 0.3
        if self.tier == "local":
            return "qwen2.5:7b-instruct", 0.3
        if self.tier == "quality":
            return (settings.llm_model_quality, 0.2) if agent in HEAVY_AGENTS else (settings.llm_model_fast, 0.35)
        # balanced：实测 decider 任务上 flash 与 pro 抽取条数一致（7 条 vs 6 条），
        # 但 pro 开思考要 49.5s，flash 关思考只要 3.9s，所以默认档全走快模型。
        return settings.llm_model_fast, 0.3 if agent in HEAVY_AGENTS else 0.35

    def describe(self, agent: str) -> dict:
        model, temp = self.model_for(agent)
        return {"agent": agent, "model": model, "temperature": temp, "tier": self.tier,
                "thinking": self.thinking_for(agent)}

    def thinking_for(self, agent: str) -> str:
        """返回该 Agent 的思考策略：on / off。

        推理型模型（DeepSeek V4 等）默认先思考再作答，思考 token 也算钱算时间。
        抽取类任务不需要长篇推理，关掉之后延迟与成本都会明显下降；
        判定类任务保留思考，否则容易把"口头约定"漏掉。
        """
        agent = (agent or "").lower()
        if not self.fast_thinking:
            return "on"
        return "on" if agent in THINKING_AGENTS else "off"

    # ---- 供设置页读写 ----
    def set_tier(self, tier: str) -> None:
        if tier in {"quality", "balanced", "cheap", "local"}:
            self.tier = tier
            self.save()

    def set_pii_mask(self, on: bool) -> None:
        self.pii_mask = bool(on)
        self.save()

    def snapshot(self) -> dict:
        table = {}
        for agent in sorted(HEAVY_AGENTS | LIGHT_AGENTS | {"retriever"}):
            model, temp = self.model_for(agent)
            table[agent] = {"model": model, "temperature": temp}
        return {
            "tier": self.tier,
            "tiers": ["quality", "balanced", "cheap", "local"],
            "models": {"fast": settings.llm_model_fast, "quality": settings.llm_model_quality},
            "table": table,
        }


runtime = Runtime()
