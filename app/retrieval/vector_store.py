"""Thin wrapper around Qdrant (in-memory by default, easy to swap for a server)."""
from __future__ import annotations

from typing import List, Dict, Any
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.config import settings
from app.ingestion.chunker import Chunk
from app.retrieval.embeddings import embed_texts


class VectorStore:
    def __init__(self, collection_name: str | None = None):
        self.client = QdrantClient(location=settings.qdrant_location)
        self.collection = collection_name or settings.qdrant_collection
        self._ensure_collection()

    def _ensure_collection(self):
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection not in existing:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=qm.VectorParams(size=384, distance=qm.Distance.COSINE),
            )

    def upsert_chunks(self, chunks: List[Chunk]):
        if not chunks:
            return
        vectors = embed_texts([c.text for c in chunks])
        points = [
            qm.PointStruct(
                id=c.id,
                vector=vectors[i].tolist(),
                payload={
                    "text": c.text,
                    "source": c.source,
                    "location": c.location,
                    "chunk_index": c.chunk_index,
                },
            )
            for i, c in enumerate(chunks)
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def dense_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        from app.retrieval.embeddings import embed_query
        vec = embed_query(query)
        hits = self.client.search(
            collection_name=self.collection,
            query_vector=vec.tolist(),
            limit=top_k,
        )
        return [
            {"id": h.id, "score": h.score, **h.payload}
            for h in hits
        ]

    def all_chunks(self) -> List[Dict[str, Any]]:
        """Used to (re)build the BM25 index. Fine for MVP scale; paginate for prod."""
        points, _ = self.client.scroll(collection_name=self.collection, limit=10000, with_payload=True)
        return [{"id": p.id, **p.payload} for p in points]

    def delete_by_source(self, source: str) -> int:
        """Incremental deletion: remove all chunks belonging to one ingested
        file, so re-uploading an updated version doesn't require a full
        reset. Returns the number of points matched for deletion (Qdrant's
        delete-by-filter doesn't report an exact count synchronously, so
        this counts via a pre-delete scroll)."""
        matches, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=qm.Filter(must=[qm.FieldCondition(key="source", match=qm.MatchValue(value=source))]),
            limit=10000,
        )
        count = len(matches)
        if count:
            self.client.delete(
                collection_name=self.collection,
                points_selector=qm.FilterSelector(
                    filter=qm.Filter(must=[qm.FieldCondition(key="source", match=qm.MatchValue(value=source))])
                ),
            )
        return count

    def reset(self):
        self.client.delete_collection(self.collection)
        self._ensure_collection()


_stores: Dict[str, VectorStore] = {}


def get_store(tenant_id: str = "default") -> VectorStore:
    """Returns a tenant-scoped VectorStore, creating it on first use. Each
    tenant gets its own Qdrant collection (see app.api.auth.collection_name_for_tenant)
    so one tenant's documents can never be retrieved by another's queries."""
    if tenant_id not in _stores:
        from app.api.auth import collection_name_for_tenant
        _stores[tenant_id] = VectorStore(collection_name=collection_name_for_tenant(tenant_id))
    return _stores[tenant_id]
