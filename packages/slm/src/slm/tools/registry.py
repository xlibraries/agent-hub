from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ToolHandler = Callable[[dict[str, Any]], "ToolResult"]


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: str
    error: str = ""


class ToolRegistry:
    """Maps tool names to read-only handlers scoped to a workspace root."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, name: str, handler: ToolHandler) -> None:
        self._handlers[name.strip().lower()] = handler

    def list_tools(self) -> list[str]:
        return sorted(self._handlers)

    def execute(self, name: str, args: dict[str, Any] | None) -> ToolResult:
        key = name.strip().lower()
        handler = self._handlers.get(key)
        if handler is None:
            return ToolResult(ok=False, output="", error=f"unknown tool: {name!r}")
        try:
            return handler(args or {})
        except Exception as exc:
            return ToolResult(ok=False, output="", error=str(exc))
