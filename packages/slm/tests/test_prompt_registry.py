from __future__ import annotations

from pathlib import Path

import pytest
from slm.prompts.agent import AGENT_SYSTEM
from slm.prompts.planner import PLANNER_SYSTEM
from slm.prompts.registry import PromptNotFoundError, PromptRegistry


def test_builtin_prompts_resolve_without_overrides_dir() -> None:
    registry = PromptRegistry(overrides_dir=None)
    assert registry.get("agent.default") == AGENT_SYSTEM
    assert registry.get("planner.default") == PLANNER_SYSTEM


def test_unknown_key_raises() -> None:
    registry = PromptRegistry(overrides_dir=None)
    with pytest.raises(PromptNotFoundError):
        registry.get("does.not.exist")


def test_override_file_wins_over_builtin(tmp_path: Path) -> None:
    (tmp_path / "agent.default.md").write_text("OVERRIDDEN PROMPT", encoding="utf-8")
    registry = PromptRegistry(overrides_dir=tmp_path)
    info = registry.info("agent.default")
    assert info.source == "override"
    assert info.text == "OVERRIDDEN PROMPT"
    # untouched key still builtin
    assert registry.info("planner.default").source == "builtin"


def test_file_only_key_defines_new_variant(tmp_path: Path) -> None:
    (tmp_path / "agent.concise.md").write_text("Be brief.", encoding="utf-8")
    registry = PromptRegistry(overrides_dir=tmp_path)
    assert registry.get("agent.concise") == "Be brief."


def test_list_includes_builtins_and_overrides(tmp_path: Path) -> None:
    (tmp_path / "agent.concise.md").write_text("Be brief.", encoding="utf-8")
    registry = PromptRegistry(overrides_dir=tmp_path)
    by_key = {info.key: info.source for info in registry.list()}
    assert by_key["agent.default"] == "builtin"
    assert by_key["planner.default"] == "builtin"
    assert by_key["agent.concise"] == "override"


def test_missing_overrides_dir_is_fine(tmp_path: Path) -> None:
    registry = PromptRegistry(overrides_dir=tmp_path / "nope")
    assert registry.get("agent.default") == AGENT_SYSTEM
    assert {i.key for i in registry.list()} == {"agent.default", "planner.default"}
