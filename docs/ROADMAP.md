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

| Issue | Topic |
|-------|--------|
| [#12](https://github.com/xlibraries/agent-hub/issues/12) | Repo context + `slm agent` |
| [#13](https://github.com/xlibraries/agent-hub/issues/13) | Tool executor loop |
| [#14](https://github.com/xlibraries/agent-hub/issues/14) | Git & shell safety |

**Current focus:** Phase 0–1 — infrastructure, `slm` CLI, `AgentStep` protocol, repo context via `slm agent`.

**Principles:** reliable before autonomous · observable before complex · benchmarked before optimized · modular before generalized.
