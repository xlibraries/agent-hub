from __future__ import annotations

import re
from dataclasses import dataclass

from slm.logging.setup import get_logger

logger = get_logger(__name__)

# Modules runnable with --execute (no arbitrary code).
READ_MODULES = frozenset({"pytest", "unittest", "json.tool"})

# Patterns blocked in python -c snippets even with --allow-shell.
_FORBIDDEN_CODE_PATTERNS = re.compile(
    r"(?i)"
    r"(\b__import__\s*\("
    r"|\beval\s*\("
    r"|\bexec\s*\("
    r"|\bcompile\s*\("
    r"|\bos\.system\b"
    r"|\bsubprocess\b"
    r"|\bshutil\b"
    r"|\bsocket\b"
    r"|\burllib\b"
    r"|\bhttpx\b"
    r"|\brequests\b"
    r"|\bopen\s*\([^)]*['\"]w"
    r"|\bopen\s*\([^)]*['\"]a"
    r"|\bopen\s*\([^)]*\+['\"]w)"
)


class PythonPolicyViolation(Exception):
    """Python execution rejected by sandbox policy."""


class PythonConfirmationRequired(PythonPolicyViolation):
    """Arbitrary code execution needs the --allow-shell human gate."""


@dataclass(frozen=True)
class PythonExecCheck:
    mode: str  # "module" | "code"
    access: str  # "read" | "write" | "denied"
    requires_confirmation: bool
    reason: str


def _validate_extra_args(args: list[str]) -> None:
    for arg in args:
        if not isinstance(arg, str):
            raise PythonPolicyViolation("args must be a list of strings")
        if "\n" in arg or "\r" in arg:
            raise PythonPolicyViolation("args must not contain newlines")


def classify_python_exec(
    *,
    module: str | None,
    args: list[str] | None,
    code: str | None,
    allow_code: bool = False,
) -> PythonExecCheck:
    extra = list(args or [])
    _validate_extra_args(extra)

    if code is not None and module is not None:
        return PythonExecCheck(
            mode="code",
            access="denied",
            requires_confirmation=False,
            reason="provide either module or code, not both",
        )

    if code is not None:
        if not allow_code:
            return PythonExecCheck(
                mode="code",
                access="denied",
                requires_confirmation=False,
                reason="python -c requires --allow-shell",
            )
        stripped = code.strip()
        if not stripped:
            return PythonExecCheck(
                mode="code",
                access="denied",
                requires_confirmation=False,
                reason="code must not be empty",
            )
        if _FORBIDDEN_CODE_PATTERNS.search(stripped):
            return PythonExecCheck(
                mode="code",
                access="denied",
                requires_confirmation=False,
                reason="code contains blocked constructs (subprocess, eval, file writes, …)",
            )
        return PythonExecCheck(
            mode="code",
            access="write",
            requires_confirmation=True,
            reason="arbitrary python -c execution",
        )

    if module is None:
        return PythonExecCheck(
            mode="module",
            access="denied",
            requires_confirmation=False,
            reason="python_exec requires args.module or args.code",
        )

    mod = module.strip()
    if mod not in READ_MODULES:
        return PythonExecCheck(
            mode="module",
            access="denied",
            requires_confirmation=False,
            reason=(
                f"module {mod!r} is not allowlisted "
                f"(allowed: {', '.join(sorted(READ_MODULES))})"
            ),
        )

    return PythonExecCheck(
        mode="module",
        access="read",
        requires_confirmation=False,
        reason=f"read-only module {mod!r}",
    )


def build_python_argv(
    *,
    module: str | None,
    args: list[str] | None,
    code: str | None,
) -> list[str]:
    import sys

    extra = list(args or [])
    if code is not None:
        return [sys.executable, "-c", code]
    return [sys.executable, "-m", module.strip(), *extra]


def guard_python_exec(
    *,
    module: str | None,
    args: list[str] | None,
    code: str | None,
    cwd: str,
    allow_code: bool = False,
    confirmed: bool = False,
    max_code_chars: int,
) -> tuple[PythonExecCheck, list[str]]:
    if code is not None and len(code) > max_code_chars:
        raise PythonPolicyViolation(
            f"code exceeds limit of {max_code_chars} characters "
            f"(got {len(code)})"
        )

    check = classify_python_exec(
        module=module,
        args=args,
        code=code,
        allow_code=allow_code,
    )
    logger.info(
        "python_policy_check",
        module=module,
        args=args,
        has_code=code is not None,
        cwd=cwd,
        access=check.access,
        allow_code=allow_code,
        confirmed=confirmed,
    )

    if check.access == "denied":
        raise PythonPolicyViolation(check.reason)

    if check.requires_confirmation and not confirmed:
        raise PythonConfirmationRequired(
            "python -c requires --allow-shell (human gate) to proceed"
        )

    argv = build_python_argv(module=module, args=args, code=code)
    return check, argv
