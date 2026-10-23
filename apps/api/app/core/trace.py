"""执行记录器：把每个 Agent 步骤写进 run_steps，前端 Trace 面板直接读这张表。"""

from __future__ import annotations

import time

from sqlalchemy.orm import Session

from ..models import Run, RunStep


class Recorder:
    def __init__(self, db: Session, workspace_id: int, kind: str, title: str, model: str = ""):
        self.db = db
        self.run = Run(workspace_id=workspace_id, kind=kind, title=title, model=model, status="running")
        db.add(self.run)
        db.commit()
        db.refresh(self.run)
        self._idx = 0
        self._t0 = time.time()
        self.tokens_in = 0
        self.tokens_out = 0
        self.cost = 0.0
        self.cache_hits = 0

    @property
    def id(self) -> int:
        return self.run.id

    def add(
        self,
        agent: str,
        *,
        status: str = "ok",
        input_summary: str = "",
        output_summary: str = "",
        meta: dict | None = None,
        evidence_count: int = 0,
        payload: dict | None = None,
    ) -> RunStep:
        meta = meta or {}
        tin = int(meta.get("tokens_in", 0) or 0)
        tout = int(meta.get("tokens_out", 0) or 0)
        cost = float(meta.get("cost_usd", 0.0) or 0.0)
        cache_hit = bool(meta.get("cache_hit", False))

        self.tokens_in += tin
        self.tokens_out += tout
        self.cost += cost
        if cache_hit:
            self.cache_hits += 1

        step = RunStep(
            run_id=self.run.id,
            idx=self._idx,
            agent=agent,
            status=status,
            input_summary=input_summary[:2000],
            output_summary=output_summary[:2000],
            tokens_in=tin,
            tokens_out=tout,
            latency_ms=int(meta.get("latency_ms", 0) or 0),
            cache_hit=cache_hit,
            evidence_count=evidence_count,
            payload={k: v for k, v in (payload or {}).items() if k != "raw"},
        )
        self._idx += 1
        self.db.add(step)
        self.db.commit()
        return step

    def finish(self, status: str = "done", **meta) -> Run:
        run = self.db.get(Run, self.run.id)
        run.status = status
        run.tokens_in = self.tokens_in
        run.tokens_out = self.tokens_out
        run.cost_usd = round(self.cost, 6)
        run.cache_hits = self.cache_hits
        run.latency_ms = int((time.time() - self._t0) * 1000)
        if meta:
            run.meta = {**(run.meta or {}), **meta}
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run
