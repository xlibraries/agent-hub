from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from slm.config.settings import Settings, get_settings
from slm.prompts.agent import AGENT_SYSTEM
from slm.prompts.planner import PLANNER_SYSTEM

_BUILTINS: dict[str, str] = {
    "agent.default": AGENT_SYSTEM,
    "planner.default": PLANNER_SYSTEM,
}


class PromptNotFoundError(KeyError):
    """No builtin or override prompt registered under the requested key."""


@dataclass(frozen=True)
class PromptInfo:
    key: str
    source: str  # "builtin" | "override"
    text: str


class PromptRegistry:
    """Named system prompts: builtin defaults + file overrides.

    Overrides live in `<overrides_dir>/<key>.md` (e.g. `.agent-hub/prompts/
    agent.default.md`). A file with a builtin key replaces it; files with new
    keys define new prompt variants.
    """

    def __init__(self, overrides_dir: Path | None = None) -> None:
        self.overrides_dir = overrides_dir

    def _override_path(self, key: str) -> Path | None:
        if self.overrides_dir is None:
            return None
        return self.overrides_dir / f"{key}.md"

    def info(self, key: str) -> PromptInfo:
        path = self._override_path(key)
        if path is not None and path.is_file():
            return PromptInfo(key=key, source="override", text=path.read_text(encoding="utf-8"))
        if key in _BUILTINS:
            return PromptInfo(key=key, source="builtin", text=_BUILTINS[key])
        raise PromptNotFoundError(key)

    def get(self, key: str) -> str:
        return self.info(key).text

    def list(self) -> list[PromptInfo]:
        keys = set(_BUILTINS)
        if self.overrides_dir is not None and self.overrides_dir.is_dir():
            keys.update(p.stem for p in self.overrides_dir.glob("*.md"))
        return [self.info(key) for key in sorted(keys)]


def get_registry(settings: Settings | None = None) -> PromptRegistry:
    s = settings or get_settings()
    return PromptRegistry(overrides_dir=s.prompts_dir)
