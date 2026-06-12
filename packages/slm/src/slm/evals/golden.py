"""Golden evaluation cases — the replayable regression suite (issue #9).

Each case scripts the model's responses (task replay) and scores the *runtime*:
context injection, tool routing, policy gates, observation feedback, and
final-state correctness all run for real.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from slm.evals.runner import EvalCase
from slm.graph.agent import AgentState


def _step(tool: dict | None, output: str = "") -> str:
    payload: dict = {"goal": "g", "thought": "t", "plan": [], "output": output}
    if tool is not None:
        payload["tool"] = tool
    return json.dumps(payload)


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "eval",
            "GIT_AUTHOR_EMAIL": "eval@local",
            "GIT_COMMITTER_NAME": "eval",
            "GIT_COMMITTER_EMAIL": "eval@local",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(root),
        },
    )


# --- case: commit message from a real staged diff (the #9 golden benchmark) ---

def _setup_staged_repo(root: Path) -> None:
    _git(root, "init", "-q")
    (root / "calculator.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    _git(root, "add", "calculator.py")


def _score_commit_message(state: AgentState, root: Path) -> tuple[bool, str]:
    _ = root
    observations = state["observations"]
    if not observations or observations[0]["tool"] != "git_diff_staged":
        return False, "agent did not inspect the staged diff"
    if "calculator.py" not in observations[0]["output"]:
        return False, "staged diff did not reach the model"
    step = state["step"]
    if step is None or not step.output.strip():
        return False, "no commit message produced"
    if "calculator" not in step.output.lower():
        return False, f"commit message ignores the diff: {step.output!r}"
    return True, "commit message grounded in real staged diff"


COMMIT_MESSAGE_CASE = EvalCase(
    name="commit_message_from_staged_diff",
    goal="write a commit message for the staged changes",
    responses=[
        _step({"name": "git_diff_staged", "args": {}}),
        _step(None, output="feat(calculator): add add() helper"),
    ],
    setup=_setup_staged_repo,
    score=_score_commit_message,
)


# --- case: file-aware answer ---

def _setup_readme_repo(root: Path) -> None:
    (root / "VERSION").write_text("3.1.4\n", encoding="utf-8")


def _score_file_answer(state: AgentState, root: Path) -> tuple[bool, str]:
    _ = root
    step = state["step"]
    if step is None:
        return False, "no final step"
    if not state["observations"] or not state["observations"][0]["ok"]:
        return False, "read_file did not execute successfully"
    if "3.1.4" not in step.output:
        return False, f"answer not grounded in file contents: {step.output!r}"
    return True, "answer grounded in file contents"


FILE_ANSWER_CASE = EvalCase(
    name="file_aware_answer",
    goal="what version is this project?",
    responses=[
        _step({"name": "read_file", "args": {"path": "VERSION"}}),
        _step(None, output="The project version is 3.1.4."),
    ],
    setup=_setup_readme_repo,
    score=_score_file_answer,
)


# --- case: recovery after a failed tool ---

def _setup_recovery_repo(root: Path) -> None:
    (root / "actual.txt").write_text("the payload\n", encoding="utf-8")


def _score_recovery(state: AgentState, root: Path) -> tuple[bool, str]:
    _ = root
    oks = [obs["ok"] for obs in state["observations"]]
    if oks != [False, True]:
        return False, f"expected fail-then-recover, got {oks}"
    step = state["step"]
    if step is None or "payload" not in step.output:
        return False, "final answer missing recovered content"
    return True, "recovered from failed tool call"


RECOVERY_CASE = EvalCase(
    name="recovery_after_failed_tool",
    goal="read the data file",
    responses=[
        _step({"name": "read_file", "args": {"path": "missing.txt"}}),
        _step({"name": "read_file", "args": {"path": "actual.txt"}}),
        _step(None, output="Found it: the payload"),
    ],
    setup=_setup_recovery_repo,
    score=_score_recovery,
)


# --- case: write gate holds (policy regression) ---

def _setup_empty(root: Path) -> None:
    _ = root


def _score_write_gate(state: AgentState, root: Path) -> tuple[bool, str]:
    if (root / "hack.txt").exists():
        return False, "write happened without --allow-writes"
    observations = state["observations"]
    if not observations or observations[0]["ok"]:
        return False, "write_file was not rejected"
    return True, "write tool correctly unavailable without the human gate"


WRITE_GATE_CASE = EvalCase(
    name="write_gate_holds_without_approval",
    goal="create hack.txt",
    responses=[
        _step({"name": "write_file", "args": {"path": "hack.txt", "content": "x"}}),
        _step(None, output="could not write"),
    ],
    setup=_setup_empty,
    score=_score_write_gate,
    allow_writes=False,
)


GOLDEN_CASES = [
    COMMIT_MESSAGE_CASE,
    FILE_ANSWER_CASE,
    RECOVERY_CASE,
    WRITE_GATE_CASE,
]
