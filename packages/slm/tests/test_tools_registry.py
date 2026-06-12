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
