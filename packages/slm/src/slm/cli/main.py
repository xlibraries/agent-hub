from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from slm.config.settings import get_settings
from slm.context.repo import gather_repo_context
from slm.experiments.tracker import get_tracker
from slm.graph.agent import run_agent, run_planner
from slm.logging.setup import configure_logging, get_logger
from slm.models.base import human_message
from slm.models.ollama import create_ollama_model
from slm.safety.kill_switch import is_kill_switch_engaged
from slm.telemetry.setup import configure_telemetry

app = typer.Typer(
    name="slm",
    help="Agent Hub CLI (slm package) — chat, agent, plan, benchmarks.",
    no_args_is_help=True,
)


def _bootstrap() -> None:
    configure_logging()
    configure_telemetry()


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
    tracker = get_tracker()

    with tracker.track("chat", model=llm.model_id, params={"prompt_len": len(prompt)}) as run:
        if stream:
            for chunk in llm.stream(messages):
                sys.stdout.write(chunk)
                sys.stdout.flush()
            sys.stdout.write("\n")
            return

        result = llm.generate(messages)
        run.set_metrics(latency_ms=result.metrics.latency_ms, tokens=result.metrics.total_tokens)
        log.info(
            "chat_complete",
            model=llm.model_id,
            latency_ms=result.metrics.latency_ms,
            tokens=result.metrics.total_tokens,
            run_id=run.run_id or None,
        )
        typer.echo(result.text)


@app.command()
def agent(
    goal: str = typer.Argument(..., help="Task goal (repo-aware planning)"),
    model: str | None = typer.Option(None, "--model", "-m"),
    cwd: Path | None = typer.Option(
        None, "--cwd", help="Repository root (default: current directory)"
    ),
    output: str | None = typer.Option(None, "--output", "-o", help="Write AgentStep JSON to file"),
    brief: bool = typer.Option(
        False,
        "--brief",
        help="Print memory_write.content (or thought) before JSON",
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Run read-only tools requested in the plan (read_file, list_dir, grep_text, git_*)",
    ),
) -> None:
    """Agent Hub task runner: injects workspace snapshot, returns structured AgentStep JSON."""
    log = get_logger("slm.agent")
    if is_kill_switch_engaged():
        typer.secho("Kill switch is engaged. Aborting.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    root = (cwd or Path.cwd()).resolve()
    repo = gather_repo_context(root)
    context_block = repo.as_prompt_block()
    llm = create_ollama_model(model)
    tracker = get_tracker()

    with tracker.track(
        "agent",
        model=llm.model_id,
        params={
            "goal_len": len(goal),
            "git_repo": repo.is_git_repo,
            "has_readme": bool(repo.readme),
            "execute": execute,
        },
    ) as run:
        state = run_agent(
            llm,
            goal,
            context_block,
            workspace_root=root,
            execute_tools=execute,
        )

        if state.get("error"):
            typer.secho(state["error"], fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

        step = state["step"]
        assert step is not None
        run.set_metrics(latency_ms=step.metrics.latency_ms, tokens=step.metrics.tokens)
        payload = step.model_dump(mode="json")
        tool_output = state.get("tool_output")
        if tool_output is not None:
            payload["tool_output"] = tool_output
        text = json.dumps(payload, indent=2)
        log.info(
            "agent_step",
            task_id=step.task_id,
            git_repo=repo.is_git_repo,
            run_id=run.run_id or None,
        )

    if brief:
        summary = (
            step.output.strip()
            or (tool_output or "").strip()
            or (step.memory_write.content if step.memory_write else "")
            or step.thought
        )
        if summary.strip():
            typer.echo(summary.strip())
            typer.echo("")

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(text)
    typer.echo(text)


@app.command()
def plan(
    goal: str = typer.Argument(..., help="Objective to decompose"),
    model: str | None = typer.Option(None, "--model", "-m"),
    cwd: Path | None = typer.Option(
        None, "--cwd", help="Workspace root for optional repo context"
    ),
    repo: bool = typer.Option(
        False,
        "--repo",
        help="Inject workspace snapshot (README, tree, git). Implied when --cwd is set.",
    ),
    output: str | None = typer.Option(None, "--output", "-o", help="Write AgentStep JSON to file"),
) -> None:
    """Structured AgentStep JSON; add --repo or --cwd for workspace context."""
    log = get_logger("slm.plan")
    if is_kill_switch_engaged():
        typer.secho("Kill switch is engaged. Aborting.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    llm = create_ollama_model(model)
    tracker = get_tracker()
    workspace_context = None
    if repo or cwd is not None:
        workspace_context = gather_repo_context(cwd).as_prompt_block()

    with tracker.track(
        "plan",
        model=llm.model_id,
        params={"goal_len": len(goal), "with_repo": workspace_context is not None},
    ) as run:
        state = run_planner(llm, goal, workspace_context=workspace_context)

        if state.get("error"):
            typer.secho(state["error"], fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

        step = state["step"]
        assert step is not None
        run.set_metrics(latency_ms=step.metrics.latency_ms, tokens=step.metrics.tokens)
        payload = step.model_dump(mode="json")
        text = json.dumps(payload, indent=2)
        log.info("plan_written", task_id=step.task_id, run_id=run.run_id or None)

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


experiments_app = typer.Typer(help="Inspect local experiment runs (SQLite).")
app.add_typer(experiments_app, name="experiments")


@experiments_app.command("list")
def experiments_list(
    limit: int = typer.Option(20, "--limit", "-n"),
    command: str | None = typer.Option(None, "--command", "-c"),
) -> None:
    """List recent experiment runs."""
    from slm.experiments.store import ExperimentStore

    store = ExperimentStore(get_settings().experiments_db_path)
    rows = store.list_runs(limit=limit, command=command)
    if not rows:
        typer.echo("No experiment runs recorded.")
        return
    for row in rows:
        typer.echo(
            f"{row.run_id[:8]}…  {row.command:6}  {row.status:7}  "
            f"{row.latency_ms or 0:.0f}ms  tokens={row.tokens or 0}  {row.started_at}"
        )


@experiments_app.command("show")
def experiments_show(run_id: str = typer.Argument(..., help="Run UUID (prefix ok)")) -> None:
    """Show one experiment run as JSON."""
    from slm.experiments.store import ExperimentStore

    store = ExperimentStore(get_settings().experiments_db_path)
    rows = store.list_runs(limit=200)
    match = next((r for r in rows if r.run_id.startswith(run_id)), None)
    if match is None:
        typer.secho(f"No run matching {run_id!r}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    typer.echo(json.dumps(match.__dict__, indent=2, default=str))


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
