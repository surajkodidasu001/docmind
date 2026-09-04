from app.agent.graph import route_query, decide_retry
from app.observability.tracker import QueryTrace


def test_route_skips_retrieval_for_greeting():
    state = {"query": "hi", "trace": QueryTrace()}
    result = route_query(state)
    assert result["needs_retrieval"] is False


def test_route_uses_retrieval_for_real_question():
    state = {"query": "What does the Q3 report say about revenue growth?", "trace": QueryTrace()}
    result = route_query(state)
    assert result["needs_retrieval"] is True


def test_decide_retry_triggers_on_low_confidence():
    state = {"verification": {"confidence": 0.1}, "attempt": 0, "answer": "..."}
    decision = decide_retry(state)
    assert decision == "retry"
    assert state["attempt"] == 1


def test_decide_retry_stops_after_max_attempts():
    state = {"verification": {"confidence": 0.1}, "attempt": 5, "answer": "..."}
    decision = decide_retry(state)
    assert decision == "done"
