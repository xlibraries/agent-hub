from __future__ import annotations

from pathlib import Path

import pytest
from slm.tools.builtin import create_default_registry
from slm.tools.paths import PathEscapeError, resolve_workspace_path


def test_resolve_workspace_path_allows_relative_file(tmp_path: Path) -> None:
    target = tmp_path / "src" / "main.py"
    target.parent.mkdir()
    target.write_text("hello\n", encoding="utf-8")
    resolved = resolve_workspace_path(tmp_path, "src/main.py")
    assert resolved == target.resolve()


def test_resolve_workspace_path_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(PathEscapeError):
        resolve_workspace_path(tmp_path, "../outside")


def test_read_file_tool(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    registry = create_default_registry(tmp_path)
    result = registry.execute("read_file", {"path": "notes.txt"})
    assert result.ok
    assert "alpha" in result.output


def test_list_dir_tool(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    registry = create_default_registry(tmp_path)
    result = registry.execute("list_dir", {"path": "."})
    assert result.ok
    assert "a.py" in result.output
    assert "pkg/" in result.output


def test_grep_text_tool(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print('needle')\n", encoding="utf-8")
    registry = create_default_registry(tmp_path)
    result = registry.execute("grep_text", {"pattern": "needle", "path": "."})
    assert result.ok
    assert "main.py:" in result.output
    assert "needle" in result.output


def test_unknown_tool_returns_error(tmp_path: Path) -> None:
    registry = create_default_registry(tmp_path)
    result = registry.execute("does_not_exist", {})
    assert not result.ok
    assert "unknown tool" in result.error


def test_read_file_rejects_path_escape(tmp_path: Path) -> None:
    registry = create_default_registry(tmp_path)
    result = registry.execute("read_file", {"path": "../secrets"})
    assert not result.ok
    assert "escapes workspace" in result.error


def test_write_file_not_registered_by_default(tmp_path: Path) -> None:
    registry = create_default_registry(tmp_path)
    result = registry.execute("write_file", {"path": "a.txt", "content": "x"})
    assert not result.ok
    assert "unknown tool" in result.error


def test_write_file_writes_within_workspace(tmp_path: Path) -> None:
    registry = create_default_registry(tmp_path, allow_writes=True)
    result = registry.execute("write_file", {"path": "sub/new.txt", "content": "data"})
    assert result.ok
    assert (tmp_path / "sub" / "new.txt").read_text(encoding="utf-8") == "data"


def test_write_file_rejects_secret_and_escape(tmp_path: Path) -> None:
    registry = create_default_registry(tmp_path, allow_writes=True)
    secret = registry.execute("write_file", {"path": ".env", "content": "x"})
    assert not secret.ok and "secret" in secret.error
    escape = registry.execute("write_file", {"path": "../out.txt", "content": "x"})
    assert not escape.ok and "escapes workspace" in escape.error


def test_git_exec_read_allowed(tmp_path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    registry = create_default_registry(tmp_path, allow_writes=True)
    result = registry.execute("git_exec", {"args": ["status", "--short"]})
    assert result.ok


def test_git_exec_denies_non_allowlisted(tmp_path: Path) -> None:
    registry = create_default_registry(tmp_path, allow_writes=True)
    result = registry.execute("git_exec", {"args": ["daemon"]})
    assert not result.ok
    assert "not allowlisted" in result.error


def test_git_exec_blocks_secret_staging(tmp_path: Path) -> None:
    registry = create_default_registry(tmp_path, allow_writes=True)
    result = registry.execute("git_exec", {"args": ["add", ".env"]})
    assert not result.ok
    assert "secret-like" in result.error
