from __future__ import annotations

from pathlib import Path

from slm.context.repo import gather_repo_context


def test_gather_repo_context_in_agent_hub_repo() -> None:
    root = Path(__file__).resolve().parents[3]
    ctx = gather_repo_context(root)
    assert ctx.is_git_repo is True
    assert "Working directory:" in ctx.as_prompt_block()
    assert "## git status" in ctx.as_prompt_block()


def test_gather_repo_context_non_git_dir(tmp_path: Path) -> None:
    ctx = gather_repo_context(tmp_path)
    assert ctx.is_git_repo is False
    assert "not a git repository" in ctx.as_prompt_block()
