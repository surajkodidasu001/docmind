"""Verifies OTel export actually produces spans, using the real SDK with an
in-memory exporter (no external collector needed — this genuinely runs)."""
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.observability.tracker import QueryTrace
from app.observability import otel
from app.config import settings


def test_export_trace_produces_expected_spans(monkeypatch):
    monkeypatch.setattr(settings, "otel_enabled", True)

    memory_exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory_exporter))
    monkeypatch.setattr(otel, "_provider", provider)
    monkeypatch.setattr(otel, "_get_provider", lambda: provider)

    qt = QueryTrace()
    qt.record("retrieve", latency_ms=12.3, model="default")
    qt.record("generate", input_tokens=100, output_tokens=50, latency_ms=340.1, model="claude-sonnet-4-6")

    otel.export_trace(qt, "what is the refund policy?")

    spans = memory_exporter.get_finished_spans()
    names = {s.name for s in spans}
    assert "docmind.query" in names
    assert "docmind.stage.retrieve" in names
    assert "docmind.stage.generate" in names

    generate_span = next(s for s in spans if s.name == "docmind.stage.generate")
    assert generate_span.attributes["docmind.tokens"] == 150


def test_export_trace_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "otel_enabled", False)
    memory_exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory_exporter))
    monkeypatch.setattr(otel, "_get_provider", lambda: provider)

    qt = QueryTrace()
    qt.record("retrieve", latency_ms=1.0)
    otel.export_trace(qt, "test")

    assert memory_exporter.get_finished_spans() == ()
