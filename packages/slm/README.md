# slm

Core package for the Agent Hub local SLM stack.

## Modules

| Module | Role |
|--------|------|
| `slm.config` | Environment-driven settings |
| `slm.logging` | Structured logging + trace context |
| `slm.protocol` | Canonical agent step schema |
| `slm.prompts` | Prompt registry: builtin system prompts + file overrides |
| `slm.models` | Model abstraction (Ollama / Qwen) |
| `slm.output` | JSON structured output parsing |
| `slm.context` | Read-only repo/git workspace snapshots |
| `slm.memory` | SQLite conversation persistence (`SessionStore`) |
| `slm.tools` | Read-only tool registry (`read_file`, `list_dir`, `grep_text`, `git_status`, `git_diff_staged`) |
| `slm.safety` | Kill switch (`SLM_KILL_SWITCH`) + git policy (allowlists, confirmation gates, secret blocking) |
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

## Prompt management (`slm prompts`)

System prompts are resolved through a registry. Builtins (`agent.default`,
`planner.default`) can be overridden — or new variants added — by dropping
`<key>.md` files into `.agent-hub/prompts/`:

```bash
slm prompts list
slm prompts show agent.default

mkdir -p .agent-hub/prompts
echo "Be extremely brief." > .agent-hub/prompts/agent.concise.md
slm agent "summarize repo" --prompt-key agent.concise
slm plan "ship feature X" --prompt-key planner.default
```

## Conversation persistence (`slm chat --session`)

`slm chat` is single-turn by default. With `--session NAME`, prior turns are
loaded as context and the new exchange is persisted to
`.agent-hub/sessions.db`:

```bash
slm chat "My project is called Agent Hub" --session demo
slm chat "What is my project called?" --session demo   # remembers

slm sessions list
slm sessions show demo
slm sessions show demo --json
```
