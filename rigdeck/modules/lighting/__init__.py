"""One colour on every device with lighting, like SignalRGB — and back to how each one was before.

Syncing first takes a snapshot of each device's own lighting (kept in
~/.local/state/rigdeck/lighting-sync.json until restored), then sets the colour everywhere.
Syncing again with another colour keeps the first snapshot, so "Restore" always goes back to the
lighting from before the sync. Each device type is a `Target`.
"""
from __future__ import annotations

import json
import os

from ... import config, servicectl
from ..base import Module, RigdeckError

STATE = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
                     "rigdeck", "lighting-sync.json")


def _color(c: str) -> str:
    config.parse_color(c)                 # raises ValueError for anything but rrggbb
    return c.lstrip("#").lower()


class Target:
    """A kind of device with lighting. snapshot/apply/restore raise on failure."""
    id = ""
    name = ""

    def present(self) -> bool:
        return False

    def snapshot(self):
        """What to restore later (JSON-serialisable)."""

    def apply(self, color: str) -> str:
        """Raise if nothing changed; return a note if only part of it did (else '')."""
        return ""

    def restore(self, snap) -> str:
        """Put the snapshot back. Returns a note for the user, or ''."""
        return ""


class CoolerTarget(Target):
    id, name = "cooler", "Cooler"

    def present(self):
        from ..waterforce.device import find_hidraw
        return bool(find_hidraw())

    def snapshot(self):
        from ..waterforce import effects
        return {**effects.DEFAULTS, **config.section(config.load(), "cooler", "led")}

    def apply(self, color):
        from ..waterforce import set_led
        led = self.snapshot()
        set_led("static", color, led.get("brightness") or 100, led.get("speed"))
        return ""

    def restore(self, snap):
        from ..waterforce import set_led
        set_led(snap["effect"], snap.get("color"), snap.get("brightness"), snap.get("speed"))
        return ""


class MotherboardTarget(Target):
    id, name = "motherboard", "Motherboard"

    def present(self):
        from ..motherboard import aura
        return bool(aura.find())

    def snapshot(self):
        from ..motherboard import lighting
        info = lighting() or {"zones": []}
        return {z["id"]: {"mode": z["mode"], "color": z["color"]} for z in info["zones"]}

    def apply(self, color):
        from ..motherboard import lighting, set_lighting
        for z in (lighting() or {"zones": []})["zones"]:
            set_lighting(z["id"], "static", color)
        return ""

    def restore(self, snap):
        from ..motherboard import set_lighting
        unknown = []
        for zid, z in snap.items():
            if z["mode"]:
                set_lighting(zid, z["mode"], z["color"])
            else:
                unknown.append(zid)
        if unknown:   # the controller can't be read, and RigDeck never set these zones
            cfg = config.load()
            for zid in unknown:
                config.section(cfg, "motherboard", "lighting").pop(zid, None)
            config.save(cfg)
            return "motherboard zones RigDeck never set before keep the synced colour"
        return ""


class KeyboardTarget(Target):
    id, name = "keyboard", "Keyboard"
    PROFILES = (1, 2, 3)

    def present(self):
        from ..keyboard import connected
        return bool(connected())

    def snapshot(self):
        from ..keyboard import custom_lighting
        return {str(n): custom_lighting(n) for n in self.PROFILES}   # None = the keyboard's own

    def _put(self, per_profile: dict):
        from ..keyboard import apply_custom, connected, save_lighting
        for n in self.PROFILES:
            save_lighting(n, per_profile[n])
        servicectl.reload()                       # the service keeps it on after profile switches
        for dev in connected():
            for n in self.PROFILES:               # only the active profile is written
                apply_custom(dev, n, analog_part=False)

    def apply(self, color):
        self._put({n: {"base": color, "keys": {}} for n in self.PROFILES})
        return ""

    def restore(self, snap):
        self._put({n: snap.get(str(n)) for n in self.PROFILES})
        return ""


class MouseTarget(Target):
    """The light shows the active DPI stage's colour, so every stage gets the colour. A mouse
    that's asleep can't be changed: the others still are, and it's reported."""
    id, name = "mouse", "Mouse"

    def present(self):
        from ..mouse import connected
        return bool(connected())

    def _mice(self) -> tuple[list[tuple[dict, dict]], list[str]]:
        """([(device, state)] of the awake mice, [names of the asleep ones])."""
        from ..mouse import connected, read_state
        awake, asleep = [], []
        for dev in connected():
            st = read_state(dev)
            if st["asleep"]:
                asleep.append(st["name"])
            else:
                awake.append((dev, st))
        if not awake and asleep:
            raise RigdeckError(self._asleep(asleep))
        return awake, asleep

    @staticmethod
    def _asleep(names: list[str]) -> str:
        return f"{' and '.join(names)} {'is' if len(names) == 1 else 'are'} asleep — move it to wake it"

    def snapshot(self):
        return {dev["model"]: {"colors": st["colors"], "led": st["led"]} for dev, st in self._mice()[0]}

    def apply(self, color):
        from ..mouse import MAX_STAGES, change
        awake, asleep = self._mice()
        for dev, _ in awake:
            for i in range(MAX_STAGES):
                change(dev, {"color": (i, color)})
            change(dev, {"led": {"mode": 1, "on": True}})          # steady
        return self._asleep(asleep) if asleep else ""

    def restore(self, snap):
        from ..mouse import change
        awake, asleep = self._mice()
        for dev, _ in awake:
            s = snap.get(dev["model"])
            if s:
                for i, c in enumerate(s["colors"]):
                    change(dev, {"color": (i, c)})
                change(dev, {"led": s["led"]})
        from ..mouse import MODELS
        missed = [n for n in asleep if any(MODELS[m]["name"] == n for m in snap)]
        if missed:
            raise RigdeckError(self._asleep(missed))
        return ""


