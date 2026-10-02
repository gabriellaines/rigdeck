"""Network: Ethernet and Wi-Fi adapters, from NetworkManager (nmcli) and sysfs.

Read-only: connecting stays in the desktop's own settings, which the page opens.
"""
from __future__ import annotations

import functools
import os
import shutil
import subprocess
import time

from ... import bluez
from ..base import Module, RigdeckError

NET = "/sys/class/net"


class NetworkError(RigdeckError):
    pass


def _run(*cmd: str, timeout: float = 8) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise NetworkError(f"{cmd[0]}: {e}") from e
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip()
        raise NetworkError(msg.splitlines()[-1] if msg else f"{cmd[0]} failed")
    return r.stdout


def _read(path: str) -> str:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


@functools.lru_cache(maxsize=None)        # the adapter's model never changes
def hardware_name(sysfs: str) -> str:
    """'TP-Link AC600 wireless Realtek RTL8811AU [Archer T2U Nano]' from udev's hardware database,
    else the USB product string."""
    props = {}
    try:
        for line in _run("udevadm", "info", "-q", "property", sysfs).splitlines():
            k, _, v = line.partition("=")
            props[k] = v
    except NetworkError:
        pass
    vendor = props.get("ID_VENDOR_FROM_DATABASE", "").split(",")[0].replace(" Semiconductor Co.", "").strip()
    model = props.get("ID_MODEL_FROM_DATABASE") or _read(os.path.join(sysfs, "device", "..", "product"))
    if model and vendor and not model.startswith(vendor):
        return f"{vendor} {model}"
    return model or vendor


def _split(line: str) -> list[str]:
    """nmcli -t fields: ':' separated, with '\\:' escaping."""
    out, cur, esc = [], "", False
    for ch in line:
        if esc:
            cur, esc = cur + ch, False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            out.append(cur)
            cur = ""
        else:
            cur += ch
    return out + [cur]


def parse_devices(out: str) -> list[dict]:
    """Physical Ethernet / Wi-Fi devices from `nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device`."""
    devs = []
    for line in out.splitlines():
        p = _split(line)
        if len(p) < 4 or p[1] not in ("ethernet", "wifi"):
            continue
        if not os.path.exists(os.path.join(NET, p[0], "device")):   # virtual (veth, docker…)
            continue
        devs.append({"device": p[0], "type": p[1], "state": p[2], "connection": p[3]})
    return devs


def _band(mhz: int) -> str:
    return "6 GHz" if mhz >= 5925 else "5 GHz" if mhz >= 4900 else "2.4 GHz" if mhz else ""


def parse_wifi_list(out: str) -> list[dict]:
    """Networks from `nmcli -t -f IN-USE,SSID,SIGNAL,FREQ,RATE,SECURITY device wifi list`,
    strongest first, one entry per name."""
    nets: dict[str, dict] = {}
    for line in out.splitlines():
        p = _split(line)
        if len(p) < 6 or not p[1]:
            continue
        mhz = int(p[3].split()[0]) if p[3].split() and p[3].split()[0].isdigit() else 0
        n = {"inUse": p[0] == "*", "ssid": p[1], "signal": int(p[2]) if p[2].isdigit() else 0,
             "band": _band(mhz), "rate": p[4], "security": p[5] or "open"}
        old = nets.get(n["ssid"])
        if old is None or n["inUse"] or (not old["inUse"] and n["signal"] > old["signal"]):
            nets[n["ssid"]] = n
    return sorted(nets.values(), key=lambda n: (not n["inUse"], -n["signal"]))


def parse_details(out: str) -> dict:
    """MAC, addresses, gateway and DNS from `nmcli -t -f … device show DEV`."""
    d = {"mac": "", "ipv4": [], "ipv6": [], "gateway": "", "dns": []}
    for line in out.splitlines():
        key, _, val = line.partition(":")
        key = key.split("[")[0]
        if not val:
            continue
        if key == "GENERAL.HWADDR":
            d["mac"] = val.replace("\\", "")
        elif key == "IP4.ADDRESS":
            d["ipv4"].append(val)
        elif key == "IP6.ADDRESS" and not val.startswith("fe80"):
            d["ipv6"].append(val)
        elif key == "IP4.GATEWAY":
            d["gateway"] = val
        elif key == "IP4.DNS":
            d["dns"].append(val)
    return d


