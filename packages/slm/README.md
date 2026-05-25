# slm

Core package for the Agent Hub local SLM stack.

## Modules

| Module | Role |
|--------|------|
| `slm.config` | Environment-driven settings |
| `slm.logging` | Structured logging + trace context |
| `slm.protocol` | Canonical agent step schema |
| `slm.models` | Model abstraction (Ollama / Qwen) |
| `slm.output` | JSON structured output parsing |
| `slm.context` | Read-only repo/git workspace snapshots |
| `slm.graph` | LangGraph planner + Agent Hub agent path |
| `slm.cli` | Typer CLI (`chat`, `agent`, `plan`, …) |
