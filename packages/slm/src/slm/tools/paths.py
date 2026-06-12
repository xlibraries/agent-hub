from __future__ import annotations

from pathlib import Path


class PathEscapeError(ValueError):
    """Resolved path escapes the workspace root."""


def resolve_workspace_path(workspace_root: Path, path: str) -> Path:
    """Resolve a user-supplied path and ensure it stays within workspace_root."""
    root = workspace_root.resolve()
    raw = path.strip() or "."
    candidate = (root / raw).resolve()
    if not candidate.is_relative_to(root):
        raise PathEscapeError(f"path escapes workspace: {path!r}")
    return candidate
