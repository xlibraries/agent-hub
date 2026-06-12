from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

from slm.logging.setup import get_logger
from slm.models.base import ChatModel, human_message, system_message
from slm.output.parser import StructuredOutputError, parse_with_retry
from slm.prompts.agent import AGENT_SYSTEM
from slm.prompts.planner import PLANNER_SYSTEM
from slm.protocol.schema import AgentStep, Verification, VerificationStatus
from slm.safety.kill_switch import assert_not_killed
from slm.telemetry.tracing import start_span
from slm.tools.builtin import AVAILABLE_TOOLS_DOC, create_default_registry

logger = get_logger(__name__)


class AgentState(TypedDict):
    goal: str
    step: AgentStep | None
    raw_response: str
    error: str | None
    tool_output: str | None


def _initial_state(goal: str) -> AgentState:
    return {
        "goal": goal,
        "step": None,
        "raw_response": "",
        "error": None,
        "tool_output": None,
    }


def build_planner_graph(
    model: ChatModel,
    *,
    system_prompt: str = PLANNER_SYSTEM,
    workspace_context: str | None = None,
    workspace_root: Path | None = None,
    execute_tools: bool = False,
):
    """LangGraph: plan → (optional: execute → verify) → end."""

    effective_prompt = system_prompt
    if execute_tools:
        effective_prompt = f"{system_prompt.rstrip()}\n\n{AVAILABLE_TOOLS_DOC}"

    def plan_node(state: AgentState) -> AgentState:
        assert_not_killed()
        with start_span("slm.graph.plan", attributes={"slm.has_context": bool(workspace_context)}):
            return _plan_node_impl(state, effective_prompt)

    def _plan_node_impl(state: AgentState, prompt: str) -> AgentState:
        started = time.perf_counter()
        user_content = state["goal"]
        if workspace_context:
            user_content = f"{workspace_context}\n\n## User goal\n{state['goal']}"
        messages = [
            system_message(prompt),
            human_message(user_content),
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
            latency_ms=latency_ms,
            tokens=step.metrics.tokens,
        )
        return {**state, "step": step, "raw_response": result.text, "error": None}

    def execute_node(state: AgentState) -> AgentState:
        assert_not_killed()
        step = state["step"]
        if step is None or step.tool is None:
            return {**state, "error": "no tool to execute", "tool_output": None}

        root = (workspace_root or Path.cwd()).resolve()
        registry = create_default_registry(root)
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
        )
        if result.ok:
            return {**state, "tool_output": result.output, "error": None}
        return {**state, "tool_output": None, "error": result.error or "tool failed"}

    def verify_node(state: AgentState) -> AgentState:
        step = state["step"]
        if step is None:
            return state

        if state.get("error"):
            step.verification = Verification(
                status=VerificationStatus.FAIL,
                reason=state["error"] or "tool failed",
            )
        elif not state.get("tool_output"):
            step.verification = Verification(
                status=VerificationStatus.FAIL,
                reason="tool produced no output",
            )
        else:
            step.verification = Verification(
                status=VerificationStatus.PASS,
                reason="tool executed successfully",
            )

        return {**state, "step": step}

    def route_after_plan(state: AgentState) -> Literal["execute", "__end__"]:
        if not execute_tools or workspace_root is None:
            return "__end__"
        step = state.get("step")
        if step is not None and step.tool is not None:
            return "execute"
        return "__end__"

    graph = StateGraph(AgentState)
    graph.add_node("plan", plan_node)
    graph.set_entry_point("plan")

    if execute_tools and workspace_root is not None:
        graph.add_node("execute", execute_node)
        graph.add_node("verify", verify_node)
        graph.add_conditional_edges(
            "plan",
            route_after_plan,
            {"execute": "execute", "__end__": END},
        )
        graph.add_edge("execute", "verify")
        graph.add_edge("verify", END)
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
) -> AgentState:
    app = build_planner_graph(
        model,
        system_prompt=system_prompt,
        workspace_context=workspace_context,
        workspace_root=workspace_root,
        execute_tools=execute_tools,
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
) -> AgentState:
    """Agent Hub path: repo-aware system prompt + workspace snapshot."""
    return run_planner(
        model,
        goal,
        system_prompt=system_prompt,
        workspace_context=workspace_context,
        workspace_root=workspace_root,
        execute_tools=execute_tools,
    )
