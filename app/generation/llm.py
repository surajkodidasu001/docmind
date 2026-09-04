from __future__ import annotations

"""LLM wrapper: Anthropic primary, with an optional local-model fallback.

If no real Anthropic key is configured, or the Anthropic call fails after
retries, this falls back to a locally-running Ollama server (when enabled).
"""

from typing import List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential

import requests
from anthropic import Anthropic, APIError, APIConnectionError
from app.config import settings

_client: Anthropic | None = None


def _has_real_anthropic_key() -> bool:
    key = settings.anthropic_api_key
    return bool(key) and key != "your_key_here"


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


class AllProvidersFailedError(Exception):
    """Raised when both the primary (Anthropic) and fallback (Ollama, if
    enabled) providers fail to produce a response."""


def _call_anthropic(system: str, user: str, max_tokens: int, model: str | None) -> Dict[str, Any]:
    client = _get_client()
    resp = client.messages.create(
        model=model or settings.llm_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text")
    return {
        "text": text,
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "model": model or settings.llm_model,
        "provider": "anthropic",
    }


def _call_ollama(system: str, user: str, max_tokens: int) -> Dict[str, Any]:
    resp = requests.post(
        f"{settings.ollama_host}/api/chat",
        json={
            "model": settings.ollama_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"num_predict": max_tokens},
        },
        timeout=settings.ollama_timeout_seconds,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data.get("message", {}).get("content", "")
    return {
        "text": text,
        "input_tokens": data.get("prompt_eval_count", 0),
        "output_tokens": data.get("eval_count", 0),
        "model": settings.ollama_model,
        "provider": "ollama",
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8),
       reraise=True,
       retry=lambda retry_state: isinstance(
           retry_state.outcome.exception() if retry_state.outcome else None,
           (APIError, APIConnectionError),
       ))
def _call_anthropic_with_retry(system: str, user: str, max_tokens: int, model: str | None) -> Dict[str, Any]:
    return _call_anthropic(system, user, max_tokens, model)


def call_llm(system: str, user: str, max_tokens: int = 1000, model: str | None = None) -> Dict[str, Any]:
    if not _has_real_anthropic_key():
        if settings.ollama_fallback_enabled:
            return _call_ollama(system, user, max_tokens)
        raise AllProvidersFailedError(
            "No ANTHROPIC_API_KEY configured and OLLAMA_FALLBACK_ENABLED is not set to true."
        )

    try:
        return _call_anthropic_with_retry(system, user, max_tokens, model)
    except Exception as anthropic_error:
        if not settings.ollama_fallback_enabled:
            raise
        try:
            result = _call_ollama(system, user, max_tokens)
            result["fallback_reason"] = str(anthropic_error)
            return result
        except Exception as ollama_error:
            raise AllProvidersFailedError(
                f"Anthropic failed ({anthropic_error}); Ollama fallback also failed ({ollama_error})"
            ) from ollama_error


def stream_llm(system: str, user: str, max_tokens: int = 1000, model: str | None = None):
    if not _has_real_anthropic_key():
        if settings.ollama_fallback_enabled:
            result = _call_ollama(system, user, max_tokens)
            yield {"type": "delta", "text": result["text"]}
            yield {"type": "done", "input_tokens": result["input_tokens"],
                   "output_tokens": result["output_tokens"], "model": result["model"]}
            return
        raise AllProvidersFailedError(
            "No ANTHROPIC_API_KEY configured and OLLAMA_FALLBACK_ENABLED is not set to true."
        )

    client = _get_client()
    with client.messages.stream(
        model=model or settings.llm_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for text in stream.text_stream:
            yield {"type": "delta", "text": text}
        final = stream.get_final_message()
        yield {
            "type": "done",
            "input_tokens": final.usage.input_tokens,
            "output_tokens": final.usage.output_tokens,
            "model": model or settings.llm_model,
        }
