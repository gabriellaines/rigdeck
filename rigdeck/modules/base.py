"""Module interface. Each supported piece of hardware is one Module.

A module contributes up to three things, all optional:
  * CLI subcommands       -> add_cli()
  * a background task     -> service_task()   (runs inside `rigdeck service`)
  * a GUI page            -> qml_page() + qt_backend()   (Qt is only imported by the GUI)
"""
from __future__ import annotations

import argparse


class RigdeckError(Exception):
    """Errors shown to the user as a plain message (no traceback)."""


class ServiceTask:
    """Work the background service does for a module. Called from one thread."""

    def reload(self, cfg: dict):
        """Config file changed (or service started)."""

    def tick(self, now: float) -> float:
        """Do periodic work. Return seconds until the next tick is wanted."""
        return 1.0

    def close(self):
        pass


class Module:
    id: str = ""            # CLI command, config table name, GUI page id
    title: str = ""         # human name (sidebar label)
    icon: str = "box"       # icon name from rigdeck/gui/icons (Lucide)
    kind: str = "device"    # "device" (cooler…), "peripheral" (mouse, headset…) or "system" (CPU…)
    order: int = 50         # sidebar position

    def detect(self) -> bool:
        """Is this hardware present?"""
        return False

    def add_cli(self, sub: argparse._SubParsersAction):
        pass

    def service_task(self) -> ServiceTask | None:
        return None

    def qml_page(self) -> str | None:
        """Absolute path of this module's QML page, or None for no GUI page."""
        return None

    def qt_backend(self, app):
        """A QObject exposed to the page as `backend`, or None. Only called by the GUI."""
        return None
