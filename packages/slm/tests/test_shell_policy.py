from __future__ import annotations

import pytest
from slm.safety.shell_policy import (
    ShellConfirmationRequired,
    ShellPolicyViolation,
    classify_shell_command,
    guard_shell_command,
    parse_command,
)


def test_parse_command_splits_without_shell() -> None:
    assert parse_command("ls -la src") == ["ls", "-la", "src"]


def test_parse_rejects_metacharacters() -> None:
    with pytest.raises(ShellPolicyViolation, match="metacharacters"):
        parse_command("ls | cat")
    with pytest.raises(ShellPolicyViolation, match="metacharacters"):
        parse_command("echo hi; rm -rf /")


def test_read_binary_allowed_read_only() -> None:
    check = classify_shell_command(["ls", "-la"])
    assert check.access == "read"
    assert not check.requires_confirmation


def test_write_binary_denied_without_allow_mutating() -> None:
    check = classify_shell_command(["mkdir", "build"])
    assert check.access == "denied"


def test_write_binary_allowed_with_allow_mutating() -> None:
    check = classify_shell_command(["mkdir", "build"], allow_mutating=True)
    assert check.access == "write"
    assert check.requires_confirmation


def test_denied_binary_git() -> None:
    check = classify_shell_command(["git", "status"])
    assert check.access == "denied"
    assert "git" in check.reason


def test_denied_binary_sudo() -> None:
    assert classify_shell_command(["sudo", "ls"]).access == "denied"


def test_uv_run_pytest_read_only() -> None:
    check = classify_shell_command(["uv", "run", "pytest", "-q"])
    assert check.access == "read"


def test_uv_run_unknown_denied_read_only() -> None:
    check = classify_shell_command(["uv", "run", "pip", "install", "evil"])
    assert check.access == "denied"


def test_uv_run_unknown_allowed_with_mutating_gate() -> None:
    check = classify_shell_command(["uv", "run", "pip", "install", "evil"], allow_mutating=True)
    assert check.access == "write"
    assert check.requires_confirmation


def test_guard_blocks_write_without_confirmation() -> None:
    with pytest.raises(ShellConfirmationRequired):
        guard_shell_command(["mkdir", "x"], cwd="/repo", allow_mutating=True)


def test_guard_allows_read_without_confirmation() -> None:
    check = guard_shell_command(["ls"], cwd="/repo")
    assert check.access == "read"


def test_guard_allows_write_with_confirmation() -> None:
    check = guard_shell_command(
        ["mkdir", "x"], cwd="/repo", allow_mutating=True, confirmed=True
    )
    assert check.access == "write"


def test_rm_rf_dot_denied() -> None:
    check = classify_shell_command(["rm", "-rf", "."], allow_mutating=True)
    assert check.access == "denied"
