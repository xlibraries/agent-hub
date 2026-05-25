from __future__ import annotations

import json
import sys

import typer
from slm.config.settings import get_settings
from pathlib import Path

from slm.context.repo import gather_repo_context
from slm.graph.agent import run_agent, run_planner
from slm.logging.setup import configure_logging, get_logger
from slm.models.base import human_message
from slm.models.ollama import create_ollama_model
from slm.safety.kill_switch import is_kill_switch_engaged

app = typer.Typer(
    name="slm",
    help="Agent Hub CLI (slm package) — chat, agent, plan, benchmarks.",
    no_args_is_help=True,
)


def _bootstrap() -> None:
    configure_logging()


@app.callback()
def main() -> None:
    _bootstrap()


@app.command()
def chat(
    prompt: str = typer.Argument(..., help="User message"),
    model: str | None = typer.Option(None, "--model", "-m", help="Ollama model id"),
    stream: bool = typer.Option(False, "--stream", "-s", help="Stream tokens to stdout"),
) -> None:
    """Raw single-turn LLM chat (no repo context, no tools).

    For repo-aware goals (commit messages, git status, code changes), use `slm agent`.
    For structured JSON only, use `slm plan`.
    """
    log = get_logger("slm.chat")
    llm = create_ollama_model(model)
    messages = [human_message(prompt)]

    if stream:
        for chunk in llm.stream(messages):
            sys.stdout.write(chunk)
            sys.stdout.flush()
        sys.stdout.write("\n")
        return

    result = llm.generate(messages)
    log.info(
        "chat_complete",
        model=llm.model_id,
        latency_ms=result.metrics.latency_ms,
        tokens=result.metrics.total_tokens,
    )
    typer.echo(result.text)


@app.command()
def agent(
    goal: str = typer.Argument(..., help="Task goal (repo-aware planning)"),
    model: str | None = typer.Option(None, "--model", "-m"),
    cwd: Path | None = typer.Option(None, "--cwd", help="Repository root (default: current directory)"),
    output: str | None = typer.Option(None, "--output", "-o", help="Write AgentStep JSON to file"),
) -> None:
    """Agent Hub task runner: injects git workspace context, returns structured AgentStep JSON."""
    log = get_logger("slm.agent")
    if is_kill_switch_engaged():
        typer.secho("Kill switch is engaged. Aborting.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    repo = gather_repo_context(cwd)
    context_block = repo.as_prompt_block()
    llm = create_ollama_model(model)
    state = run_agent(llm, goal, context_block)

    if state.get("error"):
        typer.secho(state["error"], fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    step = state["step"]
    assert step is not None
    payload = step.model_dump(mode="json")
    text = json.dumps(payload, indent=2)
    log.info("agent_step", task_id=step.task_id, git_repo=repo.is_git_repo)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(text)
    typer.echo(text)


@app.command()
def plan(
    goal: str = typer.Argument(..., help="Objective to decompose"),
    model: str | None = typer.Option(None, "--model", "-m"),
    output: str | None = typer.Option(None, "--output", "-o", help="Write AgentStep JSON to file"),
) -> None:
    """Structured AgentStep JSON without repo context (planner-only)."""
    log = get_logger("slm.plan")
    if is_kill_switch_engaged():
        typer.secho("Kill switch is engaged. Aborting.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    llm = create_ollama_model(model)
    state = run_planner(llm, goal)

    if state.get("error"):
        typer.secho(state["error"], fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    step = state["step"]
    assert step is not None
    payload = step.model_dump(mode="json")
    text = json.dumps(payload, indent=2)
    log.info("plan_written", task_id=step.task_id)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(text)
    typer.echo(text)


@app.command()
def models() -> None:
    """Show configured default model and Ollama endpoint."""
    settings = get_settings()
    typer.echo(f"default_model={settings.default_model}")
    typer.echo(f"ollama_base_url={settings.ollama_base_url}")


@app.command("bench")
def bench_latency(
    mock: bool = typer.Option(False, "--mock", help="Run without Ollama"),
    runs: int = typer.Option(5, "--runs"),
    model: str | None = typer.Option(None, "--model", "-m"),
) -> None:
    """Run latency benchmark harness."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[5]
    script = root / "benchmarks" / "run_latency.py"
    cmd = [sys.executable, str(script), "--runs", str(runs)]
    if mock:
        cmd.append("--mock")
    if model:
        cmd.extend(["--model", model])
    subprocess.run(cmd, check=True)


@app.command()
def health() -> None:
    """Check Ollama reachability."""
    import httpx

    settings = get_settings()
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    try:
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
        typer.secho("ollama: ok", fg=typer.colors.GREEN)
    except Exception as exc:
        typer.secho(f"ollama: unreachable ({exc})", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
