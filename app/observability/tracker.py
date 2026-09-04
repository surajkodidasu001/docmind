"""Per-query cost / token / latency tracking (the 'sustainability' angle).

Anthropic's published per-model $/token rates would normally be pulled from
a pricing table; for the MVP we use a small static table you can update.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any

# USD per 1K tokens, (input, output) -- update to current published rates as needed
_PRICING = {
    "claude-sonnet-4-6": (0.003, 0.015),
    "default": (0.003, 0.015),
}


@dataclass
class StageEvent:
    stage: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryTrace:
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    stages: List[StageEvent] = field(default_factory=list)
    _t0: float = field(default_factory=time.perf_counter)

    def record(self, stage: str, input_tokens: int = 0, output_tokens: int = 0,
               latency_ms: float = 0.0, model: str = "default", **meta):
        rate_in, rate_out = _PRICING.get(model, _PRICING["default"])
        cost = (input_tokens / 1000) * rate_in + (output_tokens / 1000) * rate_out
        self.stages.append(StageEvent(
            stage=stage, input_tokens=input_tokens, output_tokens=output_tokens,
            latency_ms=latency_ms, cost_usd=cost, meta=meta,
        ))

    def summary(self) -> Dict[str, Any]:
        total_cost = sum(s.cost_usd for s in self.stages)
        total_tokens = sum(s.input_tokens + s.output_tokens for s in self.stages)
        total_latency = sum(s.latency_ms for s in self.stages)
        return {
            "trace_id": self.trace_id,
            "total_cost_usd": round(total_cost, 6),
            "total_tokens": total_tokens,
            "total_latency_ms": round(total_latency, 1),
            "stages": [
                {
                    "stage": s.stage,
                    "tokens": s.input_tokens + s.output_tokens,
                    "cost_usd": round(s.cost_usd, 6),
                    "latency_ms": round(s.latency_ms, 1),
                    **s.meta,
                }
                for s in self.stages
            ],
        }


class Timer:
    """Context manager returning elapsed ms."""
    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
