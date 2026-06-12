# Benchmarks

Harnesses for latency, tool correctness, and regression tracking.

```bash
uv run python benchmarks/run_latency.py --mock
uv run slm bench --mock                  # CLI alias

uv run python benchmarks/run_evals.py    # golden eval suite (task replay)
uv run python benchmarks/run_evals.py --json
```

## Golden eval suite

`run_evals.py` runs the replayable cases in `slm.evals.golden` against the
real executor loop (context injection, tool routing, policy gates) with a
deterministic `ReplayModel` — no Ollama required. Any failure exits non-zero,
so the CI step doubles as agent regression testing.

Current cases: commit message grounded in a real staged diff, file-aware
answers, recovery after a failed tool, and write-gate enforcement.
