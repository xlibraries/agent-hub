from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from slm.config.settings import Settings, get_settings
from slm.context.repo import gather_repo_context
from slm.context.truncate import truncate_text
from slm.tools.paths import PathEscapeError, resolve_workspace_path
from slm.tools.registry import ToolRegistry, ToolResult

ToolHandler = Callable[[dict[str, Any]], ToolResult]

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


def _should_skip_dir(name: str) -> bool:
    if name.startswith(".") and name not in {".github"}:
        return True
    return name in _SKIP_DIRS or name.endswith(".egg-info")


def _read_file_handler(workspace_root: Path, settings: Settings) -> ToolHandler:
    def handler(args: dict[str, Any]) -> ToolResult:
        path_arg = str(args.get("path", "")).strip()
        if not path_arg:
            return ToolResult(ok=False, output="", error="read_file requires args.path")
        try:
            target = resolve_workspace_path(workspace_root, path_arg)
        except PathEscapeError as exc:
            return ToolResult(ok=False, output="", error=str(exc))
        if not target.is_file():
            return ToolResult(ok=False, output="", error=f"not a file: {path_arg!r}")
        max_bytes = int(args.get("max_bytes", settings.tool_max_read_bytes))
        data = target.read_bytes()[:max_bytes]
        text = data.decode("utf-8", errors="replace")
        if len(data) >= max_bytes:
            text = truncate_text(text, max_bytes, label="file")
        return ToolResult(ok=True, output=text)

    return handler


def _list_dir_handler(workspace_root: Path) -> ToolHandler:
    def handler(args: dict[str, Any]) -> ToolResult:
        path_arg = str(args.get("path", ".")).strip() or "."
        try:
            target = resolve_workspace_path(workspace_root, path_arg)
        except PathEscapeError as exc:
            return ToolResult(ok=False, output="", error=str(exc))
        if not target.is_dir():
            return ToolResult(ok=False, output="", error=f"not a directory: {path_arg!r}")
        lines: list[str] = []
        try:
            entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError as exc:
            return ToolResult(ok=False, output="", error=str(exc))
        for entry in entries:
            if entry.is_dir() and _should_skip_dir(entry.name):
                continue
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{entry.name}{suffix}")
        return ToolResult(ok=True, output="\n".join(lines) if lines else "(empty directory)")

    return handler


def _grep_text_handler(workspace_root: Path, settings: Settings) -> ToolHandler:
    def handler(args: dict[str, Any]) -> ToolResult:
        pattern = str(args.get("pattern", "")).strip()
        if not pattern:
            return ToolResult(ok=False, output="", error="grep_text requires args.pattern")
        path_arg = str(args.get("path", ".")).strip() or "."
        try:
            target = resolve_workspace_path(workspace_root, path_arg)
        except PathEscapeError as exc:
            return ToolResult(ok=False, output="", error=str(exc))

        max_matches = settings.tool_grep_max_matches
        max_files = settings.tool_grep_max_files
        max_bytes = settings.tool_max_read_bytes
        matches: list[str] = []
        files_seen = 0

        def scan_file(file_path: Path) -> None:
            nonlocal files_seen
            if len(matches) >= max_matches or files_seen >= max_files:
                return
            files_seen += 1
            try:
                data = file_path.read_bytes()[:max_bytes]
                text = data.decode("utf-8", errors="replace")
            except OSError:
                return
            for line_no, line in enumerate(text.splitlines(), start=1):
                if pattern in line:
                    rel = file_path.relative_to(workspace_root.resolve())
                    matches.append(f"{rel}:{line_no}:{line.rstrip()}")
                    if len(matches) >= max_matches:
                        return

        if target.is_file():
            scan_file(target)
        elif target.is_dir():
            for file_path in sorted(target.rglob("*")):
                if len(matches) >= max_matches or files_seen >= max_files:
                    break
                if not file_path.is_file():
                    continue
                if any(part in _SKIP_DIRS or part.startswith(".") for part in file_path.parts):
                    continue
                scan_file(file_path)
        else:
            return ToolResult(ok=False, output="", error=f"path not found: {path_arg!r}")

        if not matches:
            return ToolResult(ok=True, output=f"(no matches for {pattern!r})")
        output = "\n".join(matches)
        if len(matches) >= max_matches:
            output += f"\n…(match limit {max_matches} reached)"
        return ToolResult(ok=True, output=output)

    return handler


def _git_status_handler(workspace_root: Path, settings: Settings) -> ToolHandler:
    def handler(args: dict[str, Any]) -> ToolResult:
        _ = args
        ctx = gather_repo_context(workspace_root, settings)
        if not ctx.is_git_repo:
            return ToolResult(ok=False, output="", error="not a git repository")
        output = ctx.status or "(clean)"
        return ToolResult(ok=True, output=output)

    return handler


def _git_diff_staged_handler(workspace_root: Path, settings: Settings) -> ToolHandler:
    def handler(args: dict[str, Any]) -> ToolResult:
        _ = args
        ctx = gather_repo_context(workspace_root, settings)
        if not ctx.is_git_repo:
            return ToolResult(ok=False, output="", error="not a git repository")
        output = truncate_text(
            ctx.staged_diff or "(no staged changes)",
            settings.context_diff_max_chars,
            label="staged diff",
        )
        return ToolResult(ok=True, output=output)

    return handler


def create_default_registry(
    workspace_root: Path,
    settings: Settings | None = None,
) -> ToolRegistry:
    s = settings or get_settings()
    root = workspace_root.resolve()
    registry = ToolRegistry(root)
    registry.register("read_file", _read_file_handler(root, s))
    registry.register("list_dir", _list_dir_handler(root))
    registry.register("grep_text", _grep_text_handler(root, s))
    registry.register("git_status", _git_status_handler(root, s))
    registry.register("git_diff_staged", _git_diff_staged_handler(root, s))
    return registry


AVAILABLE_TOOLS_DOC = """Available read-only tools (set tool.name when execution is enabled):
- read_file: {"path": "relative/path"}
- list_dir: {"path": "."}
- grep_text: {"pattern": "substring", "path": "."}
- git_status: {}
- git_diff_staged: {}
"""
