from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from slm.config.settings import Settings, get_settings
from slm.context.repo import gather_repo_context
from slm.context.truncate import truncate_text
from slm.safety.git_policy import GitPolicyViolation, guard_git_command, is_secret_path
from slm.tools.paths import PathEscapeError, resolve_workspace_path
from slm.tools.registry import ToolRegistry, ToolResult
from slm.tools.sandbox import run_sandboxed_command

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


def _write_file_handler(workspace_root: Path) -> ToolHandler:
    def handler(args: dict[str, Any]) -> ToolResult:
        path_arg = str(args.get("path", "")).strip()
        if not path_arg:
            return ToolResult(ok=False, output="", error="write_file requires args.path")
        content = args.get("content")
        if not isinstance(content, str):
            return ToolResult(ok=False, output="", error="write_file requires string args.content")
        if is_secret_path(path_arg):
            return ToolResult(
                ok=False, output="", error=f"refusing to write secret-like path: {path_arg!r}"
            )
        try:
            target = resolve_workspace_path(workspace_root, path_arg)
        except PathEscapeError as exc:
            return ToolResult(ok=False, output="", error=str(exc))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ToolResult(ok=True, output=f"wrote {len(content)} chars to {path_arg}")

    return handler


def _git_exec_handler(workspace_root: Path, *, confirmed: bool) -> ToolHandler:
    def handler(args: dict[str, Any]) -> ToolResult:
        raw = args.get("args")
        if not isinstance(raw, list) or not all(isinstance(a, str) for a in raw):
            return ToolResult(
                ok=False, output="", error='git_exec requires args.args as a list of strings'
            )
        git_args = [a for a in raw if a]
        if git_args and git_args[0] == "git":
            git_args = git_args[1:]
        try:
            guard_git_command(git_args, cwd=str(workspace_root), confirmed=confirmed)
        except GitPolicyViolation as exc:
            return ToolResult(ok=False, output="", error=str(exc))

        result = subprocess.run(
            ["git", *git_args],
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            return ToolResult(ok=False, output="", error=f"git exited {result.returncode}: {err}")
        return ToolResult(ok=True, output=(result.stdout or "").strip() or "(no output)")

    return handler


def _run_shell_handler(
    workspace_root: Path, settings: Settings, *, allow_shell: bool
) -> ToolHandler:
    def handler(args: dict[str, Any]) -> ToolResult:
        command = str(args.get("command", "")).strip()
        if not command:
            return ToolResult(ok=False, output="", error="run_shell requires args.command")
        return run_sandboxed_command(
            command,
            workspace_root=workspace_root,
            settings=settings,
            allow_mutating=allow_shell,
            confirmed=allow_shell,
        )

    return handler


def create_default_registry(
    workspace_root: Path,
    settings: Settings | None = None,
    *,
    allow_writes: bool = False,
    allow_shell: bool = False,
) -> ToolRegistry:
    s = settings or get_settings()
    root = workspace_root.resolve()
    registry = ToolRegistry(root)
    registry.register("read_file", _read_file_handler(root, s))
    registry.register("list_dir", _list_dir_handler(root))
    registry.register("grep_text", _grep_text_handler(root, s))
    registry.register("git_status", _git_status_handler(root, s))
    registry.register("git_diff_staged", _git_diff_staged_handler(root, s))
    registry.register("run_shell", _run_shell_handler(root, s, allow_shell=allow_shell))
    if allow_writes:
        registry.register("write_file", _write_file_handler(root))
        # The human passed the explicit --allow-writes gate; git policy still
        # denies non-allowlisted subcommands and secret-like paths.
        registry.register("git_exec", _git_exec_handler(root, confirmed=True))
    return registry


AVAILABLE_TOOLS_DOC = """Available read-only tools (set tool.name when execution is enabled):
- read_file: {"path": "relative/path"}
- list_dir: {"path": "."}
- grep_text: {"pattern": "substring", "path": "."}
- git_status: {}
- git_diff_staged: {}
- run_shell: {"command": "ls -la"} or {"command": "uv run pytest -q"}
  Sandboxed: no shell invocation, argv allowlist only. Mutating commands need --allow-shell.
"""

WRITE_TOOLS_DOC = """Write tools (human-approved for this run; use only when the goal requires it):
- write_file: {"path": "relative/path", "content": "full new file content"}
- git_exec: {"args": ["add", "src/main.py"]} or {"args": ["commit", "-m", "message"]}
  Only allowlisted git subcommands run; secret-like paths are always refused.
"""

SHELL_TOOLS_DOC = """Shell mutations (--allow-shell human gate):
- run_shell: {"command": "mkdir -p build"} or {"command": "rm notes.tmp"}
  Never use shell metacharacters (; | & >). Use git_exec for git, not run_shell.
"""


def build_tools_doc(allow_writes: bool, allow_shell: bool = False) -> str:
    parts = [AVAILABLE_TOOLS_DOC]
    if allow_writes:
        parts.append(WRITE_TOOLS_DOC)
    if allow_shell:
        parts.append(SHELL_TOOLS_DOC)
    return "\n".join(parts)
