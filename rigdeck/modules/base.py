"""Module interface. Each supported piece of hardware is one Module.

A module contributes up to three things, all optional:
  * CLI subcommands       -> add_cli()
  * a background task     -> service_task()   (runs inside `rigdeck service`)
  * a GUI page            -> gui_page()       (GTK is only imported when the GUI runs)
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
    id: str = ""            # CLI command and config table name
    title: str = ""         # human name
    icon: str = "application-x-executable-symbolic"

    def detect(self) -> bool:
        """Is this hardware present?"""
        return False

    def add_cli(self, sub: argparse._SubParsersAction):
        pass

    def service_task(self) -> ServiceTask | None:
        return None

    def gui_page(self, window):
        """Return a Gtk.Widget for the main window content area."""
        return None
