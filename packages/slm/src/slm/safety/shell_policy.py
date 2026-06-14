from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from slm.logging.setup import get_logger

logger = get_logger(__name__)

# Shell metacharacters / chaining — we never invoke a shell, but reject these in
# the raw command string to catch injection attempts early.
_FORBIDDEN_COMMAND_CHARS = re.compile(r"[;|&`$<>\n\r]")

# Binaries safe for read-only inspection (available with --execute).
READ_BINARIES = frozenset(
    {
        "cat",
        "du",
        "echo",
        "file",
        "find",
        "grep",
        "head",
        "ls",
        "pwd",
        "pytest",
        "rg",
        "sort",
        "stat",
        "tail",
        "tr",
        "uniq",
        "wc",
    }
)

# Binaries that mutate the workspace (require --allow-shell human gate).
WRITE_BINARIES = frozenset({"cp", "mkdir", "mv", "rm", "sed", "tee", "touch"})

# Always denied — use dedicated git tools instead of shell git.
DENIED_BINARIES = frozenset(
    {
        "bash",
        "chown",
        "chmod",
        "curl",
        "dd",
        "eval",
        "exec",
        "fish",
        "kill",
        "mkfs",
        "nc",
        "netcat",
        "node",
        "npm",
        "perl",
        "pkill",
        "python",
        "python3",
        "ruby",
        "scp",
        "sh",
        "ssh",
        "sudo",
        "wget",
        "zsh",
        "git",
    }
)

# uv subcommands permitted under read-only execution.
_UV_READ_RUN_PREFIXES = (
    "pytest",
    "ruff",
    "python -m pytest",
    "python -m unittest",
)


class ShellPolicyViolation(Exception):
    """Shell command rejected by the Agent Hub sandbox policy."""


class ShellConfirmationRequired(ShellPolicyViolation):
    """Mutating shell command needs the --allow-shell human gate."""


@dataclass(frozen=True)
class ShellCommandCheck:
    binary: str
    access: str  # "read" | "write" | "denied"
    requires_confirmation: bool
    reason: str


def parse_command(command: str) -> list[str]:
    """Split a command string into argv without invoking a shell."""
    raw = command.strip()
    if not raw:
        raise ShellPolicyViolation("empty command")
    if _FORBIDDEN_COMMAND_CHARS.search(raw):
        raise ShellPolicyViolation("shell metacharacters and chaining are not allowed")
    try:
        argv = shlex.split(raw, posix=True)
    except ValueError as exc:
        raise ShellPolicyViolation(f"invalid command quoting: {exc}") from exc
    if not argv:
        raise ShellPolicyViolation("empty command")
    return argv


def _binary_name(argv: list[str]) -> str:
    return Path(argv[0]).name.lower() if argv else ""


def _check_uv(argv: list[str], *, allow_mutating: bool) -> ShellCommandCheck:
    if len(argv) < 2 or argv[1] != "run":
        return ShellCommandCheck(
            binary="uv",
            access="denied",
            requires_confirmation=False,
            reason="only `uv run …` is allowlisted",
        )
    rest = " ".join(argv[2:]).strip()
    if not rest:
        return ShellCommandCheck(
            binary="uv",
            access="denied",
            requires_confirmation=False,
            reason="`uv run` requires a command",
        )
    for prefix in _UV_READ_RUN_PREFIXES:
        if rest == prefix or rest.startswith(f"{prefix} "):
            return ShellCommandCheck(
                binary="uv",
                access="read",
                requires_confirmation=False,
                reason="read-only uv run command",
            )
    if allow_mutating:
        return ShellCommandCheck(
            binary="uv",
            access="write",
            requires_confirmation=True,
            reason="mutating uv run command",
        )
    return ShellCommandCheck(
        binary="uv",
        access="denied",
        requires_confirmation=False,
        reason=f"uv run command not allowlisted for read-only execution: {rest!r}",
    )


def _check_rm(argv: list[str]) -> ShellCommandCheck | None:
    if _binary_name(argv) != "rm":
        return None
    flags_and_paths = [a for a in argv[1:] if not a.startswith("-")]
    joined = " ".join(argv[1:]).lower()
    if "-r" in joined or "-rf" in joined or "--recursive" in joined:
        for path in flags_and_paths:
            if path in {".", "..", "/"} or path.startswith("/"):
                return ShellCommandCheck(
                    binary="rm",
                    access="denied",
                    requires_confirmation=False,
                    reason=f"refusing destructive rm: {path!r}",
                )
    return ShellCommandCheck(
        binary="rm",
        access="write",
        requires_confirmation=True,
        reason="file removal",
    )


def classify_shell_command(argv: list[str], *, allow_mutating: bool = False) -> ShellCommandCheck:
    """Classify argv[0] as read / write / denied."""
    binary = _binary_name(argv)
    if not binary:
        return ShellCommandCheck(
            binary="",
            access="denied",
            requires_confirmation=False,
            reason="no command binary",
        )

    if binary in DENIED_BINARIES:
        return ShellCommandCheck(
            binary=binary,
            access="denied",
            requires_confirmation=False,
            reason=f"binary {binary!r} is not allowlisted (use dedicated tools where available)",
        )

    if binary == "uv":
        return _check_uv(argv, allow_mutating=allow_mutating)

    rm_check = _check_rm(argv)
    if rm_check is not None:
        return rm_check

    if binary in READ_BINARIES:
        return ShellCommandCheck(
            binary=binary,
            access="read",
            requires_confirmation=False,
            reason="read-only binary",
        )

    if binary in WRITE_BINARIES:
        if not allow_mutating:
            return ShellCommandCheck(
                binary=binary,
                access="denied",
                requires_confirmation=False,
                reason=f"binary {binary!r} mutates the workspace; requires --allow-shell",
            )
        return ShellCommandCheck(
            binary=binary,
            access="write",
            requires_confirmation=True,
            reason="workspace-mutating binary",
        )

    return ShellCommandCheck(
        binary=binary,
        access="denied",
        requires_confirmation=False,
        reason=f"binary {binary!r} is not allowlisted",
    )


def guard_shell_command(
    argv: list[str],
    *,
    cwd: str,
    allow_mutating: bool = False,
    confirmed: bool = False,
) -> ShellCommandCheck:
    """Enforce sandbox policy; raises on violations."""
    check = classify_shell_command(argv, allow_mutating=allow_mutating)
    logger.info(
        "shell_policy_check",
        argv=argv,
        cwd=cwd,
        binary=check.binary,
        access=check.access,
        allow_mutating=allow_mutating,
        confirmed=confirmed,
    )

    if check.access == "denied":
        raise ShellPolicyViolation(f"{check.binary or 'command'}: {check.reason}")

    if check.requires_confirmation and not confirmed:
        raise ShellConfirmationRequired(
            f"{check.binary} mutates the workspace; pass --allow-shell (human gate) to proceed"
        )

    return check
