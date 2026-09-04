from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.ingestion.loader import load_document, SUPPORTED_EXTENSIONS
from app.ingestion.chunker import chunk_segments
from app.retrieval.vector_store import get_store
from app.agent.graph import run_agent, stream_agent_answer
from app.agent import memory
from app.observability.cache import get_cache
from app.api.auth import get_tenant_id

router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    session_id: str | None = None


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/supported-formats")
def supported_formats():
    return {"formats": sorted(SUPPORTED_EXTENSIONS)}


@router.post("/ingest")
async def ingest(file: UploadFile = File(...), vision_fallback: bool = False,
                  tenant_id: str = Depends(get_tenant_id)):
    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported format {ext}. Supported: {sorted(SUPPORTED_EXTENSIONS)}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        segments = load_document(tmp_path, vision_fallback=vision_fallback)
        for s in segments:
            s.source = file.filename
        chunks = chunk_segments(segments)
        store = get_store(tenant_id)
        store.upsert_chunks(chunks)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {"filename": file.filename, "chunks_indexed": len(chunks), "tenant_id": tenant_id}


@router.delete("/documents/{filename}")
def delete_document(filename: str, tenant_id: str = Depends(get_tenant_id)):
    """Incremental deletion: removes only this file's chunks, not the whole index."""
    count = get_store(tenant_id).delete_by_source(filename)
    from app.retrieval.tabular_store import delete_table
    delete_table(filename)  # no-op for non-CSV files. NOTE: tabular_store and
    # conversation memory are not yet tenant-namespaced (see ARCHITECTURE.md) —
    # only the vector index and semantic cache are isolated per tenant today.
    if count == 0:
        raise HTTPException(404, f"No indexed chunks found for '{filename}'")
    return {"filename": filename, "chunks_deleted": count}


@router.post("/query")
async def query(req: QueryRequest, tenant_id: str = Depends(get_tenant_id)):
    if not req.query.strip():
        raise HTTPException(400, "query must not be empty")
    return run_agent(req.query, session_id=req.session_id, tenant_id=tenant_id)


@router.post("/query/stream")
async def query_stream(req: QueryRequest, tenant_id: str = Depends(get_tenant_id)):
    """Server-Sent Events endpoint: streams answer tokens as they're
    generated, then a final event with confidence/sources/trace. Does not
    support the adaptive low-confidence retry loop (see stream_agent_answer
    docstring) — use POST /query for that.
    """
    if not req.query.strip():
        raise HTTPException(400, "query must not be empty")

    def event_stream():
        for event in stream_agent_answer(req.query, session_id=req.session_id, tenant_id=tenant_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/session/{session_id}/clear")
def clear_session(session_id: str):
    memory.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}


@router.get("/cache/stats")
def cache_stats(tenant_id: str = Depends(get_tenant_id)):
    return get_cache(tenant_id).stats()


@router.post("/cache/clear")
def cache_clear(tenant_id: str = Depends(get_tenant_id)):
    get_cache(tenant_id).clear()
    return {"status": "cleared"}


@router.post("/reset")
def reset(tenant_id: str = Depends(get_tenant_id)):
    get_store(tenant_id).reset()
    get_cache(tenant_id).clear()
    from app.retrieval.tabular_store import clear as clear_tables
    clear_tables()
    return {"status": "reset"}


@router.get("/tables")
def list_tables_endpoint():
    """Lists ingested CSVs and their columns — useful for discovering what
    aggregation questions the compute path can answer."""
    from app.retrieval.tabular_store import list_tables
    return {"tables": list_tables()}
