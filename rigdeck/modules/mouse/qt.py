"""`mouse` in QML: connected mice, settings (written to the mouse's flash) and battery.

Polling is tiered to stay cheap:
  * every 2 s   which mice are plugged in (sysfs only, no talking to the mice)
  * every 10 s  full settings of the mouse shown, only while the Mouse page is open
  * every 60 s  battery of every mouse (for the Overview), one request each
Each mouse keeps its last known state, so switching between mice doesn't blank the page.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from ...gui.activity import AdaptiveTimer, activity
from ...gui.bridge import run_async
from . import MAX_STAGES, MODELS, backup, change, compx, connected, read_battery, read_state

HOTPLUG_MS, PAGE_MS, BATTERY_MS = 2000, 10000, 60000


class MouseBackend(QObject):
    miceChanged = Signal()
    stateChanged = Signal()
    toast = Signal(str)

    def __init__(self):
        super().__init__()
        self._mice: list[dict] = []        # [{node, pid, model}]
        self._states: dict[str, dict] = {}   # node -> last known state (full or battery-only)
        self._errors: dict[str, str] = {}
        self._index = 0
        self._io = False                   # one request to the mice at a time
        self._busy = False                 # a write is in progress
        self._loaded = False
        self._full_pending = False         # a full read was asked for while another request ran
        AdaptiveTimer(self, self._hotplug, visible_ms=HOTPLUG_MS)
        AdaptiveTimer(self, self._read_full, page="mouse", page_ms=PAGE_MS)
        AdaptiveTimer(self, self._battery_tick, visible_ms=BATTERY_MS)
        self._hotplug()

    # ---- polling -------------------------------------------------------------------------

    def _dev(self) -> dict | None:
        return self._mice[self._index] if self._index < len(self._mice) else None

    def _hotplug(self):
        mice = connected()
        if [m["node"] for m in mice] == [m["node"] for m in self._mice] and self._loaded:
            return
        current = self._dev()
        self._mice, self._loaded = mice, True
        nodes = {m["node"] for m in mice}
        self._states = {n: s for n, s in self._states.items() if n in nodes}
        # stay on the same mouse if it's still there (cable <-> receiver swaps change the node)
        self._index = next((i for i, m in enumerate(mice) if current and m["model"] == current["model"]), 0)
        self.miceChanged.emit()
        self.stateChanged.emit()
        self._battery_tick()
        if activity().page == "mouse":
            self._read_full()

    def _job(self, fn, done):
        """Run one mouse request off the UI thread; skipped if another is in flight (timers retry)."""
        if self._io or self._busy:
            return False
        self._io = True

        def finish():
            self._io = False
            if self._full_pending:
                self._full_pending = False
                self._read_full()

        def ok(r):
            done(r)
            finish()

        def failed(e):
            self.stateChanged.emit()
            finish()
        run_async(fn, ok, failed)
        return True

    def _read_full(self):
        dev = self._dev()
        if not dev:
            return

        def got(st):
            prev = self._states.get(dev["node"], {})
            # asleep: keep the last known settings, just mark it asleep
            self._states[dev["node"]] = {**prev, **st} if st["asleep"] and "stages" in prev else st
            self._errors.pop(dev["node"], None)
            self.stateChanged.emit()

        def fn():
            try:
                return read_state(dev)
            except compx.MouseError as e:
                self._errors[dev["node"]] = str(e)
                raise
        if not self._job(fn, got):
            self._full_pending = True

    def _battery_tick(self):
        mice = list(self._mice)
        if not mice:
            return

        def fn():
            out = {}
            for d in mice:
                try:
                    out[d["node"]] = read_battery(d)
                except compx.MouseError as e:
                    out[d["node"]] = {"error": str(e)}
            return out

        def got(res):
            for node, st in res.items():
                if "error" in st:
                    self._errors[node] = st["error"]
                    continue
                self._errors.pop(node, None)
                self._states[node] = {**self._states.get(node, {}), **st}
            self.stateChanged.emit()
        self._job(fn, got)

    @Slot()
    def refresh(self):
        self._read_full()

    # ---- state for QML -------------------------------------------------------------------

    def _status(self, dev) -> str:
        if not dev:
            return "none" if self._loaded else "loading"
        st = self._states.get(dev["node"])
        if st is None:
            return "error" if dev["node"] in self._errors else "loading"
        return "asleep" if st.get("asleep") else "ok" if "stages" in st else "loading"

    @Property("QVariantList", notify=miceChanged)
    def mice(self):
        return [{"name": MODELS[d["model"]]["name"], "node": d["node"]} for d in self._mice]

    index = Property(int, lambda self: self._index, notify=miceChanged)
    state = Property("QVariantMap", lambda self: self._states.get(self._dev()["node"], {}) if self._dev() else {},
                     notify=stateChanged)
    status = Property(str, lambda self: self._status(self._dev()), notify=stateChanged)
    error = Property(str, lambda self: self._errors.get(self._dev()["node"], "") if self._dev() else "",
                     notify=stateChanged)
    busy = Property(bool, lambda self: self._busy, notify=stateChanged)
    maxStages = Property(int, lambda self: MAX_STAGES, constant=True)
    rates = Property("QVariantList", lambda self: sorted(compx.RATE_CODES), constant=True)

    @Property("QVariantList", notify=stateChanged)
    def summaries(self):
        """One Overview row per mouse."""
        rows = []
        for d in self._mice:
            s, st = self._states.get(d["node"], {}), self._status(d)
            b = s.get("battery") or {}
            status = {"ok": "Connected", "asleep": "Asleep", "loading": "…", "error": "Not answering",
                      "none": ""}[st]
            awake_battery = bool(b) and not s.get("asleep")   # known from the background battery read
            if awake_battery:
                status = f"{b['level']}% battery" + (" · charging" if b.get("charging") else "")
            rows.append({"id": "mouse", "icon": "mouse", "title": s.get("name") or MODELS[d["model"]]["name"],
                         "detail": MODELS[d["model"]]["pids"][d["pid"]].capitalize(), "status": status,
                         "connected": st in ("ok", "asleep") or awake_battery,
                         "tone": "live" if st == "ok" or awake_battery else "warning",
                         "battery": b.get("level")})
        return rows

    @Property("QVariantMap", notify=stateChanged)
    def summary(self):
        rows = self.summaries
        return rows[0] if rows else {"id": "mouse", "icon": "mouse", "title": "Mouse", "detail": "",
                                     "status": "Not found", "connected": False, "tone": "warning"}

    @Slot(int)
    def select(self, i):
        if 0 <= i < len(self._mice) and i != self._index:
            self._index = i
            self.miceChanged.emit()
            self.stateChanged.emit()   # shows the cached state right away; the read refreshes it
            self._read_full()

    # ---- writing -------------------------------------------------------------------------

    def _write(self, changes: dict, done_text: str = ""):
        dev = self._dev()
        if self._busy or not dev:
            return
        self._busy = True
        self.stateChanged.emit()

        def work():
            if "stages" in changes:   # list of (index, dpi)
                for i, dpi in changes.pop("stages"):
                    change(dev, {"stage": (i, dpi)})
            if changes:
                change(dev, changes)

        def done(_):
            self._busy = False
            if done_text:
                self.toast.emit(done_text)
            self._read_full()

        def failed(e):
            self._busy = False
            self.toast.emit(f"Could not change the mouse: {e}")
            self._read_full()
        run_async(work, done, failed)

    @Slot(int)
    def setRate(self, hz):
        self._write({"rate": hz})

    @Slot(str, bool)
    def setSwitch(self, key, on):
        self._write({key: on})

    @Slot(int)
    def setCurrentStage(self, i):
        self._write({"currentStage": i})

    @Slot("QVariantList", int)
    def applyStages(self, dpis, count):
        """All stage DPIs (first `count` used) and the number of stages, in one go."""
        self._write({"stages": [(i, int(d)) for i, d in enumerate(dpis[:count])], "stageCount": int(count)},
                    "DPI stages saved on the mouse")

    @Slot(int, str)
    def setStageColor(self, i, color):
        self._write({"color": (i, color)})

    @Slot("QVariantMap")
    def setLed(self, led):
        self._write({"led": dict(led)})

    @Slot()
    def backupNow(self):
        dev = self._dev()
        if not dev:
            return

        def work():
            with compx.Mouse(dev["node"]) as m:
                return backup(m, dev["model"])
        run_async(work, lambda p: self.toast.emit(f"Saved to {p}"),
                  lambda e: self.toast.emit(f"Backup failed: {e}"))
