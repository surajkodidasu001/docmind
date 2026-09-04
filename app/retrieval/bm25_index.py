"""In-memory BM25 sparse index, rebuilt from the vector store's payloads.

For a weekend MVP this is rebuilt on demand rather than persisted separately;
swap for a persisted index (e.g. Whoosh/Elasticsearch) at scale.
"""
from __future__ import annotations

from typing import List, Dict, Any
from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> List[str]:
    return text.lower().split()


class BM25Index:
    def __init__(self, chunks: List[Dict[str, Any]]):
        self.chunks = chunks
        corpus = [_tokenize(c["text"]) for c in chunks]
        self.bm25 = BM25Okapi(corpus) if corpus else None

    def search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        if not self.bm25 or not self.chunks:
            return []
        scores = self.bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self.chunks, scores), key=lambda x: x[1], reverse=True)[:top_k]
        return [{**c, "score": float(s)} for c, s in ranked if s > 0]
