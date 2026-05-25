from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(StrEnum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    TOOL = "tool"
    USER = "user"


class VerificationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


class ToolCall(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class Verification(BaseModel):
    status: VerificationStatus = VerificationStatus.SKIP
    reason: str = ""


class MemoryWrite(BaseModel):
    type: MemoryType = MemoryType.EPISODIC
    content: str = ""


class StepMetrics(BaseModel):
    latency_ms: float = 0.0
    tokens: int = 0
    cost: float = 0.0


class AgentStep(BaseModel):
    """Canonical agent protocol — one orchestration step."""

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal: str = ""
    thought: str = ""
    plan: list[str] = Field(default_factory=list)
    tool: ToolCall | None = None
    verification: Verification = Field(default_factory=Verification)
    memory_write: MemoryWrite | None = None
    metrics: StepMetrics = Field(default_factory=StepMetrics)

    model_config = {"extra": "forbid"}
