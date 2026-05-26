from __future__ import annotations

import os
from typing import Literal

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SpanExporter

from slm.config.settings import get_settings

ExporterKind = Literal["none", "console", "otlp"]

_configured = False


def _exporter_kind() -> ExporterKind:
    settings = get_settings()
    raw = (
        os.environ.get("SLM_OTEL_EXPORTER")
        or os.environ.get("OTEL_TRACES_EXPORTER")
        or settings.otel_exporter
        or "none"
    ).strip().lower()
    if raw in {"none", "off", "false", "0"}:
        return "none"
    if raw in {"console", "stdout"}:
        return "console"
    if raw in {"otlp", "otlp_http", "http"}:
        return "otlp"
    return "none"


def is_telemetry_enabled() -> bool:
    settings = get_settings()
    if settings.otel_enabled is not None:
        return settings.otel_enabled
    env = os.environ.get("SLM_OTEL_ENABLED", "").strip().lower()
    if env in {"0", "false", "no", "off"}:
        return False
    if env in {"1", "true", "yes", "on"}:
        return True
    return _exporter_kind() != "none"


def _service_name() -> str:
    return (
        os.environ.get("OTEL_SERVICE_NAME")
        or get_settings().otel_service_name
        or "agent-hub-slm"
    )


def _build_exporter(kind: ExporterKind) -> SpanExporter | None:
    if kind == "none":
        return None
    if kind == "console":
        return ConsoleSpanExporter()
    if kind == "otlp":
        endpoint = os.environ.get(
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
            os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318/v1/traces"),
        )
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        return OTLPSpanExporter(endpoint=endpoint)
    return None


def reset_telemetry() -> None:
    """Reset provider state (tests only)."""
    global _configured
    _configured = False


def configure_telemetry() -> TracerProvider | None:
    """Initialize OpenTelemetry tracing (idempotent)."""
    global _configured
    if _configured:
        provider = trace.get_tracer_provider()
        return provider if isinstance(provider, TracerProvider) else None

    if not is_telemetry_enabled():
        _configured = True
        return None

    kind = _exporter_kind()
    exporter = _build_exporter(kind)
    resource = Resource.create(
        {
            "service.name": _service_name(),
            "service.version": os.environ.get("SLM_VERSION", "0.1.0"),
        }
    )
    provider = TracerProvider(resource=resource)
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _configured = True
    return provider
