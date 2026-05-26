from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

from slm.telemetry.setup import configure_telemetry


def get_tracer(name: str = "slm") -> trace.Tracer:
    configure_telemetry()
    return trace.get_tracer(name)


@contextmanager
def start_span(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
    tracer: str = "slm",
) -> Iterator[Span]:
    """Start a span; uses the no-op tracer when telemetry is disabled."""
    configure_telemetry()
    with get_tracer(tracer).start_as_current_span(name) as active:
        if attributes:
            for key, value in attributes.items():
                if value is not None:
                    active.set_attribute(key, _attr_value(value))
        try:
            yield active
        except Exception as exc:
            active.set_status(Status(StatusCode.ERROR, str(exc)))
            active.record_exception(exc)
            raise


def _attr_value(value: Any) -> str | int | float | bool:
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
