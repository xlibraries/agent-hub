# Shell execution sandbox

Issue: [#3](https://github.com/xlibraries/agent-hub/issues/3) · Modules: `slm.safety.shell_policy`, `slm.tools.sandbox`

Agent Hub runs shell commands **without invoking a shell** (`subprocess` with an argv list only). Policy is enforced before every invocation.

## Gates

| CLI flag | `run_shell` capability |
|----------|------------------------|
| `--execute` | Read-only allowlist (`ls`, `cat`, `grep`, `pytest`, `uv run pytest`, …) |
| `--allow-shell` | + mutating commands (`mkdir`, `rm`, `cp`, `mv`, …) — explicit human gate |

`git` is **never** allowed via `run_shell`; use `git_status` / `git_diff_staged` / `git_exec` instead.

## Rules

| Rule | Enforcement |
|------|-------------|
| No shell metacharacters | `; \| & \` $ < >` rejected in the command string |
| Binary allowlist | Unknown binaries denied |
| Workspace confinement | `cwd=workspace_root`; `HOME` redirected to workspace |
| Secret env stripping | `AWS_*`, `*TOKEN*`, `*SECRET*`, … removed from subprocess env |
| Timeout + truncation | `SLM_SHELL_TIMEOUT_S` (default 30s), `SLM_SHELL_MAX_OUTPUT_CHARS` |
| Audit log | Every check logs `shell_policy_check`; runs log `shell_invoked` |

## Usage

```bash
slm agent "run the unit tests" --execute
# model may call: run_shell {"command": "uv run pytest -q packages/slm/tests -k shell"}

slm agent "create a build directory" --allow-shell
# model may call: run_shell {"command": "mkdir -p build"}
```

```python
from slm.tools.sandbox import run_sandboxed_command

run_sandboxed_command("ls -la", workspace_root=root, settings=settings,
                      allow_mutating=False, confirmed=False)
```
