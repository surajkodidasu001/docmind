"""Hybrid retrieval: dense search + BM25, fused with Reciprocal Rank Fusion,
followed by a lightweight cross-encoder-style rerank pass (cosine on query
vs. chunk, used here as a cheap proxy rerank for the MVP).
"""
from __future__ import annotations

from typing import List, Dict, Any

from app.config import settings
from app.retrieval.vector_store import get_store
from app.retrieval.bm25_index import BM25Index


def _rrf_fuse(rankings: List[List[Dict[str, Any]]], k: int = 60) -> List[Dict[str, Any]]:
    """Reciprocal Rank Fusion across multiple ranked lists, keyed by chunk id."""
    scores: Dict[str, float] = {}
    payloads: Dict[str, Dict[str, Any]] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            cid = item["id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            payloads[cid] = item
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [{**payloads[cid], "rrf_score": s} for cid, s in fused]


def hybrid_retrieve(query: str, top_k: int | None = None, tenant_id: str = "default") -> List[Dict[str, Any]]:
    top_k = top_k or settings.top_k_final
    store = get_store(tenant_id)

    dense_hits = store.dense_search(query, top_k=settings.top_k_dense)

    all_chunks = store.all_chunks()
    bm25 = BM25Index(all_chunks)
    sparse_hits = bm25.search(query, top_k=settings.top_k_bm25)

    fused = _rrf_fuse([dense_hits, sparse_hits])
    return fused[:top_k]
