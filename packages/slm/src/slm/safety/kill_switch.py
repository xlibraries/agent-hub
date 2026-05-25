import os

from slm.config.settings import get_settings


class KillSwitchEngaged(Exception):
    """Autonomous loop aborted by kill switch."""


def is_kill_switch_engaged() -> bool:
    settings = get_settings()
    value = os.environ.get(settings.kill_switch_env, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def assert_not_killed() -> None:
    if is_kill_switch_engaged():
        raise KillSwitchEngaged(
            f"Kill switch active ({get_settings().kill_switch_env}=1). Aborting autonomous loop."
        )
