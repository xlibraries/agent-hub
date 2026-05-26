from pathlib import Path

from slm.experiments.store import ExperimentStore


def test_experiment_store_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    store = ExperimentStore(db)
    run_id = store.start_run("chat", model="qwen2.5-coder:7b", params={"prompt_len": 12})
    store.finish_run(
        run_id,
        status="ok",
        latency_ms=42.5,
        tokens=100,
        metrics={"latency_ms": 42.5, "tokens": 100},
    )
    record = store.get_run(run_id)
    assert record is not None
    assert record.command == "chat"
    assert record.status == "ok"
    assert record.latency_ms == 42.5
    assert record.tokens == 100

    listed = store.list_runs(limit=5)
    assert len(listed) == 1
    assert listed[0].run_id == run_id
