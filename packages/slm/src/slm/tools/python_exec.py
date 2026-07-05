from __future__ import annotations

import subprocess
from pathlib import Path

from slm.config.settings import Settings
from slm.context.truncate import truncate_text
from slm.logging.setup import get_logger
from slm.safety.python_policy import PythonPolicyViolation, guard_python_exec
from slm.tools.registry import ToolResult
from slm.tools.sandbox import sandbox_env

logger = get_logger(__name__)


def run_python_exec(
    *,
    module: str | None,
    args: list[str] | None,
    code: str | None,
    workspace_root: Path,
    settings: Settings,
    allow_code: bool,
    confirmed: bool,
) -> ToolResult:
    """Run `sys.executable -m …` or `-c …` inside the workspace sandbox."""
    root = workspace_root.resolve()
    try:
        check, argv = guard_python_exec(
            module=module,
            args=args,
            code=code,
            cwd=str(root),
            allow_code=allow_code,
            confirmed=confirmed,
            max_code_chars=settings.python_exec_max_code_chars,
        )
    except PythonPolicyViolation as exc:
        return ToolResult(ok=False, output="", error=str(exc))

    logger.info(
        "python_exec_invoked",
        argv=argv,
        cwd=str(root),
        mode=check.mode,
        access=check.access,
    )

    try:
        completed = subprocess.run(
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=settings.python_exec_timeout_s,
            env=sandbox_env(root),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            ok=False,
            output="",
            error=f"python execution timed out after {settings.python_exec_timeout_s}s",
        )
    except OSError as exc:
        return ToolResult(ok=False, output="", error=str(exc))

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if stdout and stderr:
        combined = f"{stdout.rstrip()}\n--- stderr ---\n{stderr.rstrip()}"
    else:
        combined = (stdout or stderr).rstrip()

    combined = truncate_text(
        combined or "(no output)",
        settings.shell_max_output_chars,
        label="python output",
    )

    if completed.returncode != 0:
        return ToolResult(
            ok=False,
            output=combined,
            error=f"python exited {completed.returncode}",
        )
    return ToolResult(ok=True, output=combined)
