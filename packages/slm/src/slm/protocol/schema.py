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

    @staticmethod
    def _coerce_plan_item(item: Any) -> tuple[str, dict[str, Any] | None]:
        """Normalize SLM plan entries; infer tool calls from dict-shaped steps."""
        if isinstance(item, str):
            return item, None
        if not isinstance(item, dict):
            return str(item), None

        action = item.get("action") or item.get("name") or item.get("tool")
        if isinstance(action, str) and action.strip() and action.strip().lower() not in {
            "none",
            "null",
        }:
            args = {
                key: value
                for key, value in item.items()
                if key not in {"action", "name", "tool"}
            }
            args_text = ", ".join(f"{key}={value!r}" for key, value in args.items())
            label = f"{action}({args_text})" if args_text else action
            return label, {"name": action.strip(), "args": args}

        return str(item), None

    @classmethod
    def _normalize_plan_and_tool(cls, data: dict[str, Any]) -> dict[str, Any]:
        plan = data.get("plan")
        if not isinstance(plan, list):
            return data

        normalized_plan: list[str] = []
        inferred_tool: dict[str, Any] | None = None
        for item in plan:
            step_text, tool_payload = cls._coerce_plan_item(item)
            normalized_plan.append(step_text)
            if tool_payload and inferred_tool is None:
                inferred_tool = tool_payload

        data["plan"] = normalized_plan
        if inferred_tool and not data.get("tool"):
            data["tool"] = inferred_tool
        return data

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
        return cls._normalize_plan_and_tool(out)
