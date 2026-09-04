# DocMind — Agentic Document Intelligence Platform

A citation-grounded, cost-aware, adaptively-orchestrated RAG system. **All 15 upgrade
features from the original project scope now have real code**, including a full
React frontend. See `ARCHITECTURE.md` for exactly which pieces were verified
end-to-end in this sandbox vs. which are code-complete + logic-tested but waiting on
a live external system (a real Ollama server, a Kubernetes cluster, etc.) for final
verification.

## What's implemented

| Area | What it does |
|---|---|
| **Ingestion** | 8 formats: PDF, DOCX, PPTX, TXT, MD, CSV, HTML, JSON, plus an opt-in vision fallback for scanned/image-only PDF pages |
| **Chunking** | Word-based sliding window with configurable overlap |
| **Hybrid retrieval** | Dense (Qdrant) + BM25 sparse, fused via Reciprocal Rank Fusion, tenant-scoped |
| **Agentic orchestration** | LangGraph state machine: route → compute (tabular) or cache_check → retrieve → contradiction_check → generate → verify → retry |
| **Tabular compute** | CSV aggregation questions ("what's the total revenue?") answered with real pandas, zero LLM cost |
| **Semantic caching** | Tenant-scoped, cosine-similarity near-duplicate detection |
| **Model routing** | Complexity classifier routes simple lookups to a cheap model, complex ones to the full model |
| **Local model fallback** | Falls back to a local Ollama server if Anthropic fails after retries |
| **Streaming** | SSE endpoint + streaming Streamlit UI |
| **Conversation memory** | Per-session short-term history |
| **Citation grounding + verification** | Claim-level, flags specific unsupported sentences |
| **Contradiction detection** | Flags source pairs with conflicting numbers on the same topic |
| **Multi-tenancy** | API-key based, tenant-isolated vector index + cache |
| **Incremental indexing** | Delete a single document's chunks without a full reindex |
| **Observability** | Per-query cost/token/latency trace, plus real OpenTelemetry span export |
| **Eval harness** | RAGAS-style faithfulness/relevance/precision scoring |
| **CI/CD** | GitHub Actions running all 61 tests on every push/PR |
| **Load & chaos testing** | Locust load test (verified against the live server in this sandbox) + 5 fault-injection tests |
| **Deployment** | Docker Compose for local/single-node; Kubernetes + KEDA manifests for autoscaled deployment |
| **UI** | Two options: Streamlit (fast, Python-only) and a real React app (`frontend/`) with clickable citation highlighting and true SSE streaming |
| **Tests** | **61 Python tests + 16 frontend tests**, all passing, no network/API key required |

## Quickstart (local, no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY

# terminal 1
uvicorn app.main:app --reload

# terminal 2
streamlit run streamlit_app.py
```

Open http://localhost:8501, upload a doc, ask a question.

## Quickstart (Docker)

```bash
cp .env.example .env   # set ANTHROPIC_API_KEY
# for docker-compose, point at the qdrant service instead of :memory:
echo "QDRANT_LOCATION=http://qdrant:6333" >> .env
docker compose up --build
```

API: http://localhost:8000/docs · UI: http://localhost:8501

## Running tests

```bash
pytest tests/ -v
```
All 61 tests are self-contained (no API key or network needed) — including chaos/
fault-injection tests (`test_chaos.py`), multi-tenancy isolation (`test_multitenancy.py`),
real OpenTelemetry span export (`test_otel.py`), and a genuinely-generated synthetic
scanned PDF proving the vision-fallback detection actually works (`test_vision_pdf.py`).

## Running the load test

```bash
uvicorn app.main:app &
pip install -r requirements-dev.txt
locust -f loadtest/locustfile.py --host http://localhost:8000 --headless -u 10 -r 5 --run-time 30s
```
Or run `locust -f loadtest/locustfile.py --host http://localhost:8000` for the web UI.

## Running the eval harness

```bash
export ANTHROPIC_API_KEY=your_key
python eval/run_eval.py --ingest
```
Scores faithfulness (claim-level citation support), answer relevance (cosine
similarity to a reference answer), and context precision (fraction of retrieved
chunks actually cited) against the 4 sample questions in `eval/dataset.json`.
**Replace that dataset with your own documents + real reference answers** — the
sample set is just a smoke test, not a meaningful benchmark on its own.

## Running the React frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```
Needs the FastAPI backend running separately. See `frontend/README.md` for details
on what's been verified (build + logic tests) vs. not (actual browser rendering —
this sandbox couldn't download a browser binary to screenshot it).

## Project layout

```
app/
  ingestion/     loader.py (8 formats + vision fallback), chunker.py, vision_pdf.py
  retrieval/     embeddings.py, vector_store.py (tenant-scoped Qdrant + delete),
                 bm25_index.py, hybrid.py (RRF), tabular_store.py
  generation/    llm.py (Anthropic + Ollama fallback, streaming), citation.py,
                 contradiction.py
  agent/         graph.py (LangGraph orchestration + streaming), complexity.py,
                 memory.py, tabular_compute.py
  observability/ tracker.py, cache.py (tenant-scoped), otel.py
  api/           routes.py, auth.py (multi-tenancy)
  main.py
eval/            run_eval.py, dataset.json
loadtest/        locustfile.py
deploy/k8s/      deployment.yaml, service.yaml, scaledobject.yaml (KEDA), secret.yaml.example
frontend/        React + Vite app (see frontend/README.md)
.github/workflows/test.yml   CI: Python tests + frontend lint/test/build
streamlit_app.py
tests/           61 tests
```

## Known MVP limitations (see ARCHITECTURE.md for the fix path)

- Rerank step is a proxy (RRF ranking only) — swap in a real cross-encoder for production.
- Citation verification is lexical-overlap, not NLI/entailment — good enough to catch
  obviously unsupported claims, not airtight.
- BM25 index rebuilds from a full collection scroll on every query — fine at MVP scale,
  needs a persisted sparse index at scale.
- No auth/multi-tenancy, no persistence beyond Qdrant's own storage, no CI pipeline yet.
