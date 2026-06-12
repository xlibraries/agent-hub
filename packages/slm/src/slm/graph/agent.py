from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from slm.config.settings import get_settings
from slm.logging.setup import get_logger
from slm.models.base import ChatModel, human_message, system_message
from slm.output.parser import StructuredOutputError, parse_with_retry
from slm.prompts.agent import AGENT_SYSTEM
from slm.prompts.planner import PLANNER_SYSTEM
from slm.protocol.schema import AgentStep, Verification, VerificationStatus
from slm.safety.kill_switch import assert_not_killed
from slm.telemetry.tracing import start_span
from slm.tools.builtin import build_tools_doc, create_default_registry

logger = get_logger(__name__)


class AgentState(TypedDict):
    goal: str
    step: AgentStep | None
    raw_response: str
    error: str | None
    tool_output: str | None
    observations: list[dict[str, Any]]
    steps_taken: int


def _initial_state(goal: str) -> AgentState:
    return {
        "goal": goal,
        "step": None,
        "raw_response": "",
        "error": None,
        "tool_output": None,
        "observations": [],
        "steps_taken": 0,
    }


def _observations_block(observations: list[dict[str, Any]]) -> str:
    lines = ["## Tool results so far (oldest first)"]
    for index, obs in enumerate(observations, start=1):
        status = "ok" if obs["ok"] else f"FAILED: {obs.get('error', '')}"
        lines.append(f"### step {index}: {obs['tool']}({json.dumps(obs['args'])}) — {status}")
        if obs.get("output"):
            lines.append(obs["output"])
    lines.append(
        "\nIf the goal is complete, respond with tool name \"none\" and the final "
        "answer in `output`. Otherwise request the next tool."
    )
    return "\n".join(lines)


