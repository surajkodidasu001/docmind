"""OpenTelemetry export for QueryTrace.

Exports each pipeline stage in a QueryTrace as a real OTel span (parented
under one span per query), with tokens/cost/latency as span attributes.
Defaults to a console exporter, which requires no external account and is
genuinely verified working in this repo's test suite. Set
OTEL_EXPORTER=otlp + OTEL_OTLP_ENDPOINT to ship to Langfuse, Jaeger,
Honeycomb, or any OTLP-compatible collector instead — that swap is a config
change, not a code change, once you have somewhere to send spans.
"""
from __future__ import annotations

from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    ConsoleSpanExporter,
)

from app.config import settings
from app.observability.tracker import QueryTrace

_provider: Optional[TracerProvider] = None


def _get_provider() -> TracerProvider:
    global _provider
    if _provider is not None:
        return _provider

    resource = Resource.create({"service.name": "docmind"})
    provider = TracerProvider(resource=resource)

    if settings.otel_exporter == "otlp":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        exporter = OTLPSpanExporter(endpoint=f"{settings.otel_otlp_endpoint}/v1/traces")
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(SimpleSpanProcessor(exporter))
    _provider = provider
    return provider


def export_trace(query_trace: QueryTrace, query: str):
    """Exports a completed QueryTrace as a parent span with one child span
    per pipeline stage. No-op if OTel export is disabled in settings."""
    if not settings.otel_enabled:
        return

    tracer = trace.get_tracer("docmind", tracer_provider=_get_provider())
    summary = query_trace.summary()

    with tracer.start_as_current_span("docmind.query") as parent:
        parent.set_attribute("docmind.trace_id", summary["trace_id"])
        parent.set_attribute("docmind.query", query[:200])  # truncate to avoid huge attrs
        parent.set_attribute("docmind.total_cost_usd", summary["total_cost_usd"])
        parent.set_attribute("docmind.total_tokens", summary["total_tokens"])
        parent.set_attribute("docmind.total_latency_ms", summary["total_latency_ms"])

        for stage in summary["stages"]:
            with tracer.start_as_current_span(f"docmind.stage.{stage['stage']}") as span:
                span.set_attribute("docmind.tokens", stage["tokens"])
                span.set_attribute("docmind.cost_usd", stage["cost_usd"])
                span.set_attribute("docmind.latency_ms", stage["latency_ms"])
                for k, v in stage.items():
                    if k not in ("stage", "tokens", "cost_usd", "latency_ms"):
                        span.set_attribute(f"docmind.{k}", str(v))
