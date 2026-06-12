from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from slm.config.settings import get_settings
from slm.experiments.store import ExperimentStore
from slm.logging.setup import trace_id
from slm.telemetry.tracing import start_span


@dataclass
class RunContext:
    run_id: str
    metrics: dict[str, Any] = field(default_factory=dict)

    def set_metrics(self, **kwargs: Any) -> None:
        self.metrics.update(kwargs)


class ExperimentTracker:
    def __init__(self, store: ExperimentStore) -> None:
        self._store = store

    @contextmanager
    def track(
        self,
        command: str,
        *,
        model: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Iterator[RunContext]:
        settings = get_settings()
        noop = RunContext(run_id="")
        if not settings.experiments_enabled:
            yield noop
            return

        run_id = self._store.start_run(
            command,
            model=model,
            params=params,
            trace_id=trace_id(),
        )
        ctx = RunContext(run_id=run_id)
        status = "ok"
        error_msg: str | None = None
        span_attrs = {
            "slm.command": command,
            "slm.run_id": run_id,
            "slm.model": model,
        }

        try:
            with start_span(f"slm.{command}", attributes=span_attrs):
                yield ctx
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            status = "error"
            error_msg = str(exc) or type(exc).__name__
            raise
        finally:
            if run_id:
                self._store.finish_run(
                    run_id,
                    status=status,
                    latency_ms=_as_float(ctx.metrics.get("latency_ms")),
                    tokens=_as_int(ctx.metrics.get("tokens")),
                    metrics=ctx.metrics,
                    error=error_msg,
                )


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


@lru_cache
def get_tracker() -> ExperimentTracker:
    settings = get_settings()
    return ExperimentTracker(ExperimentStore(settings.experiments_db_path))
