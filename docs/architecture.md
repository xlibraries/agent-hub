# Agent Hub Architecture

Agent Hub (`agent-hub` repo, `slm` package) is a modular local-first agent stack. Naming: **Agent Hub** is the product; **`slm`** is the installable core library and CLI entrypoint (`uv run slm …`).

## Control flow

```text
User Input
    ↓
Planner (LangGraph)
    ↓
Task Graph / Orchestrator
    ↓
Tool Router          ← Phase 2
    ↓
Executor Sandbox
    ↓
Verifier / Critic
    ↓
Memory Write
    ↓
Persistent Knowledge Layer
```

**Today:** `slm agent` runs planner + read-only git context. Tool execution and verifier nodes are Phase 2+.

## CLI surface

| Command | Repo context | Tools | Output |
|---------|--------------|-------|--------|
| `slm chat` | No | No | Plain text |
| `slm plan` | No | No | `AgentStep` JSON |
| `slm agent` | Yes (git snapshot) | No (plan only) | `AgentStep` JSON |

See [GOLDEN_RULES.md](GOLDEN_RULES.md) for when to use each command.

## Repository layout

| Path | Purpose |
|------|---------|
| `packages/slm/` | Core: models, CLI, protocol, context, graph, safety |
| `benchmarks/` | Latency and correctness harnesses |
| `packages/slm/tests/` | Unit tests |
| `docker/` | Reproducible dev/runtime images |
| `docs/` | Roadmap, architecture, golden rules |

## Canonical agent step

Every orchestration step serializes to `slm.protocol.AgentStep` (`packages/slm/src/slm/protocol/schema.py`).

## Phase status

| Phase | Status |
|-------|--------|
| 0 — Environment | Complete (see [observability.md](observability.md)) |
| 1 — Local SLM core | In progress (`chat`, `plan`, `agent`, protocol, kill switch) |
| 2 — Tools | Not started |
| 3+ | Not started |
