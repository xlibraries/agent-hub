# Agent Hub

A modular, local-first agentic AI stack centered on small language models (SLMs), with deterministic orchestration, full observability, and evaluation-first development.

## Quick start

**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/), [Ollama](https://ollama.com/) (for local Qwen).

```bash
# Install dependencies
uv sync --all-packages --dev

# Pull a local model (primary target: Qwen2.5-Coder)
ollama pull qwen2.5-coder:14b

# Raw LLM chat (no repo context)
uv run slm chat "Explain what Agent Hub is building."

# Repo-aware structured step (git status + staged diff injected)
uv run slm agent "Suggest a commit message for staged changes"

# Planner-only JSON (no repo context)
uv run slm plan "Add a hello-world function to main.py"
```

### Which command?

| Command | Purpose |
|---------|---------|
| `slm chat` | Quick Q&A — **does not** see your repo or run tools |
| `slm agent` | **Agent Hub** tasks — injects git workspace context, returns `AgentStep` JSON |
| `slm plan` | Structured plan JSON without repo snapshot |

## Development

```bash
uv run pytest
uv run slm bench --help
docker compose -f docker/docker-compose.yml up -d
```

## Observability

```bash
# Local experiment log (SQLite)
uv run slm agent "Summarize staged changes"
uv run slm experiments list

# OpenTelemetry console spans
export SLM_OTEL_ENABLED=1 SLM_OTEL_EXPORTER=console
uv run slm chat "hello"
```

See [observability.md](docs/observability.md).

## Documentation

- [Roadmap](docs/ROADMAP.md)
- [Architecture](docs/architecture.md)
- [Observability](docs/observability.md)
- [Golden rules](docs/GOLDEN_RULES.md)

## Design principles

- Every capability must be measurable.
- Every tool execution must be logged.
- Every autonomous loop must have kill switches.
- Prefer deterministic orchestration over emergent multi-agent complexity.
