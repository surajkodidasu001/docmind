"""LangGraph agent orchestration.

Adaptive pipeline (not a fixed linear one):
  route          -> trivial input skips retrieval entirely
  cache_check     -> near-duplicate query returns the cached answer, skipping
                      retrieval + generation entirely (cost + latency win)
  retrieve        -> hybrid dense+BM25 search, RRF fused
  contradiction_check -> flags cited sources that disagree with each other
  generate        -> citation-grounded answer, routed to a cheap or full
                      model depending on query complexity
  verify          -> claim-level citation verification -> confidence score
  decide_retry    -> low confidence retries with a widened retrieval window
"""
from __future__ import annotations

import uuid
from typing import TypedDict, List, Dict, Any, Optional

from langgraph.graph import StateGraph, END

from app.config import settings
from app.retrieval.hybrid import hybrid_retrieve
from app.retrieval.embeddings import embed_query
from app.generation.citation import generate_answer, verify_citations
from app.generation.contradiction import find_contradictions
from app.observability.tracker import QueryTrace, Timer
from app.observability.cache import get_cache
from app.agent.complexity import classify_complexity, model_for_complexity
from app.agent import memory
from app.agent.query_rewrite import contextualize_query
from app.agent.tabular_compute import detect_computation_request, run_computation, phrase_answer


class AgentState(TypedDict, total=False):
    query: str
    session_id: str
    tenant_id: str
    needs_retrieval: bool
    computation_request: Optional[Dict[str, Any]]
    chunks: List[Dict[str, Any]]
    answer: str
    verification: Dict[str, Any]
    contradictions: List[Dict[str, Any]]
    attempt: int
    final: bool
    from_cache: bool
    complexity: str
    model: str
    query_embedding: Any
    trace: QueryTrace


_GREETING_WORDS = {"hi", "hello", "hey", "thanks", "thank you", "ok", "okay"}


def route_query(state: AgentState) -> AgentState:
    q = state["query"].strip().lower()
    trace: QueryTrace = state["trace"]
    with Timer() as t:
        needs_retrieval = q not in _GREETING_WORDS
        complexity = classify_complexity(state["query"])
        model = model_for_complexity(complexity)
        computation_request = detect_computation_request(state["query"]) if needs_retrieval else None
    trace.record("route", latency_ms=t.elapsed_ms, needs_retrieval=needs_retrieval,
                 complexity=complexity, model=model, is_computation=computation_request is not None)
    state["needs_retrieval"] = needs_retrieval
    state["complexity"] = complexity
    state["model"] = model
    state["computation_request"] = computation_request
    return state


def compute(state: AgentState) -> AgentState:
    """Deterministic pandas-based answer for tabular aggregation questions —
    no LLM call, no retrieval, no citation-verification needed since the
    number comes directly from the data rather than from generated text."""
    trace: QueryTrace = state["trace"]
    with Timer() as t:
        result = run_computation(state["computation_request"])
        answer = phrase_answer(result)
    trace.record("compute", latency_ms=t.elapsed_ms, **{k: v for k, v in result.items() if k != "value"})
    state["answer"] = answer
    state["verification"] = {"confidence": 1.0 if "error" not in result else 0.0, "flagged": []}
    state["contradictions"] = []
    state["chunks"] = [{"source": state["computation_request"]["table"], "location": "computed (pandas)",
                         "text": answer}] if "error" not in result else []
    state["final"] = True
    return state


def cache_check(state: AgentState) -> AgentState:
    trace: QueryTrace = state["trace"]
    if not settings.cache_enabled:
        state["from_cache"] = False
        return state

    with Timer() as t:
        query_vec = embed_query(state["query"])
        state["query_embedding"] = query_vec
        hit = get_cache(state.get("tenant_id", "default")).lookup(query_vec)
    trace.record("cache_check", latency_ms=t.elapsed_ms, hit=hit is not None)

    if hit is not None:
        state["answer"] = hit.response["answer"] + "\n\n_(served from semantic cache)_"
        state["verification"] = {"confidence": hit.response["confidence"], "flagged": []}
        state["chunks"] = []
        state["contradictions"] = []
        state["final"] = True
        state["from_cache"] = True
    else:
        state["from_cache"] = False
    return state


