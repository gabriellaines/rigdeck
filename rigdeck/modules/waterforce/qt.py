"""`cooler` in QML: live state and actions for the AORUS WATERFORCE X II page."""
from __future__ import annotations

import os
import threading

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot

from ... import config
from ...gui.bridge import run_async
from ...sensors import CpuSensors
from . import Screen, add_to_carousel, delete_media, effects, media, set_led
from .device import (FAN_MODES, PUMP_MODES, Cooler, CoolerError, SpeedMode, SpeedType,
                     preset_curve)

FAN_LABELS = {SpeedMode.DEFAULT: "Default", SpeedMode.ZERO_RPM: "Zero RPM", SpeedMode.QUIET: "Quiet",
              SpeedMode.BALANCED: "Balanced", SpeedMode.PERFORMANCE: "Performance",
              SpeedMode.TURBO: "Turbo", SpeedMode.CUSTOMIZED: "Custom"}
PUMP_LABELS = {SpeedMode.BALANCED: "Balanced", SpeedMode.TURBO: "Turbo"}


def _pts(points):
    return [{"t": t, "rpm": r} for t, r in points] if points else []


class CoolerBackend(QObject):
    stateChanged = Signal()      # connection / identity
    liveChanged = Signal()       # rpm, temperature
    coolingChanged = Signal()    # modes, curves, dirty
    ledChanged = Signal()
    screenChanged = Signal()
    toast = Signal(str)

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._cooler: Cooler | None = None
        self._sensors = CpuSensors()
        self._connected = False
        self._identity = {"model": "AORUS WATERFORCE X II", "firmware": "", "usb": "USB 0414:7a5e"}
        self._live = {"fan": None, "pump": None, "cpu": None}
        self._fan, self._pump = SpeedMode.BALANCED, SpeedMode.BALANCED
        self._custom: list[tuple[int, int]] = []
        self._saved = None
        self._led = dict(effects.DEFAULTS)
        self._led.update({k: v for k, v in config.section(config.load(), "cooler", "led").items()
                          if k in effects.DEFAULTS})
        self._screen: Screen | None = None
        self._files: list[str] = []
        self._playing: set[str] = set()
        self._single = False
        self._interval = 5
        self._free_mb = 0.0
        self._rotation, self._fahrenheit = 0, False
        self._busy = ""
        self._progress = -1.0
        self._led_timer = QTimer(self, singleShot=True, interval=150, timeout=self._send_led)
        self._screen_timer = QTimer(self, singleShot=True, interval=400, timeout=self._send_screen)
        self._poll_timer = QTimer(self, interval=2000, timeout=self._poll)
        self._poll_timer.start()
        self.reload()

    # ---- device access ------------------------------------------------------

    def _with(self, fn):
        """Run fn(cooler) holding the device lock (worker thread)."""
        with self._lock:
            if self._cooler is None:
                self._cooler = Cooler()
            try:
                return fn(self._cooler)
            except Exception:
                try:
                    self._cooler.close()
                except OSError:
                    pass
                self._cooler = None
                raise

    def _do(self, fn, done=None, what="talk to the cooler"):
        def failed(e):
            self._set_connected(not isinstance(e, CoolerError))
            self.toast.emit(f"Could not {what}: {e}")
        run_async(lambda: self._with(fn), done, failed)

    def _set_connected(self, ok: bool):
        if ok != self._connected:
            self._connected = ok
            self.stateChanged.emit()

    def _poll(self):
        self._live["cpu"] = self._sensors.temperature() or None
        if self._lock.locked():  # uploads/deletes take a while; skip a beat
            self.liveChanged.emit()
            return

        def got(rpm):
            self._set_connected(True)
            self._live["fan"], self._live["pump"] = rpm
            self.liveChanged.emit()

        def failed(_e):
            self._set_connected(False)
            self._live["fan"] = self._live["pump"] = None
            self.liveChanged.emit()
        run_async(lambda: self._with(lambda c: c.rpm()), got, failed)

    @Slot()
    def reload(self):
        def read(c: Cooler):
            return {"model": c.model(), "firmware": c.firmware(), "modes": c.modes(),
                    "curve": c.curve(SpeedType.FAN), "rotation": c.rotation(),
                    "fahrenheit": c.temp_unit_fahrenheit(), "screen": Screen.read(c),
                    "free": c.storage_free_kb()}

        def done(s):
            self._set_connected(True)
            self._identity["model"] = s["model"].replace("GP-", "")
            self._identity["firmware"] = s["firmware"]
            self._fan, self._pump = s["modes"]
            self._custom = list(s["curve"])
            self._saved = (self._fan, self._pump, list(self._custom))
            self._rotation, self._fahrenheit = s["rotation"], s["fahrenheit"]
            self._apply_screen(s["screen"], s["free"])
            self.stateChanged.emit()
            self.coolingChanged.emit()

        def failed(e):
            self._set_connected(False)
            self.stateChanged.emit()
        run_async(lambda: self._with(read), done, failed)

    # ---- identity / live ------------------------------------------------------

    connected = Property(bool, lambda self: self._connected, notify=stateChanged)
    identity = Property("QVariantMap", lambda self: self._identity, notify=stateChanged)
    live = Property("QVariantMap", lambda self: self._live, notify=liveChanged)
    busy = Property(str, lambda self: self._busy, notify=screenChanged)

    # ---- cooling --------------------------------------------------------------

    fanModes = Property("QVariantList", lambda self: [FAN_LABELS[m] for m in FAN_MODES], constant=True)
    pumpModes = Property("QVariantList", lambda self: [PUMP_LABELS[m] for m in PUMP_MODES], constant=True)
    fanMode = Property(int, lambda self: FAN_MODES.index(self._fan) if self._fan in FAN_MODES else 0,
                       notify=coolingChanged)
    pumpMode = Property(int, lambda self: PUMP_MODES.index(self._pump) if self._pump in PUMP_MODES else 0,
                        notify=coolingChanged)
    fanModeName = Property(str, lambda self: FAN_LABELS.get(self._fan, ""), notify=coolingChanged)
    pumpModeName = Property(str, lambda self: PUMP_LABELS.get(self._pump, ""), notify=coolingChanged)
    curveEditable = Property(bool, lambda self: self._fan == SpeedMode.CUSTOMIZED, notify=coolingChanged)

    def _fan_curve(self):
        if self._fan == SpeedMode.CUSTOMIZED:
            return self._custom
        return preset_curve(SpeedType.FAN, self._fan)

    fanCurve = Property("QVariantList", lambda self: _pts(self._fan_curve()), notify=coolingChanged)
    pumpCurve = Property("QVariantList", lambda self: _pts(preset_curve(SpeedType.PUMP, self._pump)),
                         notify=coolingChanged)
    dirty = Property(bool, lambda self: self._saved is not None and
                     (self._fan, self._pump, self._custom) != self._saved, notify=coolingChanged)

    @Property(str, notify=coolingChanged)
    def curveHint(self):
        if self._fan == SpeedMode.CUSTOMIZED:
            return "Drag the points (or select one and use the arrow keys) to shape the fan curve."
        if self._fan == SpeedMode.ZERO_RPM:
            return "Zero RPM: fans stop at low temperature and spin up under load; the curve is set by the cooler."
        return "Preset curve — choose Custom to edit it."

    @Slot(int)
    def setFanMode(self, i):
        self._fan = FAN_MODES[i]
        self.coolingChanged.emit()

    @Slot(int)
    def setPumpMode(self, i):
        self._pump = PUMP_MODES[i]
        self.coolingChanged.emit()

    @Slot(int, int, int)
    def setCurvePoint(self, i, t, rpm):
        if self._fan != SpeedMode.CUSTOMIZED or not 0 <= i < len(self._custom):
            return
        lo = self._custom[i - 1][0] + 1 if i > 0 else 0
        hi = self._custom[i + 1][0] - 1 if i < len(self._custom) - 1 else 100
        self._custom[i] = (max(lo, min(hi, int(t))), max(0, min(3200, int(round(rpm / 10) * 10))))
        self.coolingChanged.emit()

    @Slot()
    def applyCooling(self):
        fan, pump, curve = self._fan, self._pump, list(self._custom)

        def done(_):
            self._saved = (fan, pump, curve)
            self.coolingChanged.emit()
            self.toast.emit("Saved to the cooler")
        self._do(lambda c: c.set_modes(fan, pump, curve if fan == SpeedMode.CUSTOMIZED else None),
                 done, "apply the cooling settings")

    @Slot()
    def revertCooling(self):
        if self._saved:
            self._fan, self._pump, custom = self._saved
            self._custom = list(custom)
            self.coolingChanged.emit()

    # ---- lighting -------------------------------------------------------------

    @Property("QVariantList", constant=True)
    def ledEffects(self):
        return [{"id": e, "label": effects.LABELS[e], "usesColor": e in effects.USES_COLOR,
                 "animated": e in effects.SOFTWARE} for e in effects.ALL]

    led = Property("QVariantMap", lambda self: self._led, notify=ledChanged)

    @Slot(str, str, int, int)
    def setLed(self, effect, color, brightness, speed):
        self._led = {"effect": effect, "color": color.lstrip("#").lower()[:6] or "ffffff",
                     "brightness": brightness, "speed": speed}
        self.ledChanged.emit()
        self._led_timer.start()

    def _send_led(self):
        led = dict(self._led)

        def done(msg):
            if msg != "applied":
                self.toast.emit(msg)
        run_async(lambda: set_led(led["effect"], led["color"], led["brightness"], led["speed"]), done,
                  lambda e: self.toast.emit(f"Could not set lighting: {e}"))

    # ---- screen ---------------------------------------------------------------

    def _apply_screen(self, screen: Screen, free_kb: int):
        self._screen = screen
        self._files = list(screen.files)
        self._playing = set(screen.playing)
        self._single = len(self._playing) == 1
        self._interval = screen.interval
        self._free_mb = free_kb / 1024
        self.screenChanged.emit()

    @Property("QVariantList", notify=screenChanged)
    def files(self):
        order = [n for n in self._files if n in self._playing]
        out = []
        for n in self._files:
            prev = media.preview_path(n)
            out.append({"name": n, "playing": n in self._playing,
                        "position": order.index(n) + 1 if n in self._playing else 0,
                        "preview": QUrl.fromLocalFile(prev).toString() if os.path.exists(prev) else ""})
        return out

    single = Property(bool, lambda self: self._single, notify=screenChanged)
    interval = Property(int, lambda self: self._interval, notify=screenChanged)
    freeMb = Property(float, lambda self: self._free_mb, notify=screenChanged)
    rotation = Property(int, lambda self: self._rotation, notify=screenChanged)
    fahrenheit = Property(bool, lambda self: self._fahrenheit, notify=screenChanged)
    uploadProgress = Property(float, lambda self: self._progress, notify=screenChanged)

    def _changed_screen(self):
        self.screenChanged.emit()
        self._screen_timer.start()

    @Slot(bool)
    def setSingle(self, single):
        if single == self._single or not self._files:
            return
        self._single = single
        if single:
            self._playing = {next((n for n in self._files if n in self._playing), self._files[0])}
        self._changed_screen()

    @Slot(str, bool)
    def setPlaying(self, name, on):
        if self._single:
            if on:
                self._playing = {name}
        elif on:
            self._playing.add(name)
        elif len(self._playing) > 1:
            self._playing.discard(name)
        else:
            self.toast.emit("At least one animation has to stay on")
            self.screenChanged.emit()
            return
        self._changed_screen()

    @Slot(str, int)
    def move(self, name, delta):
        i = self._files.index(name)
        j = i + delta
        if 0 <= j < len(self._files):
            self._files[i], self._files[j] = self._files[j], self._files[i]
            self._changed_screen()

    @Slot(int)
    def setInterval(self, seconds):
        if seconds != self._interval:
            self._interval = seconds
            self._changed_screen()

    def _send_screen(self):
        if not self._screen:
            return
        files, interval, screen = list(self._files), self._interval, self._screen
        playing = [n for n in files if n in self._playing]
        self._do(lambda c: screen.write(c, files, playing, interval), None, "update the screen")

    def _set_busy(self, text, progress=-1.0):
        self._busy, self._progress = text, progress
        self.screenChanged.emit()

    @Slot(str)
    def deleteFile(self, name):
        if self._busy:
            return
        self._set_busy(f"Deleting {name}…")
        before = self._screen

        def done(r):
            self._set_busy("")
            self._apply_screen(*r)
            try:
                os.remove(media.preview_path(name))
            except OSError:
                pass
            self.toast.emit(f"Deleted {name}")

        def failed(e):
            self._set_busy("")
            self.toast.emit(f"Could not delete {name}: {e}")
            self.reload()
        run_async(lambda: self._with(lambda c: (delete_media(c, name, before), c.storage_free_kb())),
                  done, failed)

    @Slot(str)
    def upload(self, url):
        if self._busy:
            return
        path = QUrl(url).toLocalFile() or url
        try:
            name = media.target_name(path)
        except media.MediaError as e:
            self.toast.emit(str(e))
            return
        self._set_busy("Converting…", 0.0)

        def progress(done, total):
            from ...gui.bridge import on_main
            on_main(lambda: self._set_busy(f"Uploading {name}… {100 * done // total}%", done / total))

        def work(c: Cooler):
            data = media.convert(path)
            media.make_preview(path, name)
            if len(data) > c.storage_free_kb() * 1024:
                raise media.MediaError("not enough space on the cooler")
            c.upload_media(data, name, progress)
            return add_to_carousel(c, name), c.storage_free_kb()

        def done(r):
            self._set_busy("")
            self._apply_screen(*r)
            self.toast.emit(f"Uploaded {name} — it's now playing")

        def failed(e):
            self._set_busy("")
            self.toast.emit(f"Upload failed: {e}")
        run_async(lambda: self._with(work), done, failed)

    @Slot(int)
    def setRotation(self, degrees):
        self._rotation = degrees
        self.screenChanged.emit()
        self._do(lambda c: (c.set_rotation(degrees), c.save()), None, "rotate the screen")

    @Slot(bool)
    def setFahrenheit(self, f):
        self._fahrenheit = f
        self.screenChanged.emit()
        self._do(lambda c: (c.set_temp_unit(f), c.save()), None, "change the unit")
