from __future__ import annotations

from langchain_core.messages import BaseMessage

from slm.models.base import ChatModel, GenerationMetrics, GenerationResult


class ReplayModel(ChatModel):
    """Deterministic model that replays scripted responses.

    Powers the task-replay evaluation system: agent runs become reproducible
    regression tests with no LLM dependency. Repeats the last response when
    the script is exhausted.
    """

    def __init__(self, responses: list[str], *, model_id: str = "replay") -> None:
        if not responses:
            raise ValueError("ReplayModel requires at least one scripted response")
        self._responses = responses
        self._model_id = model_id
        self.calls = 0
        self.transcripts: list[list[BaseMessage]] = []

    @property
    def model_id(self) -> str:
        return self._model_id

    def generate(
        self, messages: list[BaseMessage], *, temperature: float = 0.2
    ) -> GenerationResult:
        _ = temperature
        index = min(self.calls, len(self._responses) - 1)
        self.calls += 1
        self.transcripts.append(list(messages))
        return GenerationResult(text=self._responses[index], metrics=GenerationMetrics())
