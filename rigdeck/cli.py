"""`rigdeck` command line. Each hardware module adds its own subcommands."""
from __future__ import annotations

import argparse
import sys

from . import __version__, servicectl, sysinfo
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
    print("Devices   " + (", ".join(m.title for m in MODULES if m.detect()) or "none detected"))
    print(f"Service   {servicectl.state()}")


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
    for m in MODULES:
        m.add_cli(sub)
    a = ap.parse_args()
    try:
        a.func(a)
    except (RigdeckError, ValueError) as e:
        sys.exit(f"error: {e}")
    except KeyboardInterrupt:
        sys.exit(130)
