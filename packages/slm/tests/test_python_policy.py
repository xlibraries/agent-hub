from __future__ import annotations

import pytest
from slm.safety.python_policy import (
    PythonConfirmationRequired,
    PythonPolicyViolation,
    build_python_argv,
    classify_python_exec,
    guard_python_exec,
)


def test_module_pytest_read_only() -> None:
    check = classify_python_exec(module="pytest", args=["-q"], code=None)
    assert check.access == "read"
    assert not check.requires_confirmation


def test_unknown_module_denied() -> None:
    check = classify_python_exec(module="os", args=None, code=None)
    assert check.access == "denied"


def test_code_denied_without_allow_code() -> None:
    check = classify_python_exec(module=None, args=None, code="print(1)")
    assert check.access == "denied"


def test_code_allowed_with_gate() -> None:
    check = classify_python_exec(module=None, args=None, code="print(1)", allow_code=True)
    assert check.access == "write"
    assert check.requires_confirmation


def test_code_blocks_subprocess() -> None:
    check = classify_python_exec(
        module=None, args=None, code="import subprocess", allow_code=True
    )
    assert check.access == "denied"


def test_code_blocks_eval() -> None:
    check = classify_python_exec(module=None, args=None, code="eval('1+1')", allow_code=True)
    assert check.access == "denied"


def test_build_python_argv_module() -> None:
    argv = build_python_argv(module="pytest", args=["-q"], code=None)
    assert argv[1:4] == ["-m", "pytest", "-q"]


def test_build_python_argv_code() -> None:
    argv = build_python_argv(module=None, args=None, code="print(1)")
    assert argv[1:3] == ["-c", "print(1)"]


def test_guard_blocks_code_without_confirmation() -> None:
    with pytest.raises(PythonConfirmationRequired):
        guard_python_exec(
            module=None,
            args=None,
            code="print(1)",
            cwd="/repo",
            allow_code=True,
            confirmed=False,
            max_code_chars=2000,
        )


def test_guard_allows_pytest_module() -> None:
    check, argv = guard_python_exec(
        module="pytest",
        args=["--version"],
        code=None,
        cwd="/repo",
        max_code_chars=2000,
    )
    assert check.access == "read"
    assert "-m" in argv and "pytest" in argv


def test_guard_rejects_oversized_code() -> None:
    with pytest.raises(PythonPolicyViolation, match="exceeds limit"):
        guard_python_exec(
            module=None,
            args=None,
            code="x" * 3000,
            cwd="/repo",
            allow_code=True,
            confirmed=True,
            max_code_chars=2000,
        )
