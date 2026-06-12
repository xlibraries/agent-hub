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

# Multi-turn chat with persistence (SQLite-backed)
uv run slm chat "Remember: my name is X" --session intro
uv run slm chat "What is my name?" --session intro
uv run slm sessions list

# Repo-aware agent (README, tree, git status + staged/unstaged diffs)
uv run slm agent --brief "What is this repository about?"

# Commit messages — uses diffs from workspace snapshot
uv run slm agent "Write commit message(s) for uncommitted changes"

# Execute read-only tools requested by the plan (read_file, list_dir, grep_text, git_*)
uv run slm agent "read packages/slm/src/slm/cli/main.py" --execute

# Planner with workspace context
uv run slm plan --repo "Break down adding file search tool"

# Planner-only JSON (no repo context)
uv run slm plan "Add a hello-world function to main.py"
```

### Which command?

| Command | Purpose |
|---------|---------|
| `slm chat` | Quick Q&A — **does not** see your repo or run tools |
| `slm chat --session NAME` | Multi-turn chat; history persisted in `.agent-hub/sessions.db` |
| `slm sessions list/show` | Inspect persisted conversations |
| `slm agent` | **Agent Hub** — README + tree + git snapshot; use `--brief` for a short answer |
| `slm agent --execute` | Same, plus runs read-only tools from the plan (plan → execute → verify) |
| `slm plan` | Structured plan JSON; add `--repo` or `--cwd` for workspace context |

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
