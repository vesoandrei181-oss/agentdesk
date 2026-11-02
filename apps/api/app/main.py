"""FastAPI 入口。

前端构建产物若存在（apps/web/dist），直接由本服务托管，
部署时只需要一个进程 + 一个域名，省掉跨域与第二个平台。
"""

from __future__ import annotations

import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT_DIR, settings
from .db import init_db
from .core.providers import get_provider
from .core.routing import runtime
from .routers import auth, docs, insights, kb, meetings, prefs, tasks

app = FastAPI(
    title="AgentDesk API",
    description="AI 协同办公台：会议纪要 / 文档写作 / 知识库问答 / 任务看板",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, meetings, docs, kb, tasks, insights, prefs):
    app.include_router(module.router)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    print(f"[api] db={settings.db_url}")
    print(f"[api] llm={settings.llm_provider} mock={settings.is_mock} tier={runtime.tier}")


@app.get("/api/health")
def health():
    provider = get_provider()
    return {
        "ok": True,
        "time": int(time.time()),
        "provider": settings.provider_name,
        "impl": getattr(provider, "name", "unknown"),
        "model_fast": settings.llm_model_fast,
        "model_quality": settings.llm_model_quality,
        "mock": bool(settings.is_mock),
        "tier": runtime.tier,
        "provider_ready": bool(provider),
        "pii_mask": runtime.pii_mask,
        "has_key": bool(settings.llm_api_key),
    }


WEB_DIST = ROOT_DIR / "apps" / "web" / "dist"
if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")