def retrieve(state: AgentState) -> AgentState:
    trace: QueryTrace = state["trace"]
    attempt = state.get("attempt", 0)
    top_k = settings.top_k_final + (attempt * 3)  # widen the window on retry
    search_query = contextualize_query(state["query"], state.get("session_id", ""))
    with Timer() as t:
        chunks = hybrid_retrieve(search_query, top_k=top_k, tenant_id=state.get("tenant_id", "default"))
    trace.record("retrieve", latency_ms=t.elapsed_ms, retrieved=len(chunks), attempt=attempt)
    state["chunks"] = chunks
    return state


def contradiction_check(state: AgentState) -> AgentState:
    trace: QueryTrace = state["trace"]
    if not settings.contradiction_check_enabled or not state.get("chunks"):
        state["contradictions"] = []
        return state
    with Timer() as t:
        contradictions = find_contradictions(state["chunks"])
    trace.record("contradiction_check", latency_ms=t.elapsed_ms, found=len(contradictions))
    state["contradictions"] = contradictions
    return state


def generate(state: AgentState) -> AgentState:
    trace: QueryTrace = state["trace"]
    if not state.get("needs_retrieval"):
        state["answer"] = "Hi! Ask me anything about the documents you've uploaded."
        state["verification"] = {"confidence": 1.0, "flagged": []}
        state["contradictions"] = []
        state["final"] = True
        return state

    if not state["chunks"]:
        state["answer"] = "I don't have enough indexed content to answer that. Try uploading a relevant document."
        state["verification"] = {"confidence": 0.0, "flagged": []}
        state["final"] = True
        return state

    history = memory.format_history(state.get("session_id", "")) if state.get("session_id") else ""
    model = state.get("model", settings.llm_model)

    with Timer() as t:
        result = generate_answer(state["query"], state["chunks"], model=model, history=history)
    trace.record(
        "generate", input_tokens=result["input_tokens"], output_tokens=result["output_tokens"],
        latency_ms=t.elapsed_ms, model=model,
    )
    state["answer"] = result["text"]
    return state


def verify(state: AgentState) -> AgentState:
    if state.get("final"):
        return state
    trace: QueryTrace = state["trace"]
    with Timer() as t:
        verification = verify_citations(state["answer"], state["chunks"])
    trace.record("verify", latency_ms=t.elapsed_ms, confidence=verification["confidence"])
    state["verification"] = verification
    return state


def decide_retry(state: AgentState) -> str:
    if state.get("final"):
        return "done"
    confidence = state["verification"]["confidence"]
    attempt = state.get("attempt", 0)
    if confidence < settings.confidence_threshold and attempt < settings.max_retries:
        state["attempt"] = attempt + 1
        return "retry"
    if confidence < settings.confidence_threshold:
        state["answer"] += ("\n\n_Note: confidence in this answer is low after "
                             f"{attempt + 1} attempts — treat with caution and consider "
                             "uploading more source material._")
    return "done"


def route_after_cache(state: AgentState) -> str:
    return "done" if state.get("from_cache") else "retrieve"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("route", route_query)
    graph.add_node("compute", compute)
    graph.add_node("cache_check", cache_check)
    graph.add_node("retrieve", retrieve)
    graph.add_node("contradiction_check", contradiction_check)
    graph.add_node("generate", generate)
    graph.add_node("verify", verify)

    graph.set_entry_point("route")

    def route_from_start(s: AgentState) -> str:
        if s.get("computation_request"):
            return "compute"
        return "cache_check" if s["needs_retrieval"] else "generate"

    graph.add_conditional_edges(
        "route", route_from_start,
        {"compute": "compute", "cache_check": "cache_check", "generate": "generate"},
    )
    graph.add_edge("compute", END)
    graph.add_conditional_edges(
        "cache_check", route_after_cache, {"retrieve": "retrieve", "done": END},
    )
    graph.add_edge("retrieve", "contradiction_check")
    graph.add_edge("contradiction_check", "generate")
    graph.add_edge("generate", "verify")
    graph.add_conditional_edges(
        "verify", decide_retry, {"retry": "retrieve", "done": END},
    )
    return graph.compile()


_compiled = None


