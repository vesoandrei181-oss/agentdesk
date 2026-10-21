"""语义缓存 + 响应回放。

两个用途：
1. 语义缓存：同一个问题被不同人问、或者同一段材料被反复总结时，embedding 相似度
   超过阈值直接返回上次结果，省 token 也省等待（演示里能看到"命中缓存"徽标）。
2. 回放：无密钥/断网时，按「Agent + 输入指纹」取历史真实响应，保证演示可跑。

落盘用 JSONL，进程内维持一份索引；条目上限 800 条，先进先出。
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from ..config import ROOT_DIR, settings
from .embedding import cosine, embed

_CACHE_FILE: Path = ROOT_DIR / "data" / "cache" / "semantic.jsonl"
_MAX_ENTRIES = 800


class SemanticCache:
    def __init__(self) -> None:
        self.entries: list[dict] = []
        self.hits = 0
        self.misses = 0
        self._load()

    def _load(self) -> None:
        if not _CACHE_FILE.exists():
            return
        try:
            for line in _CACHE_FILE.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self.entries.append(json.loads(line))
        except Exception:
            self.entries = []

    def _append(self, entry: dict) -> None:
        self.entries.append(entry)
        if len(self.entries) > _MAX_ENTRIES:
            self.entries = self.entries[-_MAX_ENTRIES:]
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _CACHE_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ---- 精确命中：回放用 ----
    def exact(self, namespace: str, key: str) -> dict | None:
        fp = hashlib.sha1(key.encode("utf-8")).hexdigest()
        for entry in reversed(self.entries):
            if entry.get("ns") == namespace and entry.get("fp") == fp:
                entry["hits"] = entry.get("hits", 0) + 1
                self.hits += 1
                return entry.get("payload")
        self.misses += 1
        return None

    # ---- 语义命中：缓存用 ----
    def lookup(self, namespace: str, text: str) -> dict | None:
        if not runtime_cache_enabled():
            return None
        vec = embed(text)
        best, best_score = None, 0.0
        for entry in reversed(self.entries):
            if entry.get("ns") != namespace or entry.get("vec") is None:
                continue
            score = cosine(vec, entry["vec"])
            if score > best_score:
                best, best_score = entry, score
        if best and best_score >= settings.semantic_cache_threshold:
            best["hits"] = best.get("hits", 0) + 1
            self.hits += 1
            payload = dict(best.get("payload") or {})
            payload["_cache_similarity"] = round(best_score, 4)
            return payload
        self.misses += 1
        return None

    def store(self, namespace: str, text: str, payload: dict) -> None:
        self._append(
            {
                "ns": namespace,
                "fp": hashlib.sha1(text.encode("utf-8")).hexdigest(),
                "vec": embed(text),
                "payload": payload,
                "ts": int(time.time()),
                "hits": 0,
            }
        )

    def clear(self) -> int:
        n = len(self.entries)
        self.entries = []
        self.hits = 0
        self.misses = 0
        try:
            _CACHE_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        return n

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "entries": len(self.entries),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 3) if total else 0.0,
            "threshold": settings.semantic_cache_threshold,
        }


def runtime_cache_enabled() -> bool:
    from .routing import runtime

    return runtime.cache_enabled


cache = SemanticCache()
