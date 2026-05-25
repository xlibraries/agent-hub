from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoContext:
    """Read-only snapshot of the current Git workspace."""

    cwd: str
    is_git_repo: bool
    status: str
    staged_diff: str
    recent_commits: str

    def as_prompt_block(self, max_chars: int = 24_000) -> str:
        if not self.is_git_repo:
            return f"Working directory: {self.cwd}\n(not a git repository — no git context available)"

        parts = [
            f"Working directory: {self.cwd}",
            "## git status",
            self.status or "(clean)",
            "## git diff --staged",
            self.staged_diff or "(no staged changes)",
            "## git log -5 --oneline",
            self.recent_commits or "(no commits)",
        ]
        text = "\n".join(parts)
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 40] + "\n\n…(truncated for context limit)"


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        return f"(git {' '.join(args)} failed: {err or 'unknown error'})"
    return (result.stdout or "").strip()


def gather_repo_context(cwd: Path | None = None) -> RepoContext:
    root = (cwd or Path.cwd()).resolve()
    inside = _run_git(["rev-parse", "--is-inside-work-tree"], root)
    is_repo = inside.strip() == "true"

    if not is_repo:
        return RepoContext(
            cwd=str(root),
            is_git_repo=False,
            status="",
            staged_diff="",
            recent_commits="",
        )

    return RepoContext(
        cwd=str(root),
        is_git_repo=True,
        status=_run_git(["status", "--short", "--branch"], root),
        staged_diff=_run_git(["diff", "--staged"], root),
        recent_commits=_run_git(["log", "-5", "--oneline"], root),
    )
