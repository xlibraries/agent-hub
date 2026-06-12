# Agent Hub Roadmap

**Repository:** [xlibraries/agent-hub](https://github.com/xlibraries/agent-hub)

Agent Hub is a local-first agentic stack built around small language models (SLMs), deterministic orchestration, and evaluation-first development. The `slm` Python package is the core library; the product identity is **Agent Hub**, not a separate “sm-agent” or generic assistant brand.

## Golden rules

See [GOLDEN_RULES.md](GOLDEN_RULES.md).

## Phases (GitHub tracking)

| Phase | Focus | Issue |
|-------|--------|-------|
| 0 | Environment & infrastructure | [#1](https://github.com/xlibraries/agent-hub/issues/1) |
| 1 | Local SLM core | [#2](https://github.com/xlibraries/agent-hub/issues/2) |
| 2 | Tool execution layer | [#3](https://github.com/xlibraries/agent-hub/issues/3) |
| 3 | Evaluation & benchmarks | [#9](https://github.com/xlibraries/agent-hub/issues/9) |
| 4 | Memory systems | [#6](https://github.com/xlibraries/agent-hub/issues/6) |
| 5 | Research & RAG | [#4](https://github.com/xlibraries/agent-hub/issues/4) |
| 6 | Browser & environment | [#5](https://github.com/xlibraries/agent-hub/issues/5) |
| 7 | Code intelligence | [#7](https://github.com/xlibraries/agent-hub/issues/7) |
| 8 | Multi-agent systems | [#8](https://github.com/xlibraries/agent-hub/issues/8) |
| 9 | Production hardening | [#11](https://github.com/xlibraries/agent-hub/issues/11) |
| — | Epic & near-term glue | [#10](https://github.com/xlibraries/agent-hub/issues/10) |

### Near-term issues

| Issue | Topic | Status |
|-------|--------|--------|
| [#12](https://github.com/xlibraries/agent-hub/issues/12) | Repo context + `slm agent` | ✅ Done |
| [#13](https://github.com/xlibraries/agent-hub/issues/13) | Tool executor loop | 🔄 v1 done (read-only, single tool) |
| [#14](https://github.com/xlibraries/agent-hub/issues/14) | Git & shell safety | 🔄 Policy module done; CLI write tools pending |

## Progress

| Phase | Status | Notes |
|-------|--------|-------|
| 0 — Environment | ✅ ~100% | uv, Docker, structlog, OTEL, experiments, CI, pytest, benchmarks |
| 1 — Local SLM core | 🔄 ~95% | Done: models, `AgentStep`, parser, CLI, repo context, kill switch, read-only tool execution, conversation persistence (`--session`), prompt registry (`slm prompts`). Left: file-editing assistant (needs #14 write gates) |
| 2 — Tool execution | 🔄 ~25% | Done: registry + 5 read-only tools, execution tracing. Left: sandbox, shell/python exec, file editing, replay, recovery |
| 3 — Evaluation | 🔄 ~10% | Latency scaffold only |
| 4–8 | ⬜ 0% | Memory, RAG, browser, code intelligence, multi-agent |
| 9 — Hardening | ⬜ 0% | |

**Current focus:** write tools behind the git policy gates ([#13](https://github.com/xlibraries/agent-hub/issues/13)/[#14](https://github.com/xlibraries/agent-hub/issues/14)) → file-editing assistant; then the eval golden path ([#9](https://github.com/xlibraries/agent-hub/issues/9)).

**Principles:** reliable before autonomous · observable before complex · benchmarked before optimized · modular before generalized.
