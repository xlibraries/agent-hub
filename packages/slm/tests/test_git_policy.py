from __future__ import annotations

import pytest
from slm.safety.git_policy import (
    ConfirmationRequired,
    GitPolicyViolation,
    classify_git_command,
    find_secret_paths,
    guard_git_command,
    is_secret_path,
)


def test_read_subcommands_classified_read() -> None:
    for sub in ("status", "diff", "log", "show", "rev-parse"):
        check = classify_git_command([sub])
        assert check.access == "read"
        assert not check.requires_confirmation


def test_write_subcommands_require_confirmation() -> None:
    for sub in ("add", "commit", "push", "reset", "rebase"):
        check = classify_git_command([sub])
        assert check.access == "write"
        assert check.requires_confirmation


def test_unknown_subcommand_denied() -> None:
    assert classify_git_command(["daemon"]).access == "denied"
    assert classify_git_command([]).access == "denied"


def test_flags_skipped_when_finding_subcommand() -> None:
    check = classify_git_command(["--no-pager", "log", "-5"])
    assert check.subcommand == "log"
    assert check.access == "read"


def test_secret_path_detection() -> None:
    assert is_secret_path(".env")
    assert is_secret_path("config/.env.production")
    assert is_secret_path("deploy/id_rsa")
    assert is_secret_path("certs/server.pem")
    assert is_secret_path("aws_credentials.json")
    assert not is_secret_path("src/main.py")
    assert not is_secret_path("README.md")


def test_find_secret_paths_filters() -> None:
    found = find_secret_paths(["src/main.py", ".env", "k.pem"])
    assert found == [".env", "k.pem"]


def test_guard_allows_read_without_confirmation() -> None:
    check = guard_git_command(["status", "--short"], cwd="/repo")
    assert check.access == "read"


def test_guard_blocks_write_without_confirmation() -> None:
    with pytest.raises(ConfirmationRequired):
        guard_git_command(["commit", "-m", "msg"], cwd="/repo")


def test_guard_allows_write_with_confirmation() -> None:
    check = guard_git_command(["commit", "-m", "msg"], cwd="/repo", confirmed=True)
    assert check.access == "write"


def test_guard_denies_unknown_subcommand_even_confirmed() -> None:
    with pytest.raises(GitPolicyViolation):
        guard_git_command(["daemon"], cwd="/repo", confirmed=True)


def test_guard_blocks_staging_secrets_even_confirmed() -> None:
    with pytest.raises(GitPolicyViolation, match="secret-like"):
        guard_git_command(["add", ".env"], cwd="/repo", confirmed=True)
    with pytest.raises(GitPolicyViolation, match="secret-like"):
        guard_git_command(["commit", "server.pem"], cwd="/repo", confirmed=True)


def test_guard_allows_staging_normal_files_with_confirmation() -> None:
    check = guard_git_command(["add", "src/main.py"], cwd="/repo", confirmed=True)
    assert check.subcommand == "add"
