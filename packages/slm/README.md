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
| `slm.tools` | Read-only tool registry (`read_file`, `list_dir`, `grep_text`, `git_status`, `git_diff_staged`) |
| `slm.safety` | Kill switch for autonomous loops (`SLM_KILL_SWITCH`) |
| `slm.graph` | LangGraph planner + execute/verify loop + Agent Hub agent path |
| `slm.cli` | Typer CLI (`chat`, `agent`, `plan`, …) |

## Tool execution (`slm agent --execute`)

`slm agent` is plan-only by default. With `--execute`, the graph runs
**plan → execute → verify**:

1. **plan** — the model returns an `AgentStep`; executable actions go in `tool`
2. **execute** — the runtime runs the requested tool from the read-only registry
3. **verify** — `verification.status` is set to `pass`/`fail`; raw results are
   returned in `tool_output` (separate from the model's `output` summary)

All tools are workspace-scoped (path escapes are rejected) and read-only.
Write operations (file edits, `git commit`) are deliberately excluded until
the git/shell safety policy lands (issue #14).
