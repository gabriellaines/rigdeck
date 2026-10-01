"""Talk to the rigdeck systemd user service."""
from __future__ import annotations

import subprocess

UNIT = "rigdeck.service"


def _systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True)


def state() -> str:
    """'active', 'inactive', 'failed', or 'not-installed'."""
    r = _systemctl("is-active", UNIT)
    out = r.stdout.strip()
    if out in ("inactive", "unknown") and "could not be found" in _systemctl("status", UNIT).stderr:
        return "not-installed"
    return out or "not-installed"


def is_active() -> bool:
    return state() == "active"


def enable_now() -> bool:
    return _systemctl("enable", "--now", UNIT).returncode == 0


def reload() -> bool:
    """Ask the running service to re-read config.toml. False if it isn't running."""
    return is_active() and _systemctl("kill", "-s", "HUP", UNIT).returncode == 0
