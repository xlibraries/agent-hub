from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


@dataclass(frozen=True)
class MessageRecord:
    session: str
    role: str
    content: str
    command: str
    model: str | None
    tokens: int | None
    latency_ms: float | None
    created_at: str


@dataclass(frozen=True)
class SessionSummary:
    name: str
    created_at: str
    message_count: int
    last_message_at: str | None
    first_prompt: str


class SessionStore:
    """SQLite-backed conversation persistence (local, inspectable)."""

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
                CREATE TABLE IF NOT EXISTS sessions (
                    name TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_name TEXT NOT NULL REFERENCES sessions(name),
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    command TEXT NOT NULL,
                    model TEXT,
                    tokens INTEGER,
                    latency_ms REAL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_name, id);
                """
            )

    def ensure_session(self, name: str) -> str:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (name, created_at) VALUES (?, ?)",
                (name, datetime.now(UTC).isoformat()),
            )
        return name

    def append_message(
        self,
        session: str,
        role: str,
        content: str,
        *,
        command: str,
        model: str | None = None,
        tokens: int | None = None,
        latency_ms: float | None = None,
    ) -> None:
        self.ensure_session(session)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (
                    session_name, role, content, command, model,
                    tokens, latency_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session,
                    role,
                    content,
                    command,
                    model,
                    tokens,
                    latency_ms,
                    datetime.now(UTC).isoformat(),
                ),
            )

    def get_messages(self, session: str) -> list[MessageRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_name = ? ORDER BY id",
                (session,),
            ).fetchall()
        return [
            MessageRecord(
                session=row["session_name"],
                role=row["role"],
                content=row["content"],
                command=row["command"],
                model=row["model"],
                tokens=row["tokens"],
                latency_ms=row["latency_ms"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def as_chat_messages(self, session: str) -> list[BaseMessage]:
        """Conversation history as LangChain messages, oldest first."""
        history: list[BaseMessage] = []
        for record in self.get_messages(session):
            if record.role == "user":
                history.append(HumanMessage(content=record.content))
            else:
                history.append(AIMessage(content=record.content))
        return history

    def list_sessions(self, *, limit: int = 20) -> list[SessionSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    s.name,
                    s.created_at,
                    COUNT(m.id) AS message_count,
                    MAX(m.created_at) AS last_message_at,
                    COALESCE(
                        (
                            SELECT content FROM messages
                            WHERE session_name = s.name AND role = 'user'
                            ORDER BY id LIMIT 1
                        ),
                        ''
                    ) AS first_prompt
                FROM sessions s
                LEFT JOIN messages m ON m.session_name = s.name
                GROUP BY s.name
                ORDER BY COALESCE(MAX(m.created_at), s.created_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            SessionSummary(
                name=row["name"],
                created_at=row["created_at"],
                message_count=row["message_count"],
                last_message_at=row["last_message_at"],
                first_prompt=row["first_prompt"],
            )
            for row in rows
        ]
