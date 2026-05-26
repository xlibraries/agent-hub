
from slm.telemetry.setup import configure_telemetry, is_telemetry_enabled, reset_telemetry
from slm.telemetry.tracing import start_span


def _fresh_settings(monkeypatch) -> None:
    from slm.config.settings import get_settings

    get_settings.cache_clear()
    reset_telemetry()


def test_telemetry_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SLM_OTEL_ENABLED", raising=False)
    monkeypatch.setenv("SLM_OTEL_EXPORTER", "none")
    _fresh_settings(monkeypatch)
    assert is_telemetry_enabled() is False
    assert configure_telemetry() is None


def test_console_span_does_not_raise(monkeypatch) -> None:
    monkeypatch.setenv("SLM_OTEL_ENABLED", "1")
    monkeypatch.setenv("SLM_OTEL_EXPORTER", "console")
    _fresh_settings(monkeypatch)
    configure_telemetry()
    with start_span("test.span", attributes={"slm.test": True}) as span:
        span.set_attribute("slm.ok", True)
