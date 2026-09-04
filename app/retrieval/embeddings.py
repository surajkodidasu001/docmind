"""Embedding model wrapper (lazy-loaded singleton)."""
from __future__ import annotations

from functools import lru_cache
from typing import List

import numpy as np

from app.config import settings


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: List[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    model = _get_model()
    return np.array(model.encode(texts, normalize_embeddings=True, show_progress_bar=False))


def embed_query(query: str) -> np.ndarray:
    return embed_texts([query])[0]
