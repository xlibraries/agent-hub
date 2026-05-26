from slm.graph.agent import _normalize_task_id


def test_normalize_task_id_placeholder() -> None:
    uid = _normalize_task_id("uuid-string")
    assert uid != "uuid-string"
    assert len(uid) == 36


def test_normalize_task_id_preserves_valid() -> None:
    valid = "123e4567-e89b-12d3-a456-426614174000"
    assert _normalize_task_id(valid) == valid
