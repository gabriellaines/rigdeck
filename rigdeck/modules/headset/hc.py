"""Minimal client for HeadsetControl (https://github.com/Sapd/HeadsetControl), via its JSON output.

Every write names the headset with `--device 0xVID:0xPID`. Without it HeadsetControl applies the
change to every headset it finds (its mock device included), and without the 0x prefixes it reads
the numbers as *decimal* and silently matches nothing.

RIGDECK_HEADSET_TEST=1 switches to HeadsetControl's mock headset, for development.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

from ..base import RigdeckError
from ...usb import connected

EXE = "headsetcontrol"
TEST_VENDOR = 0xF00B  # HeadsetControl's mock device
TEST_MODE = os.environ.get("RIGDECK_HEADSET_TEST") == "1"

# Option per capability we offer (all write-only: HeadsetControl can't read them back).
OPTIONS = {"sidetone": "--sidetone", "inactive_time": "--inactive-time", "lights": "--light",
           "voice_prompts": "--voice-prompt", "rotate_to_mute": "--rotate-to-mute"}
CAPS = {"CAP_SIDETONE": "sidetone", "CAP_INACTIVE_TIME": "inactive_time", "CAP_LIGHTS": "lights",
        "CAP_VOICE_PROMPTS": "voice_prompts", "CAP_ROTATE_TO_MUTE": "rotate_to_mute",
        "CAP_BATTERY_STATUS": "battery", "CAP_CHATMIX_STATUS": "chatmix"}

# Headsets whose sidetone is only on/off, whatever level is sent.
SIDETONE_ON_OFF = {"0951:1718"}  # HyperX Cloud II Wireless (Kingston)


class HeadsetError(RigdeckError):
    pass


class NotInstalled(HeadsetError):
    pass


def installed() -> bool:
    return shutil.which(EXE) is not None


def _run(*args: str, timeout: float = 15) -> str:
    if not installed():
        raise NotInstalled("HeadsetControl is not installed")
    if TEST_MODE:
        args = (*args, "--test-device")  # last: it takes an optional argument
    try:
        r = subprocess.run([EXE, *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise HeadsetError("HeadsetControl did not answer") from e
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip().splitlines()
        raise HeadsetError(msg[-1] if msg else f"HeadsetControl failed ({r.returncode})")
    return r.stdout


def supported_ids() -> set[tuple[int, int]]:
    """USB IDs HeadsetControl supports, from the udev rules it generates (opens no device)."""
    ids = set()
    for vid, pid in re.findall(r'idVendor}=="([0-9a-fA-F]{4})".*?idProduct}=="([0-9a-fA-F]{4})"', _run("-u")):
        if int(vid, 16) != TEST_VENDOR:
            ids.add((int(vid, 16), int(pid, 16)))
    return ids


def present() -> bool:
    """A supported headset (or its dongle) is plugged in. Cheap: no device I/O."""
    if TEST_MODE:
        return installed()
    try:
        return bool(supported_ids() & connected())
    except HeadsetError:
        return False


def _device(raw: dict) -> dict:
    vid, pid = int(raw.get("id_vendor", "0"), 16), int(raw.get("id_product", "0"), 16)
    bat = raw.get("battery") or {}
    state = bat.get("status", "")
    caps = [CAPS[c] for c in raw.get("capabilities", []) if c in CAPS]
    did = f"{vid:04x}:{pid:04x}"
    return {
        "id": did,
        "name": raw.get("device") or raw.get("product") or "Headset",
        "caps": caps,
        # the dongle answers even when the headset is off; then the battery is "unavailable"
        "on": state not in ("BATTERY_UNAVAILABLE", ""),
        "battery": bat.get("level") if state in ("BATTERY_AVAILABLE", "BATTERY_CHARGING") else None,
        "charging": state == "BATTERY_CHARGING",
        "chatmix": raw.get("chatmix"),
        "sidetone_on_off": did in SIDETONE_ON_OFF,
    }


def status() -> dict | None:
    """The first real headset HeadsetControl finds, or None."""
    data = json.loads(_run("--output", "json"))
    for raw in data.get("devices", []):
        is_test = int(raw.get("id_vendor", "0"), 16) == TEST_VENDOR
        if is_test == TEST_MODE and raw.get("status") in ("success", "partial"):  # partial: headset off
            return _device(raw)
    return None


def apply(device_id: str, settings: dict) -> None:
    """Send settings ({capability: value}) to one headset. Raises HeadsetError on failure."""
    vid, pid = device_id.split(":")
    args = ["--device", f"0x{vid}:0x{pid}", "--output", "json"]
    for key, value in settings.items():
        if key not in OPTIONS:
            raise HeadsetError(f"unknown setting {key}")
        args += [OPTIONS[key], str(int(value))]
    if len(args) == 4:
        return
    data = json.loads(_run(*args))
    failed = [a for a in data.get("actions", []) if a.get("status") != "success"]
    if failed:
        raise HeadsetError("; ".join(f"{CAPS.get(a.get('capability'), a.get('capability'))}: "
                                     f"{a.get('error_message') or 'failed'}" for a in failed))
