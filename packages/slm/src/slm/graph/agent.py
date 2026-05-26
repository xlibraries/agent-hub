from __future__ import annotations

import time
import uuid
from typing import TypedDict

from langgraph.graph import END, StateGraph

from slm.logging.setup import get_logger
from slm.models.base import ChatModel, human_message, system_message
from slm.output.parser import StructuredOutputError, parse_with_retry
from slm.prompts.agent import AGENT_SYSTEM
from slm.prompts.planner import PLANNER_SYSTEM
from slm.protocol.schema import AgentStep
from slm.safety.kill_switch import assert_not_killed
from slm.telemetry.tracing import start_span

logger = get_logger(__name__)


class AgentState(TypedDict):
    goal: str
    step: AgentStep | None
    raw_response: str
    error: str | None


def build_planner_graph(
    model: ChatModel,
    *,
    system_prompt: str = PLANNER_SYSTEM,
    workspace_context: str | None = None,
):
    """Minimal LangGraph: plan → (future: execute tools) → end."""

    def plan_node(state: AgentState) -> AgentState:
        assert_not_killed()
        with start_span("slm.graph.plan", attributes={"slm.has_context": bool(workspace_context)}):
            return _plan_node_impl(state)

    def _plan_node_impl(state: AgentState) -> AgentState:
        started = time.perf_counter()
        user_content = state["goal"]
        if workspace_context:
            user_content = f"{workspace_context}\n\n## User goal\n{state['goal']}"
        messages = [
            system_message(system_prompt),
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

    graph = StateGraph(AgentState)
    graph.add_node("plan", plan_node)
    graph.set_entry_point("plan")
    graph.add_edge("plan", END)
    return graph.compile()


def run_planner(
    model: ChatModel,
    goal: str,
    *,
    system_prompt: str = PLANNER_SYSTEM,
    workspace_context: str | None = None,
) -> AgentState:
    app = build_planner_graph(
        model,
        system_prompt=system_prompt,
        workspace_context=workspace_context,
    )
    return app.invoke({"goal": goal, "step": None, "raw_response": "", "error": None})


def _normalize_task_id(task_id: str) -> str:
    placeholder = task_id.strip().lower().replace(" ", "")
    if placeholder in {"", "uuid-string", "uuid", "task_id"}:
        return str(uuid.uuid4())
    try:
        uuid.UUID(task_id)
        return task_id
    except ValueError:
        return str(uuid.uuid4())


def run_agent(model: ChatModel, goal: str, workspace_context: str) -> AgentState:
    """Agent Hub path: repo-aware system prompt + workspace snapshot."""
    return run_planner(
        model,
        goal,
        system_prompt=AGENT_SYSTEM,
        workspace_context=workspace_context,
    )
