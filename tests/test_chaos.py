"""Chaos/fault-injection tests: simulate real failure modes (LLM API down,
vector store unavailable) and verify the system degrades the way the
architecture claims — retries, falls back, or fails clearly rather than
hanging or corrupting state. Runs fully offline via mocking, which is the
right tool for this: it tests OUR failure-handling code deterministically,
whereas load testing (loadtest/locustfile.py) needs a real deployed target
to say anything about production behavior — the two are complementary, not
redundant.
"""
from unittest.mock import patch, MagicMock

import pytest

from app.generation import llm
from app import config
from app.agent.graph import decide_retry


def test_anthropic_transient_failure_triggers_tenacity_retry():
    """The primary provider call is wrapped in @retry — verify it actually
    retries on transient errors rather than failing on the first blip."""
    call_count = {"n": 0}

    def flaky_call(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise llm.APIConnectionError(request=MagicMock())
        return {"text": "recovered", "input_tokens": 5, "output_tokens": 5,
                "model": "claude-sonnet-4-6", "provider": "anthropic"}

    with patch.object(llm, "_call_anthropic", side_effect=flaky_call):
        result = llm._call_anthropic_with_retry("sys", "user", 100, None)

    assert result["text"] == "recovered"
    assert call_count["n"] == 2  # failed once, succeeded on retry


def test_persistent_anthropic_outage_exhausts_retries_and_raises():
    with patch.object(llm, "_call_anthropic", side_effect=llm.APIConnectionError(request=MagicMock())):
        with pytest.raises(llm.APIConnectionError):
            llm._call_anthropic_with_retry("sys", "user", 100, None)


def test_full_outage_with_fallback_disabled_surfaces_clear_error(monkeypatch):
    """When both the primary provider is down AND there's no fallback
    configured, the system should fail loudly and immediately — not hang,
    not silently return an empty answer."""
    monkeypatch.setattr(config.settings, "ollama_fallback_enabled", False)
    with patch.object(llm, "_call_anthropic_with_retry", side_effect=RuntimeError("total outage")):
        with pytest.raises(RuntimeError, match="total outage"):
            llm.call_llm("sys", "user")


def test_low_confidence_under_repeated_failure_eventually_gives_up():
    """Simulates a pathological case: retrieval keeps returning low-quality
    (low-confidence) results. The retry loop must terminate at max_retries
    rather than looping forever."""
    state = {"verification": {"confidence": 0.05}, "attempt": 0, "answer": "shaky answer"}
    decisions = []
    for _ in range(config.settings.max_retries + 3):  # try well past the limit
        decision = decide_retry(state)
        decisions.append(decision)
        if decision == "done":
            break

    assert decisions[-1] == "done"
    assert decisions.count("retry") == config.settings.max_retries
    assert "low" in state["answer"].lower()  # the low-confidence warning got appended


def test_vector_store_unreachable_does_not_crash_bm25_index(monkeypatch):
    """If the vector store's scroll() call fails (e.g. Qdrant server down in
    a networked deployment), hybrid_retrieve should raise a clear exception
    rather than a confusing downstream error inside BM25 indexing."""
    from app.retrieval import hybrid

    class BrokenStore:
        def dense_search(self, *a, **k):
            raise ConnectionError("qdrant unreachable")

        def all_chunks(self):
            raise ConnectionError("qdrant unreachable")

    with patch.object(hybrid, "get_store", return_value=BrokenStore()):
        with pytest.raises(ConnectionError, match="qdrant unreachable"):
            hybrid.hybrid_retrieve("test query")
