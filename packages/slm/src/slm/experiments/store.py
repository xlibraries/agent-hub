from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class ExperimentRecord:
    run_id: str
    command: str
    status: str
    model: str | None
    started_at: str
    ended_at: str | None
    latency_ms: float | None
    tokens: int | None
    trace_id: str | None
    params: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class ExperimentStore:
    """Local SQLite experiment log (inspectable, no external service required)."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    command TEXT NOT NULL,
                    status TEXT NOT NULL,
                    model TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    latency_ms REAL,
                    tokens INTEGER,
                    trace_id TEXT,
                    params_json TEXT NOT NULL DEFAULT '{}',
                    metrics_json TEXT NOT NULL DEFAULT '{}',
                    error TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at);
                CREATE INDEX IF NOT EXISTS idx_runs_command ON runs(command);
                """
            )

    def start_run(
        self,
        command: str,
        *,
        model: str | None = None,
        params: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> str:
        run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, command, status, model, started_at,
                    trace_id, params_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    command,
                    "running",
                    model,
                    started_at,
                    trace_id,
                    json.dumps(params or {}),
                ),
            )
        return run_id

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        latency_ms: float | None = None,
        tokens: int | None = None,
        metrics: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        ended_at = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs SET
                    status = ?,
                    ended_at = ?,
                    latency_ms = ?,
                    tokens = ?,
                    metrics_json = ?,
                    error = ?
                WHERE run_id = ?
                """,
                (
                    status,
                    ended_at,
                    latency_ms,
                    tokens,
                    json.dumps(metrics or {}),
                    error,
                    run_id,
                ),
            )

    def list_runs(self, *, limit: int = 20, command: str | None = None) -> list[ExperimentRecord]:
        query = "SELECT * FROM runs"
        args: list[Any] = []
        if command:
            query += " WHERE command = ?"
            args.append(command)
        query += " ORDER BY started_at DESC LIMIT ?"
        args.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, args).fetchall()
        return [_row_to_record(row) for row in rows]

    def get_run(self, run_id: str) -> ExperimentRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return _row_to_record(row)


def _row_to_record(row: sqlite3.Row) -> ExperimentRecord:
    return ExperimentRecord(
        run_id=row["run_id"],
        command=row["command"],
        status=row["status"],
        model=row["model"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        latency_ms=row["latency_ms"],
        tokens=row["tokens"],
        trace_id=row["trace_id"],
        params=json.loads(row["params_json"] or "{}"),
        metrics=json.loads(row["metrics_json"] or "{}"),
        error=row["error"],
    )
