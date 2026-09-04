"""Query complexity classification for model routing.

Cheap heuristic for the MVP: short, single-fact-lookup-shaped queries route
to the small/cheap model; anything requiring synthesis, comparison, or
multi-step reasoning routes to the full model. A learned classifier or a
one-shot LLM call could replace this heuristic later, but a heuristic keeps
the routing decision itself free (no extra API call to decide which model
to call).
"""
from __future__ import annotations

from app.config import settings

_COMPLEXITY_MARKERS = (
    "why", "how", "compare", "difference", "versus", " vs ", "analyze",
    "summarize", "summarise", "explain", "relationship", "trend", "evaluate",
    "pros and cons", "recommend", "strategy",
)


def classify_complexity(query: str) -> str:
    """Returns 'simple' or 'complex'."""
    q = query.lower().strip()
    word_count = len(q.split())
    has_marker = any(marker in q for marker in _COMPLEXITY_MARKERS)
    has_multiple_clauses = q.count(" and ") + q.count(";") >= 1

    if has_marker or has_multiple_clauses or word_count > settings.simple_query_max_words:
        return "complex"
    return "simple"


def model_for_complexity(complexity: str) -> str:
    return settings.llm_model if complexity == "complex" else settings.llm_model_small
