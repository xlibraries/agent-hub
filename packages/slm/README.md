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
| `slm.tools` | Tool registry + sandboxed `run_shell` / `python_exec` |
| `slm.safety` | Kill switch + git/shell/python policies (allowlists, human gates) |
| `slm.graph` | LangGraph planner + execute/verify loop + Agent Hub agent path |
| `slm.evals` | Golden eval suite: replayable agent tasks with deterministic scoring |
| `slm.cli` | Typer CLI (`chat`, `agent`, `plan`, …) |

## Tool execution (`slm agent --execute`)

`slm agent` is plan-only by default. With `--execute`, the graph runs an
iterative **plan → execute → verify → plan …** loop:

1. **plan** — the model returns an `AgentStep`; executable actions go in `tool`
2. **execute** — the runtime runs the requested tool from the registry
3. **verify** — `verification.status` set to `pass`/`fail`; the result is
   recorded as an observation and fed back to the model
4. the loop ends when the model stops requesting tools (final answer in
   `output`) or the step budget is reached (`--max-steps`, default 5)

All tools are workspace-scoped (path escapes are rejected). Read-only tools
are always available; **write tools require the explicit `--allow-writes`
human gate**:

| Gate | Tools |
|------|-------|
| `--execute` | read tools + read-only `run_shell` + `python_exec -m pytest/unittest/json.tool` |
| `--allow-shell` | + mutating `run_shell` + `python_exec -c` snippets (blocked patterns always denied) |
| `--allow-writes` | + `write_file`, `git_exec` (allowlisted subcommands only, secret paths always refused — see `docs/git-safety.md`) |

```bash
slm agent "read main.py and summarize it" --execute
slm agent "fix the typo in README and commit it" --allow-writes
```

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
