from __future__ import annotations

from pathlib import Path

from slm.context.repo import gather_repo_context
from slm.context.truncate import truncate_text


def test_gather_repo_context_in_agent_hub_repo() -> None:
    root = Path(__file__).resolve().parents[3]
    ctx = gather_repo_context(root)
    block = ctx.as_prompt_block()
    assert "Working directory:" in block
    assert "## README (excerpt)" in block
    assert "Agent Hub" in block or "agent" in block.lower()
    assert "## File tree (shallow)" in block
    if ctx.is_git_repo:
        assert "## git status" in block
        assert "## git diff (unstaged)" in block


def test_gather_repo_context_non_git_dir(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Temp\n\nA scratch project.\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('hi')\n", encoding="utf-8")
    ctx = gather_repo_context(tmp_path)
    assert ctx.is_git_repo is False
    block = ctx.as_prompt_block()
    assert "not a git repository" in block
    assert "Temp" in block
    assert "main.py" in block


def test_truncate_text_adds_marker() -> None:
    long = "x" * 100
    out = truncate_text(long, 50, label="test")
    assert len(out) < 100
    assert "truncated" in out
