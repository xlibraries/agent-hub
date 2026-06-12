from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import BaseMessage
from slm.graph.agent import run_planner
from slm.models.base import ChatModel, GenerationMetrics, GenerationResult
from slm.protocol.schema import VerificationStatus


class _SequencedModel(ChatModel):
    """Returns scripted responses in order; repeats the last one when exhausted."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.calls = 0

    @property
    def model_id(self) -> str:
        return "stub"

    def generate(
        self, messages: list[BaseMessage], *, temperature: float = 0.2
    ) -> GenerationResult:
        _ = temperature
        index = min(self.calls, len(self._responses) - 1)
        self.calls += 1
        self.last_messages = messages
        return GenerationResult(text=self._responses[index], metrics=GenerationMetrics())


def _step(tool: dict | None, output: str = "") -> str:
    payload: dict = {"goal": "g", "thought": "t", "plan": [], "output": output}
    if tool is not None:
        payload["tool"] = tool
    return json.dumps(payload)


def test_loop_executes_then_finishes_on_no_tool(tmp_path: Path) -> None:
    (tmp_path / "target.txt").write_text("file-aware content\n", encoding="utf-8")
    model = _SequencedModel(
        [
            _step({"name": "read_file", "args": {"path": "target.txt"}}),
            _step(None, output="The file says: file-aware content"),
        ]
    )
    state = run_planner(
        model, "read target", workspace_root=tmp_path, execute_tools=True
    )
    assert model.calls == 2
    assert len(state["observations"]) == 1
    assert state["observations"][0]["ok"] is True
    assert "file-aware content" in state["observations"][0]["output"]
    step = state["step"]
    assert step is not None
    assert step.output == "The file says: file-aware content"


def test_loop_feeds_observations_back_to_model(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    model = _SequencedModel(
        [
            _step({"name": "read_file", "args": {"path": "a.txt"}}),
            _step(None, output="done"),
        ]
    )
    run_planner(model, "read a", workspace_root=tmp_path, execute_tools=True)
    second_call_content = str(model.last_messages[-1].content)
    assert "Tool results so far" in second_call_content
    assert "alpha" in second_call_content


def test_loop_respects_step_budget(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("x\n", encoding="utf-8")
    model = _SequencedModel([_step({"name": "read_file", "args": {"path": "x.txt"}})])
    state = run_planner(
        model,
        "loop forever",
        workspace_root=tmp_path,
        execute_tools=True,
        max_steps=2,
    )
    assert state["steps_taken"] == 2
    assert len(state["observations"]) == 2


def test_failed_tool_recorded_and_loop_can_recover(tmp_path: Path) -> None:
    (tmp_path / "real.txt").write_text("real\n", encoding="utf-8")
    model = _SequencedModel(
        [
            _step({"name": "read_file", "args": {"path": "missing.txt"}}),
            _step({"name": "read_file", "args": {"path": "real.txt"}}),
            _step(None, output="recovered"),
        ]
    )
    state = run_planner(model, "read", workspace_root=tmp_path, execute_tools=True)
    assert [obs["ok"] for obs in state["observations"]] == [False, True]
    assert state["error"] is None
    step = state["step"]
    assert step is not None
    assert step.output == "recovered"


def test_execute_skipped_without_flag(tmp_path: Path) -> None:
    (tmp_path / "target.txt").write_text("hidden\n", encoding="utf-8")
    model = _SequencedModel(
        [_step({"name": "read_file", "args": {"path": "target.txt"}})]
    )
    state = run_planner(model, "read", workspace_root=tmp_path, execute_tools=False)
    assert model.calls == 1
    assert state["observations"] == []
    step = state["step"]
    assert step is not None
    assert step.verification.status == VerificationStatus.SKIP


def test_write_tool_unavailable_without_allow_writes(tmp_path: Path) -> None:
    model = _SequencedModel(
        [
            _step({"name": "write_file", "args": {"path": "new.txt", "content": "hi"}}),
            _step(None, output="gave up"),
        ]
    )
    state = run_planner(model, "write", workspace_root=tmp_path, execute_tools=True)
    assert state["observations"][0]["ok"] is False
    assert "unknown tool" in state["observations"][0]["error"]
    assert not (tmp_path / "new.txt").exists()


def test_write_tool_works_with_allow_writes(tmp_path: Path) -> None:
    model = _SequencedModel(
        [
            _step({"name": "write_file", "args": {"path": "new.txt", "content": "hi"}}),
            _step(None, output="wrote it"),
        ]
    )
    state = run_planner(
        model,
        "write",
        workspace_root=tmp_path,
        execute_tools=True,
        allow_writes=True,
    )
    assert state["observations"][0]["ok"] is True
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "hi"
