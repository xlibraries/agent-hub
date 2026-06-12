from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from slm.memory.store import SessionStore


def _store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / "sessions.db")


def test_append_and_get_messages_roundtrip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.append_message("s1", "user", "hello", command="chat", model="qwen")
    store.append_message(
        "s1", "assistant", "hi there", command="chat", model="qwen", tokens=12, latency_ms=80.5
    )

    records = store.get_messages("s1")
    assert [r.role for r in records] == ["user", "assistant"]
    assert records[0].content == "hello"
    assert records[1].tokens == 12
    assert records[1].latency_ms == 80.5


def test_messages_ordered_oldest_first(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for i in range(3):
        store.append_message("s1", "user", f"q{i}", command="chat")
        store.append_message("s1", "assistant", f"a{i}", command="chat")

    contents = [r.content for r in store.get_messages("s1")]
    assert contents == ["q0", "a0", "q1", "a1", "q2", "a2"]


def test_as_chat_messages_maps_roles(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.append_message("s1", "user", "question", command="chat")
    store.append_message("s1", "assistant", "answer", command="chat")

    history = store.as_chat_messages("s1")
    assert isinstance(history[0], HumanMessage)
    assert isinstance(history[1], AIMessage)
    assert history[0].content == "question"
    assert history[1].content == "answer"


def test_sessions_are_isolated(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.append_message("a", "user", "in-a", command="chat")
    store.append_message("b", "user", "in-b", command="chat")

    assert [r.content for r in store.get_messages("a")] == ["in-a"]
    assert [r.content for r in store.get_messages("b")] == ["in-b"]


def test_list_sessions_summary(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.append_message("s1", "user", "first prompt here", command="chat")
    store.append_message("s1", "assistant", "reply", command="chat")
    store.ensure_session("empty")

    summaries = {s.name: s for s in store.list_sessions()}
    assert summaries["s1"].message_count == 2
    assert summaries["s1"].first_prompt == "first prompt here"
    assert summaries["empty"].message_count == 0


def test_ensure_session_idempotent(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.ensure_session("s1")
    store.ensure_session("s1")
    assert len([s for s in store.list_sessions() if s.name == "s1"]) == 1


def test_get_messages_unknown_session_empty(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.get_messages("missing") == []
