from __future__ import annotations

import json
from pathlib import Path

import pytest
from slm.evals import GOLDEN_CASES, EvalCase, ReplayModel, run_case, run_cases
from slm.graph.agent import AgentState


def test_replay_model_replays_in_order_and_repeats_last() -> None:
    model = ReplayModel(["a", "b"])
    assert model.generate([]).text == "a"
    assert model.generate([]).text == "b"
    assert model.generate([]).text == "b"
    assert model.calls == 3


def test_replay_model_rejects_empty_script() -> None:
    with pytest.raises(ValueError):
        ReplayModel([])


def test_golden_suite_all_pass() -> None:
    report = run_cases(GOLDEN_CASES)
    failures = [r for r in report.results if not r.passed]
    assert not failures, "; ".join(f"{r.name}: {r.detail}" for r in failures)
    assert report.total == len(GOLDEN_CASES)
    assert report.passed == report.total


def test_failing_case_reported_not_raised() -> None:
    def setup(root: Path) -> None:
        _ = root

    def score(state: AgentState, root: Path) -> tuple[bool, str]:
        _ = state, root
        return False, "intentional failure"

    case = EvalCase(
        name="always_fails",
        goal="g",
        responses=[json.dumps({"goal": "g", "thought": "t", "plan": [], "output": "x"})],
        setup=setup,
        score=score,
    )
    result = run_case(case)
    assert not result.passed
    assert result.detail == "intentional failure"


def test_report_serializes_to_dict() -> None:
    report = run_cases([GOLDEN_CASES[1]])  # file_aware_answer: no git needed
    data = report.as_dict()
    assert data["total"] == 1
    assert data["results"][0]["name"] == "file_aware_answer"
    assert {"passed", "detail", "model_calls", "steps_taken", "latency_ms"} <= set(
        data["results"][0]
    )
