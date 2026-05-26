from langchain_core.messages import BaseMessage

from slm.graph.agent import run_planner
from slm.models.base import ChatModel, GenerationMetrics, GenerationResult


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


def _planner_response(*, task_id: str) -> str:
    return (
        '{"goal": "g", "thought": "t", "plan": [], '
        f'"task_id": "{task_id}"}}'
    )


def test_planner_replaces_placeholder_task_id() -> None:
    state = run_planner(_StubModel(_planner_response(task_id="uuid-string")), "g")
    step = state["step"]
    assert step is not None
    assert step.task_id != "uuid-string"
    assert len(step.task_id) == 36


def test_planner_preserves_valid_task_id() -> None:
    valid = "123e4567-e89b-12d3-a456-426614174000"
    state = run_planner(_StubModel(_planner_response(task_id=valid)), "g")
    step = state["step"]
    assert step is not None
    assert step.task_id == valid
