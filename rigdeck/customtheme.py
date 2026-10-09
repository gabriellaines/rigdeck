"""Custom themes: a RigDeck theme as a small JSON file in ~/.config/rigdeck/themes/.

A theme file is `{"name": "...", "window": "#rrggbb", "panel": "...", "raised": "...",
"text": "...", "muted": "...", "border": "...", "accent": "..."}` — the same 7 colors every
built-in theme in `rigdeck/gui/theme.py` has. `parse()` checks a file before it's used; `save()`
and `delete()` manage the files in `DIR`; `list_themes()` is what the app loads at startup and
whenever a theme is added or removed. The format is described in docs/custom-themes.md.
"""
from __future__ import annotations

import json
import os
import re

from . import config

TOKEN_KEYS = ("window", "panel", "raised", "text", "muted", "border", "accent")
DIR = os.path.join(os.path.dirname(config.PATH), "themes")


class ThemeFileError(ValueError):
    """The file can't be used; nothing was changed. `problems` lists every mistake found."""

    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "theme"


def _norm_color(v) -> str:
    """Raises ValueError (via config.parse_color) if `v` isn't a colour."""
    config.parse_color(str(v))
    return "#" + str(v).lstrip("#").lower()


def _luminance(hex_color: str) -> float:
    r, g, b = config.parse_color(hex_color)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def parse(text: str) -> dict:
    """Validate a theme file's JSON text; return {"name", "dark", **7 colors} or raise ThemeFileError."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ThemeFileError([f"not valid JSON — {e}"]) from e
    if not isinstance(data, dict):
        raise ThemeFileError(["should be an object { … }"])

    problems: list[str] = []
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append('name: should be a short name, e.g. "My Theme"')

    colors: dict[str, str] = {}
    for key in TOKEN_KEYS:
        if key not in data:
            problems.append(f'{key}: missing — should be a colour like "ff0000" or "#00c8ff"')
            continue
        try:
            colors[key] = _norm_color(data[key])
        except ValueError:
            problems.append(f'{key}: should be a colour like "ff0000" or "#00c8ff"')

    extra = sorted(set(data) - {"name", *TOKEN_KEYS})
    if extra:
        problems.append(f"unknown setting(s): {', '.join(extra)}")

    if problems:
        raise ThemeFileError(problems)

    return {"name": name.strip(), "dark": _luminance(colors["window"]) < 0.5, **colors}


def list_themes() -> dict[str, dict]:
    """{slug: theme} for every valid *.json file in DIR. A broken file is skipped, not raised."""
    themes: dict[str, dict] = {}
    if not os.path.isdir(DIR):
        return themes
    for name in sorted(os.listdir(DIR)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(DIR, name)) as f:
                themes[name[:-5]] = parse(f.read())
        except (ThemeFileError, OSError):
            continue
    return themes


def save(text: str) -> tuple[str, dict]:
    """Validate `text`, then write it (normalized) to DIR, overwriting a same-named theme."""
    theme = parse(text)
    os.makedirs(DIR, exist_ok=True)
    slug = _slug(theme["name"])
    # "dark" isn't stored — it's recomputed from `window` every time the file is read.
    stored = {"name": theme["name"], **{k: theme[k] for k in TOKEN_KEYS}}
    with open(os.path.join(DIR, f"{slug}.json"), "w") as f:
        f.write(json.dumps(stored, indent=2))
    return slug, theme


def delete(slug: str):
    path = os.path.join(DIR, f"{slug}.json")
    if os.path.exists(path):
        os.remove(path)


def template(tokens: dict, name: str = "My Theme") -> str:
    """A ready-to-edit theme file starting from `tokens` (e.g. the active theme's own colors)."""
    return json.dumps({"name": name, **{k: tokens[k] for k in TOKEN_KEYS}}, indent=2)
