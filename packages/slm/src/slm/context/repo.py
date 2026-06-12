from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from slm.config.settings import Settings, get_settings
from slm.context.truncate import truncate_text
from slm.logging.setup import get_logger

logger = get_logger(__name__)

_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".agent-hub",
    ".eggs",
}
_README_NAMES = ("README.md", "README.MD", "readme.md", "README")
_MANIFEST_NAMES = ("pyproject.toml", "package.json", "Cargo.toml")


@dataclass(frozen=True)
class RepoContext:
    """Read-only snapshot of the workspace (git + project files)."""

    cwd: str
    is_git_repo: bool
    status: str
    staged_diff: str
    unstaged_diff: str
    recent_commits: str
    readme: str
    file_tree: str
    project_manifest: str

    def as_prompt_block(self, settings: Settings | None = None) -> str:
        s = settings or get_settings()
        parts = [f"Working directory: {self.cwd}"]

        if self.readme:
            parts.extend(
                [
                    "## README (excerpt)",
                    truncate_text(self.readme, s.context_readme_max_chars, label="README"),
                ]
            )
        if self.project_manifest:
            parts.extend(
                [
                    "## Project manifest (excerpt)",
                    truncate_text(
                        self.project_manifest,
                        s.context_manifest_max_chars,
                        label="manifest",
                    ),
                ]
            )
        if self.file_tree:
            parts.extend(["## File tree (shallow)", self.file_tree])

        if self.is_git_repo:
            parts.extend(
                [
                    "## git status",
                    self.status or "(clean)",
                    "## git diff --staged",
                    truncate_text(
                        self.staged_diff or "(no staged changes)",
                        s.context_diff_max_chars,
                        label="staged diff",
                    ),
                    "## git diff (unstaged)",
                    truncate_text(
                        self.unstaged_diff or "(no unstaged changes)",
                        s.context_diff_max_chars,
                        label="unstaged diff",
                    ),
                    "## git log -5 --oneline",
                    self.recent_commits or "(no commits)",
                ]
            )
        else:
            parts.append("(not a git repository — git sections omitted)")

        text = "\n".join(parts)
        return truncate_text(text, s.context_max_chars, label="workspace snapshot")


def _run_git(args: list[str], cwd: Path) -> str:
    logger.debug("git_invoked", args=args, cwd=str(cwd))
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


def _read_file_limited(path: Path, max_bytes: int = 64_000) -> str:
    if not path.is_file():
        return ""
    try:
        data = path.read_bytes()[:max_bytes]
        return data.decode("utf-8", errors="replace").strip()
    except OSError:
        return ""


def _find_readme(root: Path) -> str:
    for name in _README_NAMES:
        text = _read_file_limited(root / name)
        if text:
            return text
    return ""


def _find_manifest(root: Path) -> str:
    for name in _MANIFEST_NAMES:
        text = _read_file_limited(root / name)
        if text:
            return text
    return ""


def _should_skip_dir(name: str) -> bool:
    if name.startswith(".") and name not in {".github"}:
        return True
    return name in _SKIP_DIRS or name.endswith(".egg-info")


def _build_file_tree(root: Path, settings: Settings) -> str:
    lines: list[str] = []
    max_entries = settings.context_tree_max_entries
    max_depth = settings.context_tree_max_depth

    def walk(dir_path: Path, prefix: str, depth: int) -> None:
        if depth > max_depth or len(lines) >= max_entries:
            return
        try:
            entries = sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return
        for entry in entries:
            if len(lines) >= max_entries:
                lines.append("…(tree entry limit reached)")
                return
            if entry.is_dir():
                if _should_skip_dir(entry.name):
                    continue
                lines.append(f"{prefix}{entry.name}/")
                walk(entry, prefix + "  ", depth + 1)
            else:
                lines.append(f"{prefix}{entry.name}")

    walk(root, "", 0)
    if not lines:
        return "(empty directory)"
    return "\n".join(lines)


def gather_repo_context(cwd: Path | None = None, settings: Settings | None = None) -> RepoContext:
    s = settings or get_settings()
    root = (cwd or Path.cwd()).resolve()
    readme = _find_readme(root)
    manifest = _find_manifest(root)
    file_tree = _build_file_tree(root, s)

    inside = _run_git(["rev-parse", "--is-inside-work-tree"], root)
    is_repo = inside.strip() == "true"

    if not is_repo:
        return RepoContext(
            cwd=str(root),
            is_git_repo=False,
            status="",
            staged_diff="",
            unstaged_diff="",
            recent_commits="",
            readme=readme,
            file_tree=file_tree,
            project_manifest=manifest,
        )

    return RepoContext(
        cwd=str(root),
        is_git_repo=True,
        status=_run_git(["status", "--short", "--branch"], root),
        staged_diff=_run_git(["diff", "--staged"], root),
        unstaged_diff=_run_git(["diff"], root),
        recent_commits=_run_git(["log", "-5", "--oneline"], root),
        readme=readme,
        file_tree=file_tree,
        project_manifest=manifest,
    )