def run_agent(query: str, session_id: Optional[str] = None, tenant_id: str = "default") -> Dict[str, Any]:
    global _compiled
    if _compiled is None:
        _compiled = build_graph()

    session_id = session_id or "default"
    trace = QueryTrace()
    state: AgentState = {"query": query, "session_id": session_id, "tenant_id": tenant_id, "attempt": 0, "trace": trace}
    result = _compiled.invoke(state)

    response = {
        "answer": result["answer"],
        "confidence": result["verification"]["confidence"],
        "flagged_claims": result["verification"].get("flagged", []),
        "contradictions": result.get("contradictions", []),
        "from_cache": result.get("from_cache", False),
        "complexity": result.get("complexity"),
        "model_used": result.get("model"),
        "sources": [
            {"source": c["source"], "location": c["location"]}
            for c in result.get("chunks", [])
        ],
        "trace": trace.summary(),
    }

    # populate the semantic cache (skip if this answer *was* a cache hit, or
    # if there's nothing worth caching, e.g. the greeting bypass)
    if settings.cache_enabled and result.get("needs_retrieval") and not result.get("from_cache"):
        query_vec = result.get("query_embedding")
        if query_vec is not None:
            get_cache(tenant_id).store(query, query_vec, {"answer": result["answer"], "confidence": response["confidence"]})

    memory.add_turn(session_id, query, response["answer"])

    from app.observability.otel import export_trace
    export_trace(trace, query)

    return response


def stream_agent_answer(query: str, session_id: Optional[str] = None, tenant_id: str = "default"):
    """Simplified streaming variant of run_agent for the SSE endpoint.

    Streams the generation stage token-by-token. Retry-on-low-confidence
    isn't compatible with an already-streamed response (you can't un-send
    tokens), so this path runs retrieval once, streams the answer, then
    verifies afterward and reports confidence + flags as a final event
    rather than looping. Use the non-streaming /query endpoint when you
    need the full adaptive-retry behavior.
    """
    from app.generation.llm import stream_llm
    from app.generation.citation import build_context_block, SYSTEM_PROMPT

    session_id = session_id or "default"
    trace = QueryTrace()
    q = query.strip().lower()

    with Timer() as t:
        needs_retrieval = q not in _GREETING_WORDS
        complexity = classify_complexity(query)
        model = model_for_complexity(complexity)
    trace.record("route", latency_ms=t.elapsed_ms, needs_retrieval=needs_retrieval, complexity=complexity)

    if not needs_retrieval:
        yield {"type": "delta", "text": "Hi! Ask me anything about the documents you've uploaded."}
        yield {"type": "final", "confidence": 1.0, "flagged_claims": [], "sources": [],
               "contradictions": [], "trace": trace.summary()}
        return

    search_query = contextualize_query(query, session_id or "")
    with Timer() as t:
        chunks = hybrid_retrieve(search_query, top_k=settings.top_k_final, tenant_id=tenant_id)
    trace.record("retrieve", latency_ms=t.elapsed_ms, retrieved=len(chunks))

    if not chunks:
        yield {"type": "delta", "text": "I don't have enough indexed content to answer that."}
        yield {"type": "final", "confidence": 0.0, "flagged_claims": [], "sources": [],
               "contradictions": [], "trace": trace.summary()}
        return

    contradictions = find_contradictions(chunks) if settings.contradiction_check_enabled else []

    history = memory.format_history(session_id)
    context = build_context_block(chunks)
    history_block = f"Conversation so far:\n{history}\n\n" if history else ""
    user_prompt = f"{history_block}Context chunks:\n\n{context}\n\nQuestion: {search_query}\n\nAnswer using inline citation markers with real chunk numbers."

    full_text = ""
    final_event = None
    with Timer() as t:
        for event in stream_llm(SYSTEM_PROMPT, user_prompt, max_tokens=800, model=model):
            if event["type"] == "delta":
                full_text += event["text"]
                yield event
            else:
                final_event = event
    trace.record("generate", input_tokens=final_event["input_tokens"],
                 output_tokens=final_event["output_tokens"], latency_ms=t.elapsed_ms, model=model)

    verification = verify_citations(full_text, chunks)
    trace.record("verify", confidence=verification["confidence"])
    memory.add_turn(session_id, query, full_text)

    yield {
        "type": "final",
        "confidence": verification["confidence"],
        "flagged_claims": verification.get("flagged", []),
        "contradictions": contradictions,
        "sources": [{"source": c["source"], "location": c["location"]} for c in chunks],
        "trace": trace.summary(),
    }
