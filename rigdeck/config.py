"""User settings in ~/.config/rigdeck/config.toml, shared by CLI, GUI and service.

Each module owns a top-level table named after its id, e.g. [cooler.led].
"""
from __future__ import annotations

import os
import tomllib

PATH = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                    "rigdeck", "config.toml")


def load() -> dict:
    try:
        with open(PATH, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}


def section(cfg: dict, *path: str) -> dict:
    """Return (creating if needed) the nested table at cfg[path[0]][path[1]]..."""
    for key in path:
        cfg = cfg.setdefault(key, {})
    return cfg


def _value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_value(x) for x in v) + "]"
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _dump(table: dict, prefix: str, out: list[str]):
    scalars = {k: v for k, v in table.items() if not isinstance(v, dict)}
    if scalars and prefix:
        out.append(f"[{prefix}]")
    out.extend(f"{k} = {_value(v)}" for k, v in scalars.items())
    if scalars:
        out.append("")
    for k, v in table.items():
        if isinstance(v, dict):
            _dump(v, f"{prefix}.{k}" if prefix else k, out)


def save(cfg: dict):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    out: list[str] = []
    _dump(cfg, "", out)
    with open(PATH + ".tmp", "w") as f:
        f.write("\n".join(out))
    os.replace(PATH + ".tmp", PATH)


def parse_color(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    if len(s) != 6:
        raise ValueError(f"colour must be RRGGBB hex, got {s!r}")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
