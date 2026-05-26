from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


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
    output: str = Field(
        default="",
        description="User-facing answer (informational goals, commit message text, etc.).",
    )
    plan: list[str] = Field(default_factory=list)
    tool: ToolCall | None = None
    verification: Verification = Field(default_factory=Verification)
    memory_write: MemoryWrite | None = None
    metrics: StepMetrics = Field(default_factory=StepMetrics)

    model_config = {"extra": "forbid"}

    @model_validator(mode="before")
    @classmethod
    def coerce_null_fields(cls, data: Any) -> Any:
        """SLMs often emit JSON null instead of [] or {} — normalize before validation."""
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if out.get("plan") is None:
            out["plan"] = []
        if out.get("metrics") is None:
            out["metrics"] = {}
        if out.get("verification") is None:
            out["verification"] = {}
        for key in ("goal", "thought", "output", "task_id"):
            if out.get(key) is None:
                out[key] = ""
        if out.get("memory_write") is None:
            out.pop("memory_write", None)
        if out.get("tool") is None:
            out.pop("tool", None)
        return out
