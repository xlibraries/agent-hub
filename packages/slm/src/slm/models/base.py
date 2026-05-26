from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from slm.telemetry.tracing import start_span


@dataclass
class GenerationMetrics:
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class GenerationResult:
    text: str
    metrics: GenerationMetrics = field(default_factory=GenerationMetrics)


class ChatModel(ABC):
    """Model abstraction — swap Ollama, vLLM, or remote APIs behind one interface."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        ...

    @abstractmethod
    def generate(
        self, messages: list[BaseMessage], *, temperature: float = 0.2
    ) -> GenerationResult:
        ...

    def stream(
        self, messages: list[BaseMessage], *, temperature: float = 0.2
    ) -> Iterator[str]:
        result = self.generate(messages, temperature=temperature)
        yield result.text

    async def agenerate(
        self, messages: list[BaseMessage], *, temperature: float = 0.2
    ) -> GenerationResult:
        return self.generate(messages, temperature=temperature)

    async def astream(
        self, messages: list[BaseMessage], *, temperature: float = 0.2
    ) -> AsyncIterator[str]:
        for chunk in self.stream(messages, temperature=temperature):
            yield chunk


class LangChainChatModelAdapter(ChatModel):
    """Wraps a LangChain chat model with token/latency accounting."""

    def __init__(self, model: BaseChatModel, model_id: str) -> None:
        self._model = model
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def _runnable(self, temperature: float) -> BaseChatModel:
        """Bind temperature on the model; Ollama rejects temperature in invoke kwargs."""
        default = getattr(self._model, "temperature", None)
        if default is not None and float(default) == temperature:
            return self._model
        return self._model.bind(temperature=temperature)

    def generate(
        self, messages: list[BaseMessage], *, temperature: float = 0.2
    ) -> GenerationResult:
        with start_span(
            "slm.model.generate",
            attributes={"slm.model_id": self.model_id, "slm.message_count": len(messages)},
        ):
            started = time.perf_counter()
            response: AIMessage = self._runnable(temperature).invoke(messages)
            latency_ms = (time.perf_counter() - started) * 1000

        usage = getattr(response, "usage_metadata", None) or {}
        prompt_tokens = int(usage.get("input_tokens", 0) or 0)
        completion_tokens = int(usage.get("output_tokens", 0) or 0)

        return GenerationResult(
            text=str(response.content),
            metrics=GenerationMetrics(
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
        )

    def stream(self, messages: list[BaseMessage], *, temperature: float = 0.2) -> Iterator[str]:
        started = time.perf_counter()
        chunks: list[str] = []
        for chunk in self._runnable(temperature).stream(messages):
            if chunk.content:
                text = str(chunk.content)
                chunks.append(text)
                yield text
        _ = (time.perf_counter() - started) * 1000  # stream latency logged at call site


def system_message(content: str) -> SystemMessage:
    return SystemMessage(content=content)


def human_message(content: str) -> HumanMessage:
    return HumanMessage(content=content)