def build_planner_graph(
    model: ChatModel,
    *,
    system_prompt: str = PLANNER_SYSTEM,
    workspace_context: str | None = None,
    workspace_root: Path | None = None,
    execute_tools: bool = False,
    allow_writes: bool = False,
    max_steps: int | None = None,
):
    """LangGraph: plan → (execute → verify → plan …) → end.

    Without `execute_tools` the graph is plan-only. With it, tool requests are
    executed and results fed back to the model until it stops requesting tools
    or the step budget is exhausted.
    """

    budget = max_steps if max_steps is not None else get_settings().executor_max_steps

    effective_prompt = system_prompt
    if execute_tools:
        effective_prompt = f"{system_prompt.rstrip()}\n\n{build_tools_doc(allow_writes)}"

    registry = None
    if execute_tools and workspace_root is not None:
        registry = create_default_registry(
            workspace_root.resolve(), allow_writes=allow_writes
        )

    def plan_node(state: AgentState) -> AgentState:
        assert_not_killed()
        with start_span(
            "slm.graph.plan",
            attributes={
                "slm.has_context": bool(workspace_context),
                "slm.steps_taken": state["steps_taken"],
            },
        ):
            return _plan_node_impl(state, effective_prompt)

    def _plan_node_impl(state: AgentState, prompt: str) -> AgentState:
        started = time.perf_counter()
        parts: list[str] = []
        if workspace_context:
            parts.append(workspace_context)
        if state["observations"]:
            parts.append(_observations_block(state["observations"]))
        parts.append(f"## User goal\n{state['goal']}")
        messages = [
            system_message(prompt),
            human_message("\n\n".join(parts)),
        ]
        result = model.generate(messages)
        latency_ms = (time.perf_counter() - started) * 1000

        try:
            step = parse_with_retry(result.text, AgentStep)
        except StructuredOutputError as exc:
            logger.error("plan_parse_failed", error=str(exc))
            return {**state, "raw_response": result.text, "error": str(exc)}

        if step.goal == "":
            step.goal = state["goal"]
        step.task_id = _normalize_task_id(step.task_id)
        step.metrics.latency_ms = latency_ms
        step.metrics.tokens = result.metrics.total_tokens

        tool = step.tool
        if tool and tool.name in {"", "none", "null"}:
            step.tool = None

        logger.info(
            "plan_complete",
            task_id=step.task_id,
            steps=len(step.plan),
            steps_taken=state["steps_taken"],
            latency_ms=latency_ms,
            tokens=step.metrics.tokens,
        )
        return {**state, "step": step, "raw_response": result.text, "error": None}

    def execute_node(state: AgentState) -> AgentState:
        assert_not_killed()
        step = state["step"]
        if step is None or step.tool is None or registry is None:
            return {**state, "error": "no tool to execute", "tool_output": None}

        with start_span(
            "slm.graph.execute",
            attributes={"slm.tool": step.tool.name},
        ):
            result = registry.execute(step.tool.name, step.tool.args)

        logger.info(
            "tool_execute",
            task_id=step.task_id,
            tool=step.tool.name,
            ok=result.ok,
            error=result.error or None,
        )
        if result.ok:
            return {**state, "tool_output": result.output, "error": None}
        return {**state, "tool_output": None, "error": result.error or "tool failed"}

    def verify_node(state: AgentState) -> AgentState:
        step = state["step"]
        if step is None:
            return state

        tool_error = state.get("error")
        tool_output = state.get("tool_output")
        if tool_error:
            step.verification = Verification(
                status=VerificationStatus.FAIL,
                reason=tool_error,
            )
        elif not tool_output:
            step.verification = Verification(
                status=VerificationStatus.FAIL,
                reason="tool produced no output",
            )
        else:
            step.verification = Verification(
                status=VerificationStatus.PASS,
                reason="tool executed successfully",
            )

        observation = {
            "tool": step.tool.name if step.tool else "",
            "args": step.tool.args if step.tool else {},
            "ok": step.verification.status == VerificationStatus.PASS,
            "output": tool_output or "",
            "error": tool_error or "",
        }
        return {
            **state,
            "step": step,
            # Tool failures are recorded as observations so the model can
            # correct course; only parse failures surface as state errors.
            "error": None,
            "observations": [*state["observations"], observation],
            "steps_taken": state["steps_taken"] + 1,
        }

    def route_after_plan(state: AgentState) -> Literal["execute", "__end__"]:
        if not execute_tools or registry is None:
            return "__end__"
        if state.get("error"):
            return "__end__"
        step = state.get("step")
        if step is not None and step.tool is not None and state["steps_taken"] < budget:
            return "execute"
        return "__end__"

    def route_after_verify(state: AgentState) -> Literal["plan", "__end__"]:
        if state["steps_taken"] >= budget:
            logger.info("executor_budget_exhausted", steps_taken=state["steps_taken"])
            return "__end__"
        return "plan"

    graph = StateGraph(AgentState)
    graph.add_node("plan", plan_node)
    graph.set_entry_point("plan")

    if execute_tools and registry is not None:
        graph.add_node("execute", execute_node)
        graph.add_node("verify", verify_node)
        graph.add_conditional_edges(
            "plan",
            route_after_plan,
            {"execute": "execute", "__end__": END},
        )
        graph.add_edge("execute", "verify")
        graph.add_conditional_edges(
            "verify",
            route_after_verify,
            {"plan": "plan", "__end__": END},
        )
    else:
        graph.add_edge("plan", END)

    return graph.compile()


def run_planner(
    model: ChatModel,
    goal: str,
    *,
    system_prompt: str = PLANNER_SYSTEM,
    workspace_context: str | None = None,
    workspace_root: Path | None = None,
    execute_tools: bool = False,
    allow_writes: bool = False,
    max_steps: int | None = None,
) -> AgentState:
    app = build_planner_graph(
        model,
        system_prompt=system_prompt,
        workspace_context=workspace_context,
        workspace_root=workspace_root,
        execute_tools=execute_tools,
        allow_writes=allow_writes,
        max_steps=max_steps,
    )
    return app.invoke(_initial_state(goal))


def _normalize_task_id(task_id: str) -> str:
    placeholder = task_id.strip().lower().replace(" ", "")
    if placeholder in {"", "uuid-string", "uuid", "task_id"}:
        return str(uuid.uuid4())
    try:
        uuid.UUID(task_id)
        return task_id
    except ValueError:
        return str(uuid.uuid4())


def run_agent(
    model: ChatModel,
    goal: str,
    workspace_context: str,
    *,
    system_prompt: str = AGENT_SYSTEM,
    workspace_root: Path | None = None,
    execute_tools: bool = False,
    allow_writes: bool = False,
    max_steps: int | None = None,
) -> AgentState:
    """Agent Hub path: repo-aware system prompt + workspace snapshot."""
    return run_planner(
        model,
        goal,
        system_prompt=system_prompt,
        workspace_context=workspace_context,
        workspace_root=workspace_root,
        execute_tools=execute_tools,
        allow_writes=allow_writes,
        max_steps=max_steps,
    )
