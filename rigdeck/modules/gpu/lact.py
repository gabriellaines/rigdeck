"""Minimal client for LACT's daemon (lactd): newline-delimited JSON over a unix socket.

Schema reference: LACT v0.10 `lact-schema` (Request / Response). Every settings change returns
a timer in seconds; unless confirmed within it, lactd reverts the change (safety for bad
overclocks). `apply()` confirms automatically; `apply(confirm=False)` leaves that to the caller.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess

from ..base import RigdeckError

SOCKET = os.environ.get("LACT_DAEMON_SOCKET_PATH", "/run/lactd.sock")


class LactError(RigdeckError):
    pass


class LactUnavailable(LactError):
    """lactd isn't installed / running / reachable."""


def installed() -> bool:
    return shutil.which("lact") is not None or os.path.exists("/usr/bin/lact")


def service_state() -> str:
    r = subprocess.run(["systemctl", "is-active", "lactd.service"], capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


class Lact:
    def __init__(self, path: str = SOCKET, timeout: float = 10):
        self.path, self.timeout = path, timeout

    def request(self, command: str, args=None):
        msg = {"command": command}
        if args is not None:
            msg["args"] = args
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(self.timeout)
                s.connect(self.path)
                s.sendall(json.dumps(msg).encode() + b"\n")
                buf = b""
                while not buf.endswith(b"\n"):
                    chunk = s.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
        except FileNotFoundError as e:
            raise LactUnavailable("LACT's service (lactd) is not running") from e
        except PermissionError as e:
            raise LactUnavailable("no permission to talk to lactd — is your user in the 'wheel' group?") from e
        except (ConnectionError, OSError) as e:
            raise LactUnavailable(f"could not reach lactd: {e}") from e
        try:
            resp = json.loads(buf)
        except ValueError as e:
            raise LactError(f"unexpected reply from lactd: {buf[:200]!r}") from e
        if resp.get("status") == "ok":
            return resp.get("data")
        err = resp.get("data") or {}
        raise LactError(_error_text(err))

    # ---- reads
    def system_info(self) -> dict:
        return self.request("system_info")

    def devices(self) -> list[dict]:
        return self.request("list_devices")

    def device_info(self, gpu: str) -> dict:
        return self.request("device_info", {"id": gpu})

    def stats(self, gpu: str) -> dict:
        return self.request("device_stats", {"id": gpu})

    def config(self, gpu: str) -> dict:
        return self.request("get_gpu_config", {"id": gpu}) or {}

    # ---- writes (each returns lactd's revert timer)
    def set_fan(self, gpu: str, enabled: bool, mode: str | None = None, static_speed: float | None = None,
                curve: dict[int, float] | None = None, pmfw: dict | None = None) -> int:
        args = {"id": gpu, "enabled": enabled, "pmfw": pmfw or {}}
        if mode:
            args["mode"] = mode
        if static_speed is not None:
            args["static_speed"] = float(static_speed)
        if curve is not None:
            args["curve"] = {str(int(t)): float(v) for t, v in sorted(curve.items())}
        return self.request("set_fan_control", args)

    def set_power_cap(self, gpu: str, watts: float | None) -> int:
        return self.request("set_power_cap", {"id": gpu, "cap": watts})

    def set_performance_level(self, gpu: str, level: str) -> int:
        return self.request("set_performance_level", {"id": gpu, "performance_level": level})

    def confirm(self, keep: bool = True):
        return self.request("confirm_pending_config", {"command": "confirm" if keep else "revert"})

    def apply(self, fn, *args, confirm: bool = True, **kw) -> int:
        """Run a write and (by default) confirm it immediately."""
        timer = fn(*args, **kw)
        if confirm:
            self.confirm(True)
        return timer

    def enable_overdrive(self) -> str:
        return self.request("enable_overdrive")


def _error_text(err) -> str:
    """lactd sends serde_error::Error {description, source}; flatten it into one message."""
    if isinstance(err, str):
        return err
    parts = []
    while isinstance(err, dict):
        d = err.get("description") or err.get("message")
        if d and d not in parts:
            parts.append(d)
        err = err.get("source")
    return ": ".join(parts) or "lactd reported an error"
