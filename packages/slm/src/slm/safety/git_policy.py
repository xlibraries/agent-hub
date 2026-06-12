from __future__ import annotations

import fnmatch
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath

from slm.logging.setup import get_logger

logger = get_logger(__name__)

# Read-only git subcommands the agent may run without confirmation.
READ_SUBCOMMANDS = frozenset(
    {
        "status",
        "diff",
        "log",
        "show",
        "rev-parse",
        "branch",
        "ls-files",
        "blame",
        "describe",
        "shortlog",
        "remote",
    }
)

# Repo-mutating subcommands: allowed only with explicit human confirmation.
WRITE_SUBCOMMANDS = frozenset(
    {
        "add",
        "commit",
        "push",
        "checkout",
        "switch",
        "restore",
        "reset",
        "merge",
        "rebase",
        "cherry-pick",
        "revert",
        "rm",
        "mv",
        "stash",
        "tag",
        "clean",
    }
)

# Paths that must never be staged/committed by the agent without human review.
SECRET_PATH_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "id_ed25519*",
    "*credentials*",
    "*secret*",
    "*.keystore",
    "*token*",
)


class GitPolicyViolation(Exception):
    """Git command rejected by the Agent Hub safety policy."""


class ConfirmationRequired(GitPolicyViolation):
    """Write command needs an explicit human confirmation gate."""


@dataclass(frozen=True)
class GitCommandCheck:
    subcommand: str
    access: str  # "read" | "write" | "denied"
    requires_confirmation: bool
    reason: str


def classify_git_command(args: list[str]) -> GitCommandCheck:
    """Classify a git argv (without the leading 'git') as read/write/denied."""
    positional = [a for a in args if not a.startswith("-")]
    if not positional:
        return GitCommandCheck(
            subcommand="",
            access="denied",
            requires_confirmation=False,
            reason="no git subcommand provided",
        )
    sub = positional[0].lower()
    if sub in READ_SUBCOMMANDS:
        return GitCommandCheck(
            subcommand=sub,
            access="read",
            requires_confirmation=False,
            reason="read-only subcommand",
        )
    if sub in WRITE_SUBCOMMANDS:
        return GitCommandCheck(
            subcommand=sub,
            access="write",
            requires_confirmation=True,
            reason="repo-mutating subcommand; human confirmation required",
        )
    return GitCommandCheck(
        subcommand=sub,
        access="denied",
        requires_confirmation=False,
        reason=f"subcommand {sub!r} is not allowlisted",
    )


def is_secret_path(path: str) -> bool:
    name = PurePosixPath(path.replace("\\", "/")).name.lower()
    return any(fnmatch.fnmatch(name, pattern) for pattern in SECRET_PATH_PATTERNS)


def find_secret_paths(paths: Iterable[str]) -> list[str]:
    return [p for p in paths if is_secret_path(p)]


def guard_git_command(
    args: list[str],
    *,
    cwd: str,
    confirmed: bool = False,
) -> GitCommandCheck:
    """Enforce the git policy for one invocation; raises on violations.

    Every call is structured-logged (golden rule 2), including denials.
    """
    check = classify_git_command(args)
    logger.info(
        "git_policy_check",
        args=args,
        cwd=cwd,
        subcommand=check.subcommand,
        access=check.access,
        confirmed=confirmed,
    )

    if check.access == "denied":
        raise GitPolicyViolation(f"git {check.subcommand or '<none>'}: {check.reason}")

    if check.subcommand in {"add", "commit"}:
        secrets = find_secret_paths(a for a in args[1:] if not a.startswith("-"))
        if secrets:
            raise GitPolicyViolation(
                f"refusing to stage/commit secret-like paths: {', '.join(secrets)}"
            )

    if check.requires_confirmation and not confirmed:
        raise ConfirmationRequired(
            f"git {check.subcommand} mutates the repo; pass an explicit confirmation "
            "(human approval gate) to proceed"
        )

    return check