TARGETS: list[Target] = [CoolerTarget(), MotherboardTarget(), KeyboardTarget(), MouseTarget()]


def _load() -> dict:
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(state: dict | None):
    if not state:
        try:
            os.remove(STATE)
        except FileNotFoundError:
            pass
        return
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE + ".tmp", "w") as f:
        json.dump(state, f, indent=1)
    os.replace(STATE + ".tmp", STATE)


def status() -> dict:
    """{active, color, devices: [{id, name, present, synced}]}."""
    st = _load()
    synced = st.get("snapshots", {})
    return {"active": bool(synced), "color": st.get("color", ""),
            "devices": [{"id": t.id, "name": t.name, "present": t.present(), "synced": t.id in synced}
                        for t in TARGETS]}


def sync(color: str, only: list[str] | None = None) -> dict[str, str]:
    """Set `color` on every present device (or those in `only`). Returns {device id: problem} for
    the ones that failed or only partly changed; every device that changed keeps a snapshot."""
    color = _color(color)
    st = _load()
    snaps = st.get("snapshots", {})
    errors = {}
    for t in TARGETS:
        if (only and t.id not in only) or not t.present():
            continue
        new = t.id not in snaps                   # keep the lighting from before the first sync
        try:
            if new:
                snaps[t.id] = t.snapshot()
            note = t.apply(color)
            if note:
                errors[t.id] = note
        except Exception as e:                    # one device failing mustn't stop the others
            errors[t.id] = str(e)
            if new:                               # nothing changed: nothing to restore
                snaps.pop(t.id, None)
    _save({"color": color, "snapshots": snaps} if snaps else None)
    return errors


def restore() -> tuple[dict[str, str], list[str]]:
    """Put every synced device's lighting back. Returns ({device id: error}, notes). Devices that
    failed (e.g. unplugged) keep their snapshot, so restoring again later still works."""
    st = _load()
    snaps = st.get("snapshots", {})
    errors, notes, left = {}, [], {}
    for t in TARGETS:
        if t.id not in snaps:
            continue
        try:
            if not t.present():
                raise RigdeckError(f"{t.name.lower()} not connected")
            note = t.restore(snaps[t.id])
            if note:
                notes.append(note)
        except Exception as e:
            errors[t.id] = str(e)
            left[t.id] = snaps[t.id]
    _save({**st, "snapshots": left} if left else None)
    return errors, notes


# ---- CLI ------------------------------------------------------------------------------

def _report(errors: dict[str, str]):
    names = {t.id: t.name for t in TARGETS}
    for tid, e in errors.items():
        print(f"  {names[tid]}: {e}")


def cli_status(a):
    s = status()
    print("Synced to #" + s["color"] if s["active"] else "Not synced: every device has its own lighting")
    for d in s["devices"]:
        state = ("synced" if d["synced"] else "own lighting") if d["present"] else "not connected"
        print(f"  {d['name']:<14}{state}")


def cli_sync(a):
    errors = sync(a.color, a.only)
    done = [d["name"] for d in status()["devices"] if d["synced"] and d["present"] and d["id"] not in errors]
    print(f"#{_color(a.color)} on {', '.join(done)}" if done else "no device changed")
    _report(errors)


def cli_restore(a):
    errors, notes = restore()
    print("lighting restored" if not errors else "some devices could not be restored:")
    _report(errors)
    for n in notes:
        print(f"  note: {n}")


class LightingModule(Module):
    id = "lighting"
    title = "Lighting"
    icon = "lightbulb"
    order = 60

    def detect(self) -> bool:
        return any(t.present() for t in TARGETS)

    def add_cli(self, sub):
        p = sub.add_parser("lighting", help="one colour on every device with lighting, and back")
        p.set_defaults(func=cli_status)
        ls = p.add_subparsers(dest="lighting_cmd")
        s = ls.add_parser("sync", help="set one colour on every device (remembers their own lighting)")
        s.add_argument("color", help="RRGGBB, e.g. 00c8ff")
        s.add_argument("--only", nargs="+", choices=[t.id for t in TARGETS], help="just these devices")
        s.set_defaults(func=cli_sync)
        ls.add_parser("restore", help="every device back to its own lighting from before the sync")\
            .set_defaults(func=cli_restore)

    def qml_page(self):
        return os.path.join(os.path.dirname(__file__), "qml", "LightingPage.qml")

    def qt_backend(self, app):
        from .qt import LightingBackend
        return LightingBackend(app)
