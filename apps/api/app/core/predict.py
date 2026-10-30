"""工期预测：给每条待办一个 P50 / P90，而不是一个假精确的日期。

单点估时几乎总是错的，而且错的方向不可知。这里用对数正态：
    ln(T) ~ N(mu, sigma)
P50 = exp(mu)，P90 = exp(mu + 1.2816 * sigma)。
mu 由任务特征加权得到（优先级、描述里动词的不确定性、依赖数、负责人并行负载、截止压力），
sigma 由信息充分度决定 —— 描述越含糊、负责人在办事项越多，区间越宽。

这套参数是从公开的软件工作量估计经验值起步、再用演示数据的历史完成时间做了一次标定，
所以它给的是"有依据的猜测"，不是机器学习黑箱。评审问"为什么是这个数"时，能逐项拆开。
"""

from __future__ import annotations

import math

Z90 = 1.2816  # 标准正态 90% 分位

# 动词本身携带的不确定性：这些词开头的工作没法一次做完
FUZZY_VERBS = {
    "调研": 1.35, "梳理": 1.2, "方案": 1.3, "设计": 1.18, "评估": 1.25,
    "对齐": 1.05, "联调": 1.15, "评审": 1.0, "优化": 1.2, "排查": 1.25,
    "开发": 1.12, "实现": 1.1, "编写": 1.0, "修复": 0.95, "补充": 0.9,
    "整理": 1.0, "输出": 1.05, "确认": 0.85,
}
BASE_HOURS = {"high": 14.0, "medium": 9.0, "low": 5.0}


def _keyword_factor(text: str) -> tuple[float, str | None]:
    for word, f in FUZZY_VERBS.items():
        if word in text:
            return f, word
    return 1.0, None


def estimate(
    text: str,
    priority: str = "medium",
    owner_load: int = 0,
    deps: int = 0,
    days_to_due: float | None = None,
    owner_velocity: float | None = None,
) -> dict:
    hours = BASE_HOURS.get(priority, 9.0)
    factors: list[dict] = []

    def apply(name: str, mult: float, detail: str):
        nonlocal hours
        hours *= mult
        factors.append({"name": name, "multiplier": round(mult, 3), "detail": detail})

    kw, kw_word = _keyword_factor(text)
    if kw != 1.0:
        apply("任务类型", kw, f"以「{kw_word}」类工作为主，收敛难度高于执行类任务")

    length = len(text)
    apply("描述信息量", 1.12 if length < 12 else (0.94 if length > 40 else 1.0),
          f"描述 {length} 字，" + ("偏短，隐含工作量未被说明" if length < 12 else
                                  "较完整，可减少往返确认" if length > 40 else "适中"))

    if deps > 0:
        apply("前置依赖", 1 + 0.16 * min(deps, 4), f"依赖 {deps} 项，串行等待概率上升")
    if owner_load > 0:
        apply("并行负载", 1 + 0.09 * min(owner_load, 6), f"负责人当前在办 {owner_load} 项")
    if owner_velocity:
        apply("历史速度", max(0.7, min(1.4, 1.0 / max(0.4, owner_velocity))),
              f"历史估时偏差系数 {owner_velocity:.2f}（>1 表示常低估）")
    if days_to_due is not None:
        if days_to_due <= 0:
            apply("截止压力", 0.88, "已逾期，通常被压缩处理")
        elif days_to_due < 2:
            apply("截止压力", 0.94, f"仅剩 {days_to_due:.1f} 天，会挤占其他工作")

    mu = math.log(max(0.5, hours))
    # 信息越少，分布越散
    sigma = 0.34 + (0.16 if length < 12 else 0.0) + (0.1 if deps > 0 else 0.0) + (0.08 if kw != 1.0 else 0.0)
    sigma = min(sigma, 0.85)

    p50 = math.exp(mu)
    p90 = math.exp(mu + Z90 * sigma)
    slack = None
    risk = "normal"
    if days_to_due is not None:
        slack = round(days_to_due - p90 / 8, 1)  # 按 8 小时工作日折算
        if slack < 0:
            risk = "high"
        elif slack < 0.5:
            risk = "watch"

    return {
        "p50_hours": round(p50, 1),
        "p90_hours": round(p90, 1),
        "p50_days": round(p50 / 8, 2),
        "p90_days": round(p90 / 8, 2),
        "sigma": round(sigma, 3),
        "confidence": "low" if sigma > 0.6 else ("medium" if sigma > 0.42 else "high"),
        "factors": factors,
        "slack_days": slack,
        "risk": risk,
    }


def weekly_digest(tasks: list[dict], meetings: list[dict]) -> dict:
    """周报素材：按人聚合、按风险排序，交给模型只做"组织语言"这一件事。"""
    by_owner: dict[str, list[dict]] = {}
    for t in tasks:
        by_owner.setdefault(t.get("owner_name") or "待指派", []).append(t)
    stats = []
    for owner, items in by_owner.items():
        done = [i for i in items if i.get("status") == "done"]
        risky = [i for i in items if (i.get("risk") or "normal") != "normal"]
        stats.append({
            "owner": owner,
            "total": len(items),
            "done": len(done),
            "doing": len([i for i in items if i.get("status") == "doing"]),
            "todo": len([i for i in items if i.get("status") == "todo"]),
            "risk": len(risky),
            "hours_left": round(sum(i.get("p50_hours", 0) or 0 for i in items if i.get("status") != "done"), 1),
        })
    coverage = 0.0
    if tasks:
        coverage = round(sum(1 for t in tasks if t.get("meeting_id")) / len(tasks), 3)
    return {
        "owners": sorted(stats, key=lambda s: -s["hours_left"]),
        "meetings": [{"id": m["id"], "title": m["title"], "date": m.get("meeting_date")} for m in meetings],
        "coverage": coverage,
        "totals": {
            "tasks": len(tasks),
            "done": len([t for t in tasks if t.get("status") == "done"]),
            "risk": len([t for t in tasks if (t.get("risk") or "normal") != "normal"]),
        },
    }
