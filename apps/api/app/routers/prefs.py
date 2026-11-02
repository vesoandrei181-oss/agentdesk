"""设置：模型路由档位、脱敏开关、语义缓存。演示时现场切档，token 与耗时会立刻变化。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..config import settings
from ..deps import current_workspace
from ..models import Workspace
from ..core.cache import cache
from ..core.routing import runtime

router = APIRouter(prefix="/api/settings", tags=["settings"])


class RuntimeIn(BaseModel):
    tier: str | None = None
    pii_mask: bool | None = None
    semantic_cache: bool | None = None
    fast_thinking: bool | None = None


@router.get("/runtime")
def get_runtime():
    return {
        **runtime.snapshot(),
        "provider": settings.provider_name,
        "base_url": settings.llm_base_url,
        "mock": bool(settings.is_mock),
        "fast_thinking": runtime.fast_thinking,
        "pii_mask": runtime.pii_mask,
        "semantic_cache": runtime.cache_enabled,
        "budget": settings.token_budget,
        "cache_threshold": settings.semantic_cache_threshold,
    }


@router.put("/runtime")
def set_runtime(body: RuntimeIn, ws: Workspace = Depends(current_workspace)):
    if body.tier:
        runtime.set_tier(body.tier)
    if body.pii_mask is not None:
        runtime.set_pii_mask(body.pii_mask)
    if body.semantic_cache is not None:
        runtime.cache_enabled = body.semantic_cache
        runtime.save()
    if body.fast_thinking is not None:
        runtime.fast_thinking = body.fast_thinking
        runtime.save()
    return {"ok": True, **runtime.snapshot(), "pii_mask": runtime.pii_mask,
            "semantic_cache": runtime.cache_enabled, "fast_thinking": runtime.fast_thinking}


@router.get("/cache")
def cache_stats():
    return cache.stats()


@router.post("/cache/clear")
def clear_cache():
    n = cache.clear()
    return {"cleared": n, **cache.stats()}
