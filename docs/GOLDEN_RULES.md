# Agent Hub — Golden Rules

These rules apply to every phase of the project. They are non-negotiable defaults for design and implementation.

1. **Measurable** — Every capability ships with a benchmark, test, or observable metric before it is considered done.
2. **Logged** — Every tool execution and orchestration step is structured-logged; no silent side effects.
3. **Kill-switchable** — Autonomous loops respect `SLM_KILL_SWITCH` and halt immediately when engaged.
4. **Deterministic orchestration** — LangGraph owns control flow; the SLM proposes plans, the runtime executes tools.
5. **Context before claims** — Repo-aware answers require injected workspace snapshots (`slm agent`), not bare `slm chat`.
6. **No invented state** — Do not assert git status, file contents, or test results without tool-backed evidence.
7. **Safe by default** — Destructive actions (commit, push, shell, browser) require explicit policy and human approval gates.
8. **Modular before generalized** — Ship the smallest vertical slice (e.g. read-only git context) before broad frameworks.

## CLI contract

| Command | Use when |
|---------|----------|
| `slm chat` | Quick Q&A with the local model; **no** repo context or tools |
| `slm plan` | Structured `AgentStep` JSON from goal only |
| `slm agent` | **Agent Hub** path: git snapshot + structured plan for repo tasks |
| `slm bench` | Latency / reliability measurements |
