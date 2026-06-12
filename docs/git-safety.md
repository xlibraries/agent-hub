# Git & shell safety policy

Issue: [#14](https://github.com/xlibraries/agent-hub/issues/14) · Module: `slm.safety.git_policy`

Agent Hub treats every repo-mutating operation as privileged. The policy is
enforced in code (`guard_git_command`), not just in prompts.

## Rules

| Rule | Enforcement |
|------|-------------|
| Read vs write allowlist | `READ_SUBCOMMANDS` run freely; `WRITE_SUBCOMMANDS` (add, commit, push, reset, …) require confirmation; everything else is **denied** |
| Human confirmation gate | `guard_git_command(..., confirmed=False)` raises `ConfirmationRequired` for any write subcommand |
| Secret hygiene | `add`/`commit` argv is scanned against `SECRET_PATH_PATTERNS` (`.env*`, `*.pem`, `*.key`, `id_rsa*`, `*credentials*`, `*secret*`, `*token*`, …); matches raise `GitPolicyViolation` even when confirmed |
| Full audit log | Every policy check is structured-logged (`git_policy_check`: args, cwd, access, confirmed); read-only snapshot commands log `git_invoked` |
| Explicit intent | Commit/push tools may only be invoked when the user goal explicitly requests them — enforced at the CLI layer when write tools land (#13) |

## Usage

```python
from slm.safety.git_policy import guard_git_command, ConfirmationRequired

guard_git_command(["status", "--short"], cwd=str(root))            # ok
guard_git_command(["commit", "-m", "msg"], cwd=str(root))          # raises ConfirmationRequired
guard_git_command(["commit", "-m", "msg"], cwd=str(root), confirmed=True)  # ok
guard_git_command(["add", ".env"], cwd=str(root), confirmed=True)  # raises GitPolicyViolation
```

The kill switch (`SLM_KILL_SWITCH=1`) independently halts all autonomous
loops regardless of policy state.
