"""Wi-Fi, Ethernet and Bluetooth status, from NetworkManager (nmcli) and BlueZ (D-Bus via busctl).

Read-only apart from switching Bluetooth on and off: connecting and pairing stay in the
desktop's own settings, which the page opens.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

from ..base import Module, RigdeckError

NET = "/sys/class/net"


class ConnectivityError(RigdeckError):
    pass


def _run(*cmd: str, timeout: float = 8) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ConnectivityError(f"{cmd[0]}: {e}") from e
    if r.returncode != 0:
        raise ConnectivityError((r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip()
                                else f"{cmd[0]} failed")
    return r.stdout


def _read(path: str) -> str:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def hardware_name(sysfs: str) -> str:
    """'TP-Link AC600 wireless Realtek RTL8811AU [Archer T2U Nano]' from udev's hardware database,
    else the USB product string."""
    props = {}
    try:
        for line in _run("udevadm", "info", "-q", "property", sysfs).splitlines():
            k, _, v = line.partition("=")
            props[k] = v
    except ConnectivityError:
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


def parse_wifi(out: str) -> dict | None:
    """The network in use from `nmcli -t -f IN-USE,SSID,SIGNAL,FREQ,RATE,SECURITY device wifi list`."""
    for line in out.splitlines():
        p = _split(line)
        if len(p) >= 6 and p[0] == "*":
            mhz = int(p[3].split()[0]) if p[3].split() and p[3].split()[0].isdigit() else 0
            band = "6 GHz" if mhz >= 5925 else "5 GHz" if mhz >= 4900 else "2.4 GHz" if mhz else ""
            return {"ssid": p[1], "signal": int(p[2]) if p[2].isdigit() else None, "band": band,
                    "rate": p[4], "security": p[5] or "open"}
    return None


def parse_bluez(data: dict) -> tuple[list[dict], list[dict]]:
    """Adapters and devices from BlueZ's GetManagedObjects (busctl --json=short)."""
    adapters, devices = [], []
    for path, ifaces in data.items():
        def props(name):
            return {k: v["data"] for k, v in ifaces.get(name, {}).items()}
        if "org.bluez.Adapter1" in ifaces:
            a = props("org.bluez.Adapter1")
            adapters.append({"path": path, "name": a.get("Alias") or a.get("Name", ""), "address": a.get("Address", ""),
                             "powered": bool(a.get("Powered"))})
        if "org.bluez.Device1" in ifaces:
            d = props("org.bluez.Device1")
            if not d.get("Paired") and not d.get("Connected"):
                continue   # seen nearby, not yours
            bat = props("org.bluez.Battery1").get("Percentage")
            devices.append({"path": path, "name": d.get("Alias") or d.get("Name") or d.get("Address", ""),
                            "icon": d.get("Icon", ""), "connected": bool(d.get("Connected")),
                            "battery": bat, "adapter": d.get("Adapter", "")})
    return adapters, devices


def read() -> dict:
    net, wifi, error = [], None, ""
    if shutil.which("nmcli"):
        try:
            net = parse_devices(_run("nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"))
            if any(d["type"] == "wifi" and d["state"] == "connected" for d in net):
                wifi = parse_wifi(_run("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,FREQ,RATE,SECURITY",
                                       "device", "wifi", "list", "--rescan", "no"))
        except ConnectivityError as e:
            error = str(e)
    for d in net:
        sysfs = os.path.join(NET, d["device"])
        d["hardware"] = hardware_name(sysfs)
        d["driver"] = os.path.basename(os.path.realpath(os.path.join(sysfs, "device", "driver")))
        speed = _read(os.path.join(sysfs, "speed"))
        d["speed"] = int(speed) if speed.lstrip("-").isdigit() and int(speed) > 0 else None
        if d["type"] == "wifi" and d["state"] == "connected":
            d["wifi"] = wifi
    adapters, bt = [], []
    if shutil.which("busctl"):
        try:
            out = _run("busctl", "--system", "--json=short", "call", "org.bluez", "/",
                       "org.freedesktop.DBus.ObjectManager", "GetManagedObjects", timeout=5)
            adapters, bt = parse_bluez(json.loads(out)["data"][0])
        except (ConnectivityError, ValueError, KeyError, IndexError):
            pass   # no BlueZ / no adapter
        for a in adapters:
            a["hardware"] = hardware_name(os.path.join("/sys/class/bluetooth", a["path"].rsplit("/", 1)[-1]))
    return {"network": net, "adapters": adapters, "bluetooth": bt, "error": error,
            "nmcli": bool(shutil.which("nmcli"))}


def set_bluetooth_power(adapter_path: str, on: bool):
    _run("busctl", "--system", "set-property", "org.bluez", adapter_path, "org.bluez.Adapter1", "Powered", "b",
         "true" if on else "false")


def settings_command(page: str) -> list[str] | None:
    """The desktop's own settings page for 'bluetooth' or 'network', if we know how to open it."""
    if shutil.which("systemsettings"):
        return ["systemsettings", {"bluetooth": "kcm_bluetooth", "network": "kcm_networkmanagement"}[page]]
    if shutil.which("gnome-control-center"):
        return ["gnome-control-center", {"bluetooth": "bluetooth", "network": "wifi"}[page]]
    return None


# ---- CLI ------------------------------------------------------------------------------

def cli_status(a):
    s = read()
    for d in s["network"]:
        line = f"{'Wi-Fi' if d['type'] == 'wifi' else 'Ethernet':<10}{d['device']:<10}{d['state']:<14}"
        w = d.get("wifi")
        if w:
            line += f"{w['ssid']}  {w['signal']}%  {w['band']}  {w['rate']}"
        elif d["speed"]:
            line += f"{d['connection']}  {d['speed']} Mbit/s"
        print(line + f"   ({d['hardware']})")
    for ad in s["adapters"]:
        print(f"{'Bluetooth':<10}{ad['path'].rsplit('/', 1)[-1]:<10}{'on' if ad['powered'] else 'off':<14}"
              f"as \"{ad['name']}\"   ({ad['hardware']})")
    for d in s["bluetooth"]:
        bat = f"  {d['battery']}%" if d["battery"] is not None else ""
        print(f"  {d['name']:<30}{'connected' if d['connected'] else 'paired'}{bat}")
    if not s["adapters"]:
        print("Bluetooth no adapter")


class ConnectivityModule(Module):
    id = "connectivity"
    title = "Wi-Fi & Bluetooth"
    icon = "wifi"
    kind = "peripheral"
    order = 66

    def detect(self) -> bool:
        has_wifi = any(os.path.isdir(os.path.join(NET, n, "wireless")) for n in os.listdir(NET)) \
            if os.path.isdir(NET) else False
        return has_wifi or os.path.isdir("/sys/class/bluetooth")

    def add_cli(self, sub):
        sub.add_parser("network", help="Wi-Fi, Ethernet and Bluetooth status").set_defaults(func=cli_status)

    def qml_page(self):
        return os.path.join(os.path.dirname(__file__), "qml", "ConnectivityPage.qml")

    def qt_backend(self, app):
        from .qt import ConnectivityBackend
        return ConnectivityBackend()
