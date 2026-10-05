"""`keyboard` in QML: identity, lighting brightness, analog settings (read-only)."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from ...gui.activity import AdaptiveTimer
from ...gui.bridge import run_async
from ... import servicectl
from . import (BRIGHTNESS_PRESETS, analog, analog_state, apply_custom, connected, custom, custom_lighting,
               edit_keys, effective, from_keyboard, read_state, save_custom, save_lighting, set_brightness)
from .keymap import KEYS, LABELS, LAYOUT, MEDIA_LAYOUT, zone

KEY_IDS = {v: k for k, v in KEYS.items()}

POLL_MS = 10000   # picks up brightness changed with the Fn key


class KeyboardBackend(QObject):
    stateChanged = Signal()
    toast = Signal(str)

    def __init__(self):
        super().__init__()
        self._state: dict = {}
        self._dev: dict | None = None
        self._status = "loading"   # loading | ok | none | error
        self._error = ""
        self._busy = False
        self._jobs: dict = {}            # waiting keyboard jobs, oldest first
        self._reading = False
        self._analog: list = []
        self._analog_status = "idle"   # idle | loading | ok | error
        self._timer = AdaptiveTimer(self, self.refresh, page="keyboard", page_ms=POLL_MS, visible_ms=60000)
        self.refresh()

    @Slot()
    def refresh(self):
        if self._reading or self._busy:
            return
        self._reading = True

        def read():
            kbs = connected()
            return (kbs[0], read_state(kbs[0])) if kbs else (None, None)

        def got(r):
            self._reading = False
            self._dev, st = r
            self._state = st or {}
            if not st:
                self._analog, self._analog_status = [], "idle"     # read again when it's back
            self._status = "ok" if st else "none"
            self._error = ""
            self.stateChanged.emit()
            if st and self._analog_status == "idle":
                self.refreshAnalog()

        def failed(e):
            self._reading = False
            self._status, self._error = "error", str(e)
            self.stateChanged.emit()
        run_async(read, got, failed)

    # ---- analog settings: ~150 small reads, so once per connection and on demand, not polled

    analogChanged = Signal()

    @Slot()
    def refreshAnalog(self):
        if self._analog_status == "loading" or not self._dev:
            return
        self._analog_status = "loading"
        self.analogChanged.emit()
        dev = self._dev

        def got(profiles):
            self._analog, self._analog_status = profiles, "ok"
            self.analogChanged.emit()

        def failed(e):
            self._analog_status = "error"
            self.toast.emit(f"Could not read the analog settings: {e}")
            self.analogChanged.emit()
        run_async(lambda: analog_state(dev), got, failed)

    analog = Property("QVariantList", lambda self: self._analog, notify=analogChanged)
    keyNames = Property("QVariantList", lambda self: list(KEYS.values()), constant=True)
    layout = Property("QVariantList", lambda self: [
        {"name": n, "label": LABELS.get(n, n), "x": x, "y": y + 1.1, "w": w, "analog": analog_key}
        for layout, analog_key in ((LAYOUT, True), (MEDIA_LAYOUT, False)) for n, x, y, w in layout], constant=True)

    def _per_key(self, n) -> dict[int, dict]:
        """What profile n does per key: RigDeck's settings if on, else the keyboard's own."""
        c = custom(n)
        if c:
            default, keys, rapid = effective(c)
            return {kid: {"act": keys.get(kid, default), "rapid": rapid.get(kid, 0),
                          "own": kid in c["keys"] or kid in c["rapidKeys"]} for kid in KEYS}
        p = next((p for p in self._analog if p["index"] == n), None)
        return {KEY_IDS[name]: v for name, v in p["perKey"].items()} if p else {}

    @Slot(int, result="QVariantMap")
    def keyValues(self, n):
        """name -> {act, rapid, color}; color only when RigDeck's colours are on for profile n."""
        out = {KEYS[kid]: dict(v) for kid, v in self._per_key(n).items()}
        li = custom_lighting(n)
        if li:
            from .lighting import LIT_KEYS
            for name in LIT_KEYS:
                out.setdefault(name, {})["color"] = li["keys"].get(name, li["base"])
        return out

    @Slot()
    def lightingChangedElsewhere(self):
        """Colours were changed outside this page (Lighting sync): show them."""
        self.analogChanged.emit()

    @Slot(int, result="QVariant")
    def lightingFor(self, n):
        return custom_lighting(n)

    @Slot(int, "QVariantList", str)
    def setColors(self, n, names, color):
        """Colour the given keys (color '' = back to the background colour)."""
        li = custom_lighting(n) or {"base": "ffffff", "keys": {}}
        keys = dict(li["keys"])
        for name in (x for x in names if zone(x) is not None):     # keys without an LED (Fn) are skipped
            if color and color.lower() != li["base"]:
                keys[name] = color.lower()
            else:
                keys.pop(name, None)
        self._change_lights(n, {"base": li["base"], "keys": keys})

    @Slot(int, str)
    def setBaseColor(self, n, color):
        li = custom_lighting(n) or {"base": "ffffff", "keys": {}}
        self._change_lights(n, {"base": color.lower(), "keys": li["keys"]})

    @Slot(int)
    def resetLighting(self, n):
        self._change_lights(n, None)

    def _change_lights(self, n, s):
        self._run_change(n, lambda: save_lighting(n, s), analog_part=False, lights_part=True, saved=s is not None)

    @Slot(int, result="QVariantMap")
    def profileWide(self, n):
        """{act, rapid, own: number of keys with their own settings} for profile n (0.1 mm)."""
        c = custom(n) or from_keyboard(self._per_key(n)) if self._per_key(n) else None
        if not c:
            return {}
        own = set(c["keys"]) | set(c["rapidKeys"])
        return {"act": c["actuation"], "rapid": c["rapid"], "own": len(own), "custom": custom(n) is not None}

    @Slot(int, "QVariantMap")
    def setProfileWide(self, n, patch):
        """Every key of profile n (keys with their own settings keep them): patch {act?, rapid?}."""
        s = custom(n) or from_keyboard(self._per_key(n))
        s = {**s, "keys": dict(s["keys"]), "rapidKeys": dict(s["rapidKeys"])}
        if "act" in patch:
            s["actuation"] = int(patch["act"])
            s["keys"] = {k: v for k, v in s["keys"].items() if v != s["actuation"]}
        if "rapid" in patch:
            s["rapid"] = int(patch["rapid"])
            s["rapidKeys"] = {k: v for k, v in s["rapidKeys"].items() if v != s["rapid"]}
        self._change(n, s)

    @Slot(int, "QVariantList")
    def clearOwn(self, n, names):
        """Selected keys (all if empty) follow the profile-wide settings again."""
        s = custom(n)
        if not s:
            return
        ids = {KEY_IDS[x] for x in names if x in KEY_IDS} or set(KEYS)
        self._change(n, {**s, "keys": {k: v for k, v in s["keys"].items() if k not in ids},
                         "rapidKeys": {k: v for k, v in s["rapidKeys"].items() if k not in ids}})

    @Slot(int, "QVariantList", "QVariantMap")
    def setKeys(self, n, names, patch):
        """Change the selected keys of profile n: patch {act?, rapid?} in 0.1 mm (rapid 0 = off).
        Turns RigDeck settings on for that profile, starting from what it does now."""
        base = custom(n) or from_keyboard(self._per_key(n))
        ids = [KEY_IDS[x] for x in names if x in KEY_IDS]      # media keys have no analog switch
        self._change(n, edit_keys(base, ids, act=patch.get("act"), rapid=patch.get("rapid")))

    @Property("QVariantList", notify=analogChanged)
    def custom(self):
        """RigDeck's settings per profile (None = the keyboard's own), keys by name, values in 0.1 mm."""
        out = []
        for n in (1, 2, 3):
            c = custom(n)
            out.append(None if c is None else {
                "actuation": c["actuation"], "rapid": c["rapid"],
                "keys": [{"name": KEYS[k], "value": v} for k, v in sorted(c["keys"].items())],
                "rapidKeys": [{"name": KEYS[k], "value": v} for k, v in sorted(c["rapidKeys"].items())]})
        return out

    @Slot(int, "QVariantMap")
    def setCustom(self, n, s):
        """s: {actuation, rapid, keys: {name: value}, rapidKeys: {name: value}}; values in 0.1 mm."""
        settings = {"actuation": int(s["actuation"]), "rapid": int(s.get("rapid", 0)),
                    "keys": {KEY_IDS[k]: int(v) for k, v in (s.get("keys") or {}).items()},
                    "rapidKeys": {KEY_IDS[k]: int(v) for k, v in (s.get("rapidKeys") or {}).items()}}
        self._change(n, settings)

    @Slot(int)
    def resetCustom(self, n):
        self._change(n, None)

    def _change(self, n, settings):
        self._run_change(n, lambda: save_custom(n, settings), analog_part=True, lights_part=False,
                         saved=settings is not None)

    def _run_change(self, n, save, analog_part, lights_part, saved):
        """Save now (so the next change builds on it); put it on the keyboard in the background."""
        if not self._dev:
            return
        save()
        self.analogChanged.emit()                  # the page shows the new values straight away
        dev = self._dev

        def work():
            servicectl.reload()                     # the service keeps them on after profile switches
            # reads the config when it runs: a burst of changes ends up as one write of the latest
            return apply_custom(dev, n, analog_part=analog_part, lights_part=lights_part)

        def done(active):
            if not active and saved:
                self.toast.emit(f"Saved. They take effect when profile {n} is active ({analog.PROFILE_KEYS[n - 1]}).")
        self._enqueue(("profile", n, analog_part, lights_part), work, done)

    # ---- one keyboard job at a time; a newer job of the same kind replaces a waiting one

    def _enqueue(self, key, work, done=None):
        self._jobs[key] = (work, done)
        if not self._busy:
            self._next()

    def _next(self):
        if not self._jobs:
            if self._busy:
                self._busy = False
                self.stateChanged.emit()
            return
        key = next(iter(self._jobs))
        work, done = self._jobs.pop(key)
        self._busy = True

        def ok(r):
            if done:
                done(r)
            self._next()

        def failed(e):
            self.toast.emit(f"Could not change the keyboard: {e}")
            self._jobs.clear()
            self._busy = False
            self.stateChanged.emit()
            self.analogChanged.emit()
            self.refresh()
        run_async(work, ok, failed)
    analogStatus = Property(str, lambda self: self._analog_status, notify=analogChanged)

    state = Property("QVariantMap", lambda self: self._state, notify=stateChanged)
    status = Property(str, lambda self: self._status, notify=stateChanged)
    error = Property(str, lambda self: self._error, notify=stateChanged)
    busy = Property(bool, lambda self: self._busy, notify=stateChanged)
    presets = Property("QVariantList", lambda self: BRIGHTNESS_PRESETS, constant=True)

    @Property("QVariantMap", notify=stateChanged)
    def summary(self):
        s, st = self._state, self._status
        return {"id": "keyboard", "icon": "keyboard", "title": s.get("name") or "Keyboard",
                "detail": f"USB 046d:{s['pid']}" if s.get("pid") else "",
                "status": {"ok": "Connected", "none": "Not found", "loading": "…", "error": "Error"}[st],
                "connected": st == "ok", "tone": "live" if st == "ok" else "warning", "battery": None}

    @Slot(int)
    def setBrightness(self, value):
        if not self._dev:
            return
        self._state = {**self._state, "brightness": value}     # show it right away
        self.stateChanged.emit()
        dev = self._dev
        self._enqueue(("brightness",), lambda: set_brightness(dev, value))