def default_device() -> str:
    """The adapter the internet goes through ('' if offline)."""
    try:
        out = _run("ip", "route", "show", "default")
    except NetworkError:
        return ""
    p = out.split()
    return p[p.index("dev") + 1] if "dev" in p else ""


def counters(dev: str) -> tuple[int, int]:
    s = os.path.join(NET, dev, "statistics")
    try:
        return int(_read(os.path.join(s, "rx_bytes"))), int(_read(os.path.join(s, "tx_bytes")))
    except ValueError:
        return 0, 0


def read() -> dict:
    if not shutil.which("nmcli"):
        return {"nmcli": False, "adapters": [], "networks": [], "internet": "", "time": time.monotonic()}
    adapters = parse_devices(_run("nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"))
    networks = []
    if any(a["type"] == "wifi" for a in adapters):
        networks = parse_wifi_list(_run("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,FREQ,RATE,SECURITY",
                                        "device", "wifi", "list", "--rescan", "no"))
    for a in adapters:
        sysfs = os.path.join(NET, a["device"])
        a["hardware"] = hardware_name(sysfs)
        a["driver"] = os.path.basename(os.path.realpath(os.path.join(sysfs, "device", "driver")))
        speed = _read(os.path.join(sysfs, "speed"))
        a["speed"] = int(speed) if speed.lstrip("-").isdigit() and int(speed) > 0 else None
        a.update(parse_details(_run("nmcli", "-t", "-f", "GENERAL.HWADDR,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS,IP6.ADDRESS",
                                    "device", "show", a["device"])))
        a["wifi"] = next((n for n in networks if n["inUse"]), None) if a["type"] == "wifi" else None
        a["rx"], a["tx"] = counters(a["device"])
    return {"nmcli": True, "adapters": adapters, "networks": networks, "internet": default_device(),
            "time": time.monotonic()}


# ---- CLI ------------------------------------------------------------------------------

def cli_status(a):
    s = read()
    if not s["nmcli"]:
        raise RigdeckError("network status needs NetworkManager (nmcli)")
    for d in s["adapters"]:
        kind = "Wi-Fi" if d["type"] == "wifi" else "Ethernet"
        star = "  ← internet" if d["device"] == s["internet"] else ""
        print(f"{kind:<10}{d['device']:<10}{d['state']}{star}   ({d['hardware']})")
        w = d.get("wifi")
        if w:
            print(f"{'':<10}{w['ssid']}  {w['signal']}%  {w['band']}  {w['rate']}  {w['security']}")
        elif d["speed"]:
            print(f"{'':<10}link {d['speed']} Mbit/s")
        if d["ipv4"]:
            print(f"{'':<10}{', '.join(d['ipv4'])}  gateway {d['gateway'] or '—'}")
    adapters, devices = bluez.read()
    for ad in adapters:
        print(f"{'Bluetooth':<10}{ad['path'].rsplit('/', 1)[-1]:<10}{'on' if ad['powered'] else 'off'}")
    for d in devices:
        bat = f"  {d['battery']}%" if d["battery"] is not None else ""
        print(f"{'':<10}{d['name']} ({d['kind'].lower()}) {'connected' if d['connected'] else 'paired'}{bat}")


class NetworkModule(Module):
    id = "network"
    title = "Network"
    icon = "network"
    kind = "system"
    order = 55

    def detect(self) -> bool:
        return os.path.isdir(NET)

    def add_cli(self, sub):
        sub.add_parser("network", help="Ethernet, Wi-Fi and Bluetooth status").set_defaults(func=cli_status)

    def qml_page(self):
        return os.path.join(os.path.dirname(__file__), "qml", "NetworkPage.qml")

    def qt_backend(self, app):
        from .qt import NetworkBackend
        return NetworkBackend()
