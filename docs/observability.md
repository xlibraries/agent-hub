# Observability (Phase 0)

Agent Hub records **traces** (OpenTelemetry) and **experiments** (local SQLite). Both are inspectable without a cloud account.

## Tracing

| Variable | Default | Description |
|----------|---------|-------------|
| `SLM_OTEL_ENABLED` | off unless exporter set | Force enable/disable |
| `SLM_OTEL_EXPORTER` | `none` | `none`, `console`, or `otlp` |
| `SLM_OTEL_SERVICE_NAME` | `agent-hub-slm` | Service name on spans |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | `http://127.0.0.1:4318/v1/traces` | OTLP HTTP endpoint |

**Console exporter (local dev):**

```bash
export SLM_OTEL_ENABLED=1
export SLM_OTEL_EXPORTER=console
uv run slm chat "hello"
```

Spans: `slm.chat` → `slm.model.generate`. Logs include `trace_id` / `span_id` when a span is active.

**OTLP (Jaeger, Grafana Tempo, LangSmith-compatible collectors):**

```bash
export SLM_OTEL_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:4318/v1/traces
```

## Experiment tracking

Every `slm chat`, `slm plan`, and `slm agent` run is stored in SQLite (default: `.agent-hub/experiments.db`).

| Variable | Default |
|----------|---------|
| `SLM_EXPERIMENTS_ENABLED` | `1` |
| `SLM_EXPERIMENTS_DB_PATH` | `.agent-hub/experiments.db` |

```bash
uv run slm agent "Summarize recent git changes"
uv run slm experiments list
uv run slm experiments show <run-id-prefix>
```

Stored fields: command, model, latency, tokens, params, metrics, `trace_id`, status, error.

## Phase 0 checklist ([issue #1](https://github.com/xlibraries/agent-hub/issues/1))

- [x] Monorepo, uv, Docker, structlog, pytest, benchmarks, CI
- [x] OpenTelemetry wiring (console + OTLP)
- [x] Experiment tracking (SQLite)
