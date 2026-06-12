from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import BaseMessage
from slm.graph.agent import run_planner
from slm.models.base import ChatModel, GenerationMetrics, GenerationResult
from slm.protocol.schema import VerificationStatus


class _StubModel(ChatModel):
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    @property
    def model_id(self) -> str:
        return "stub"

    def generate(
        self, messages: list[BaseMessage], *, temperature: float = 0.2
    ) -> GenerationResult:
        _ = messages, temperature
        return GenerationResult(text=self._response_text, metrics=GenerationMetrics())


def test_execute_loop_runs_read_file(tmp_path: Path) -> None:
    (tmp_path / "target.txt").write_text("file-aware content\n", encoding="utf-8")
    response = json.dumps(
        {
            "goal": "read target",
            "thought": "use read_file",
            "plan": ["read file"],
            "tool": {"name": "read_file", "args": {"path": "target.txt"}},
        }
    )
    state = run_planner(
        _StubModel(response),
        "read target",
        workspace_root=tmp_path,
        execute_tools=True,
    )
    step = state["step"]
    assert step is not None
    assert state["error"] is None
    assert state["tool_output"] == "file-aware content\n"
    assert step.verification.status == VerificationStatus.PASS
    assert step.output == ""


def test_execute_loop_skipped_without_flag(tmp_path: Path) -> None:
    (tmp_path / "target.txt").write_text("hidden\n", encoding="utf-8")
    response = json.dumps(
        {
            "goal": "read target",
            "thought": "use read_file",
            "tool": {"name": "read_file", "args": {"path": "target.txt"}},
        }
    )
    state = run_planner(
        _StubModel(response),
        "read target",
        workspace_root=tmp_path,
        execute_tools=False,
    )
    step = state["step"]
    assert step is not None
    assert state["tool_output"] is None
    assert step.verification.status == VerificationStatus.SKIP


def test_execute_loop_marks_verification_fail_on_unknown_tool(tmp_path: Path) -> None:
    response = json.dumps(
        {
            "goal": "bad tool",
            "thought": "try unknown",
            "tool": {"name": "unknown_tool", "args": {}},
        }
    )
    state = run_planner(
        _StubModel(response),
        "bad tool",
        workspace_root=tmp_path,
        execute_tools=True,
    )
    step = state["step"]
    assert step is not None
    assert state["error"] is not None
    assert step.verification.status == VerificationStatus.FAIL
