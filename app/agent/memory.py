"""Short-term, in-process conversation memory, keyed by session id.

Stores the last N (query, answer) turns and formats them into a short
context block the generation prompt can reference for follow-up questions
("what about the second one?"). In-process dict for the MVP; swap for
Redis/a DB row per session for a multi-instance deployment.
"""
from __future__ import annotations

from collections import deque
from typing import Deque, Dict, List, Tuple

from app.config import settings

_sessions: Dict[str, Deque[Tuple[str, str]]] = {}


def get_history(session_id: str) -> List[Tuple[str, str]]:
    return list(_sessions.get(session_id, deque()))


def add_turn(session_id: str, query: str, answer: str):
    if session_id not in _sessions:
        _sessions[session_id] = deque(maxlen=settings.memory_max_turns)
    _sessions[session_id].append((query, answer))


def format_history(session_id: str) -> str:
    history = get_history(session_id)
    if not history:
        return ""
    lines = []
    for q, a in history:
        lines.append(f"Previous question: {q}\nPrevious answer: {a[:300]}")
    return "\n\n".join(lines)


def clear_session(session_id: str):
    _sessions.pop(session_id, None)
