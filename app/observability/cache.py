"""Semantic cache for near-duplicate queries.

Rather than exact-string caching, this embeds the incoming query and checks
cosine similarity against previously cached queries. A hit above the
threshold skips retrieval + generation entirely and returns the prior
answer, with the trace annotated so cost savings are visible.

In-process + single-instance for the MVP. For multi-instance deployments,
back this with Redis (store vectors in a Redis vector index or just do
brute-force cosine over a small cached set, which is what this class does).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

import numpy as np

from app.config import settings


@dataclass
class CacheEntry:
    query: str
    embedding: np.ndarray
    response: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    hits: int = 0


class SemanticCache:
    def __init__(self, max_entries: int | None = None, threshold: float | None = None):
        self.max_entries = max_entries or settings.cache_max_entries
        self.threshold = threshold or settings.cache_similarity_threshold
        self._entries: List[CacheEntry] = []

    def _cosine(self, a: np.ndarray, b: np.ndarray) -> float:
        denom = (np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    def lookup(self, query_embedding: np.ndarray) -> Optional[CacheEntry]:
        best_entry, best_score = None, -1.0
        for entry in self._entries:
            score = self._cosine(query_embedding, entry.embedding)
            if score > best_score:
                best_entry, best_score = entry, score
        if best_entry is not None and best_score >= self.threshold:
            best_entry.hits += 1
            return best_entry
        return None

    def store(self, query: str, query_embedding: np.ndarray, response: Dict[str, Any]):
        if len(self._entries) >= self.max_entries:
            # evict least-recently-created entry (simple FIFO for the MVP)
            self._entries.pop(0)
        self._entries.append(CacheEntry(query=query, embedding=query_embedding, response=response))

    def stats(self) -> Dict[str, Any]:
        return {
            "entries": len(self._entries),
            "total_hits": sum(e.hits for e in self._entries),
        }

    def clear(self):
        self._entries.clear()


_caches: Dict[str, SemanticCache] = {}


def get_cache(tenant_id: str = "default") -> SemanticCache:
    """Tenant-scoped: a shared cache would leak one tenant's answers to
    another's near-duplicate queries."""
    if tenant_id not in _caches:
        _caches[tenant_id] = SemanticCache()
    return _caches[tenant_id]
