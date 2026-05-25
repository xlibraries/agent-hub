from __future__ import annotations

import time
from typing import TypedDict

from langgraph.graph import END, StateGraph

from slm.logging.setup import get_logger
from slm.models.base import ChatModel, human_message, system_message
from slm.output.parser import StructuredOutputError, parse_with_retry
from slm.prompts.agent import AGENT_SYSTEM
from slm.prompts.planner import PLANNER_SYSTEM
from slm.protocol.schema import AgentStep
from slm.safety.kill_switch import assert_not_killed

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


def run_agent(model: ChatModel, goal: str, workspace_context: str) -> AgentState:
    """Agent Hub path: repo-aware system prompt + workspace snapshot."""
    return run_planner(
        model,
        goal,
        system_prompt=AGENT_SYSTEM,
        workspace_context=workspace_context,
    )
