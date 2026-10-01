"""`rigdeck` command line. Each hardware module adds its own subcommands."""
from __future__ import annotations

import argparse
import sys

from . import __version__, servicectl, sysinfo, updater
from .modules import MODULES
from .modules.base import RigdeckError


def cmd_info(a):
    o = sysinfo.overview()
    print(f"OS        {o['os']}  (kernel {o['kernel']})")
    print(f"CPU       {o['cpu']}")
    for g in o["gpus"]:
        print(f"GPU       {g.get('name') or g['vendor']}  [{g['pci']}]")
        print(f"  driver  {g.get('kernel_driver')} (kernel), {g.get('vulkan_driver')} {g.get('driver_version') or ''}")
        print(f"  vulkan  {g.get('vulkan_api')}   VBIOS {g.get('vbios')}")
    print(f"Mesa      {o['mesa']}")
    print("Devices   " + (", ".join(m.title for m in MODULES if m.kind == "device" and m.detect())
                          or "none detected"))
    print(f"Service   {servicectl.state()}")


def cmd_update(a):
    try:
        rel = updater.check()
    except updater.UpdateError as e:
        raise RigdeckError(str(e))
    if not rel["newer"]:
        print(f"rigdeck {rel['current']} is up to date.")
        return
    print(f"rigdeck {rel['version']} is available (you have {rel['current']}): {rel['url']}")
    if a.check:
        return
    if rel["method"] != "installer":
        print("This copy is managed by your package manager — update it there.")
        return
    try:
        updater.apply(rel)
    except updater.UpdateError as e:
        raise RigdeckError(str(e))


def cmd_service(a):
    from .service import run
    run()


def main():
    ap = argparse.ArgumentParser(prog="rigdeck", description="Control panel for PC hardware on Linux. "
                                 "Run `rigdeck-gui` for the graphical app.")
    ap.add_argument("--version", action="version", version=f"rigdeck {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info", help="system overview: CPU, GPU, drivers, detected devices").set_defaults(func=cmd_info)
    sub.add_parser("service", help="run the background service in the foreground "
                   "(normally started by systemd)").set_defaults(func=cmd_service)
    u = sub.add_parser("update", help="update rigdeck to the latest GitHub release")
    u.add_argument("--check", action="store_true", help="only check, don't install")
    u.set_defaults(func=cmd_update)
    for m in MODULES:
        m.add_cli(sub)
    a = ap.parse_args()
    try:
        a.func(a)
    except (RigdeckError, ValueError) as e:
        sys.exit(f"error: {e}")
    except KeyboardInterrupt:
        sys.exit(130)
