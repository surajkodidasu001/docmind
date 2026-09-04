"""Tests the Anthropic-fails -> Ollama-fallback decision logic with both
network calls mocked out. This validates the *branching logic* (when do we
fall back, what do we do if the fallback also fails) without needing a real
Ollama server — that dependency is real and can't be faked, but the code
path that decides to use it can be verified.
"""
from unittest.mock import patch, MagicMock

import pytest

from app.generation import llm
from app import config


def test_falls_back_to_ollama_when_anthropic_fails(monkeypatch):
    monkeypatch.setattr(config.settings, "ollama_fallback_enabled", True)

    with patch.object(llm, "_call_anthropic_with_retry", side_effect=RuntimeError("anthropic down")), \
         patch.object(llm, "_call_ollama", return_value={
             "text": "fallback answer", "input_tokens": 10, "output_tokens": 5,
             "model": "llama3.2", "provider": "ollama",
         }) as mock_ollama:
        result = llm.call_llm("system", "user")

    assert result["provider"] == "ollama"
    assert result["text"] == "fallback answer"
    assert "fallback_reason" in result
    mock_ollama.assert_called_once()


def test_does_not_fall_back_when_disabled(monkeypatch):
    monkeypatch.setattr(config.settings, "ollama_fallback_enabled", False)

    with patch.object(llm, "_call_anthropic_with_retry", side_effect=RuntimeError("anthropic down")):
        with pytest.raises(RuntimeError, match="anthropic down"):
            llm.call_llm("system", "user")


def test_raises_combined_error_when_both_providers_fail(monkeypatch):
    monkeypatch.setattr(config.settings, "ollama_fallback_enabled", True)

    with patch.object(llm, "_call_anthropic_with_retry", side_effect=RuntimeError("anthropic down")), \
         patch.object(llm, "_call_ollama", side_effect=RuntimeError("ollama also down")):
        with pytest.raises(llm.AllProvidersFailedError, match="anthropic down.*ollama also down"):
            llm.call_llm("system", "user")


def test_anthropic_success_skips_fallback_entirely(monkeypatch):
    monkeypatch.setattr(config.settings, "ollama_fallback_enabled", True)

    with patch.object(llm, "_call_anthropic_with_retry", return_value={
        "text": "primary answer", "input_tokens": 10, "output_tokens": 5,
        "model": "claude-sonnet-4-6", "provider": "anthropic",
    }) as mock_anthropic, patch.object(llm, "_call_ollama") as mock_ollama:
        result = llm.call_llm("system", "user")

    assert result["provider"] == "anthropic"
    mock_ollama.assert_not_called()
