"""Heuristic conversational query rewriting for retrieval.

Follow-up messages like "are you sure?" or "explain more" carry no
searchable topic words on their own - hybrid_retrieve has nothing to match
against, so it returns near-random chunks. This module detects that case
and, retrieval-only, prepends the previous turn's actual question so
search has real content to work with. The LLM still sees the user's
original, unmodified message in the generation prompt - only the search
query gets rewritten, never what's shown in the UI or sent as "the
question" to the model.
"""
from __future__ import annotations

from app.agent import memory

_FOLLOWUP_INDICATORS = {
    "it", "that", "this", "they", "them", "those", "these",
    "sure", "really", "confirm", "certain", "again",
    "why", "how come", "explain", "more", "further", "elaborate",
    "correct", "right", "true", "accurate", "wrong",
}

_MAX_WORDS_FOR_FOLLOWUP = 8


def needs_contextualization(query: str) -> bool:
    words = query.lower().split()
    if len(words) == 0 or len(words) > _MAX_WORDS_FOR_FOLLOWUP:
        return False
    stripped = {w.strip(".,!?'\"") for w in words}
    return bool(stripped & _FOLLOWUP_INDICATORS)


def contextualize_query(query: str, session_id: str) -> str:
    if not needs_contextualization(query):
        return query

    history = memory.get_history(session_id)
    if not history:
        return query

    previous_question = history[-1][0]
    return f"{previous_question} {query}"
