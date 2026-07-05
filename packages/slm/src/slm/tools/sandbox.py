from __future__ import annotations

import os
import subprocess
from pathlib import Path

from slm.config.settings import Settings
from slm.context.truncate import truncate_text
from slm.logging.setup import get_logger
from slm.safety.shell_policy import ShellPolicyViolation, guard_shell_command, parse_command
from slm.tools.registry import ToolResult

logger = get_logger(__name__)

_SENSITIVE_ENV_PREFIXES = (
    "AWS_",
    "GITHUB_",
    "GITLAB_",
    "SLACK_",
    "OPENAI_",
    "ANTHROPIC_",
    "HF_",
    "HUGGINGFACE_",
)
_SENSITIVE_ENV_SUBSTRINGS = ("SECRET", "TOKEN", "PASSWORD", "API_KEY", "PRIVATE_KEY")


def _is_sensitive_env(name: str) -> bool:
    upper = name.upper()
    if any(upper.startswith(prefix) for prefix in _SENSITIVE_ENV_PREFIXES):
        return True
    return any(part in upper for part in _SENSITIVE_ENV_SUBSTRINGS)


def sandbox_env(workspace_root: Path) -> dict[str, str]:
    """Minimal environment: strip secrets, confine HOME to the workspace."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not _is_sensitive_env(key)
    }
    root = workspace_root.resolve()
    env["HOME"] = str(root)
    env["PWD"] = str(root)
    env.setdefault("LANG", "C.UTF-8")
    env.setdefault("TERM", "dumb")
    env["SLM_SANDBOX"] = "1"
    return env


def run_sandboxed(
    argv: list[str],
    *,
    workspace_root: Path,
    settings: Settings,
    allow_mutating: bool,
    confirmed: bool,
) -> ToolResult:
    """Execute argv without a shell, inside workspace_root, with policy checks."""
    root = workspace_root.resolve()
    try:
        guard_shell_command(
            argv,
            cwd=str(root),
            allow_mutating=allow_mutating,
            confirmed=confirmed,
        )
    except ShellPolicyViolation as exc:
        return ToolResult(ok=False, output="", error=str(exc))

    logger.info("shell_invoked", argv=argv, cwd=str(root), allow_mutating=allow_mutating)

    try:
        completed = subprocess.run(
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=settings.shell_timeout_s,
            env=sandbox_env(root),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            ok=False,
            output="",
            error=f"command timed out after {settings.shell_timeout_s}s",
        )
    except OSError as exc:
        return ToolResult(ok=False, output="", error=str(exc))

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if stdout and stderr:
        combined = f"{stdout.rstrip()}\n--- stderr ---\n{stderr.rstrip()}"
    else:
        combined = (stdout or stderr).rstrip()

    combined = truncate_text(
        combined or "(no output)",
        settings.shell_max_output_chars,
        label="shell output",
    )

    if completed.returncode != 0:
        return ToolResult(
            ok=False,
            output=combined,
            error=f"command exited {completed.returncode}",
        )
    return ToolResult(ok=True, output=combined)


def run_sandboxed_command(
    command: str,
    *,
    workspace_root: Path,
    settings: Settings,
    allow_mutating: bool,
    confirmed: bool,
) -> ToolResult:
    try:
        argv = parse_command(command)
    except ShellPolicyViolation as exc:
        return ToolResult(ok=False, output="", error=str(exc))
    return run_sandboxed(
        argv,
        workspace_root=workspace_root,
        settings=settings,
        allow_mutating=allow_mutating,
        confirmed=confirmed,
    )
