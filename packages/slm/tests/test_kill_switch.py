import os

from slm.safety.kill_switch import assert_not_killed, is_kill_switch_engaged


def test_kill_switch_default_off():
    os.environ.pop("SLM_KILL_SWITCH", None)
    assert is_kill_switch_engaged() is False
    assert_not_killed()


def test_kill_switch_engaged(monkeypatch):
    monkeypatch.setenv("SLM_KILL_SWITCH", "1")
    assert is_kill_switch_engaged() is True
