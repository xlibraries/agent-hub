from __future__ import annotations

import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from slm.context.repo import gather_repo_context
from slm.evals.replay import ReplayModel
from slm.graph.agent import AgentState, run_agent
from slm.logging.setup import get_logger

logger = get_logger(__name__)

Scorer = Callable[[AgentState, Path], tuple[bool, str]]
Setup = Callable[[Path], None]


@dataclass(frozen=True)
class EvalCase:
    """One replayable agent task with deterministic scoring."""

    name: str
    goal: str
    responses: list[str]
    setup: Setup
    score: Scorer
    allow_writes: bool = False
    max_steps: int = 5


@dataclass(frozen=True)
class EvalResult:
    name: str
    passed: bool
    detail: str
    model_calls: int
    steps_taken: int
    latency_ms: float


@dataclass
class EvalReport:
    results: list[EvalResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "results": [r.__dict__ for r in self.results],
        }


def run_case(case: EvalCase) -> EvalResult:
    with tempfile.TemporaryDirectory(prefix=f"slm-eval-{case.name}-") as tmp:
        root = Path(tmp)
        case.setup(root)
        model = ReplayModel(case.responses)
        context = gather_repo_context(root).as_prompt_block()

        started = time.perf_counter()
        state = run_agent(
            model,
            case.goal,
            context,
            workspace_root=root,
            execute_tools=True,
            allow_writes=case.allow_writes,
            max_steps=case.max_steps,
        )
        latency_ms = (time.perf_counter() - started) * 1000

        passed, detail = case.score(state, root)
        result = EvalResult(
            name=case.name,
            passed=passed,
            detail=detail,
            model_calls=model.calls,
            steps_taken=state["steps_taken"],
            latency_ms=latency_ms,
        )
        logger.info("eval_case_done", name=case.name, passed=passed, detail=detail)
        return result


def run_cases(cases: list[EvalCase]) -> EvalReport:
    report = EvalReport()
    for case in cases:
        report.results.append(run_case(case))
    return report
