"""Tests incremental deletion against the in-memory Qdrant store directly,
bypassing the real embedding model (which needs network access) by inserting
synthetic vectors through the qdrant client the same way upsert_chunks does.
"""
import uuid

import numpy as np
from qdrant_client.http import models as qm

from app.retrieval.vector_store import VectorStore


def _seed_fake_points(store: VectorStore, source: str, count: int):
    points = [
        qm.PointStruct(
            id=str(uuid.uuid4()),
            vector=np.random.rand(384).tolist(),
            payload={"text": f"chunk {i} of {source}", "source": source, "location": f"page {i}", "chunk_index": i},
        )
        for i in range(count)
    ]
    store.client.upsert(collection_name=store.collection, points=points)


def test_delete_by_source_removes_only_matching_chunks():
    store = VectorStore()
    _seed_fake_points(store, "doc_a.pdf", 3)
    _seed_fake_points(store, "doc_b.pdf", 2)

    all_chunks = store.all_chunks()
    assert len(all_chunks) == 5

    deleted = store.delete_by_source("doc_a.pdf")
    assert deleted == 3

    remaining = store.all_chunks()
    assert len(remaining) == 2
    assert all(c["source"] == "doc_b.pdf" for c in remaining)


def test_delete_by_source_nonexistent_returns_zero():
    store = VectorStore()
    _seed_fake_points(store, "doc_c.pdf", 1)
    assert store.delete_by_source("does_not_exist.pdf") == 0
