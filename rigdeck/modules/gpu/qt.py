"""`gpu` in QML: GPU telemetry and fan / power controls through LACT."""
from __future__ import annotations

import shutil
import subprocess

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from ...gui.bridge import run_async
from . import DEFAULT_CURVE, enable_overdrive, fan_controls_available, overdrive_plan, read_state
from .lact import Lact, LactUnavailable, installed

POLL_MS = 2000


class GpuBackend(QObject):
    stateChanged = Signal()     # availability / identity / live numbers
    fanChanged = Signal()       # editable fan settings
    powerChanged = Signal()
    confirmChanged = Signal()
    toast = Signal(str)

    def __init__(self):
        super().__init__()
        self._lact = Lact()
        self._status = "loading"   # loading | ok | not-installed | not-running | no-permission | error
        self._error = ""
        self._s: dict = {}
        self._reboot_needed = False
        # editable fan settings (UI side) and the last applied copy
        self._fan = {"mode": "auto", "zero_rpm": None, "zero_rpm_temp": None, "speed": 50,
                     "curve": dict(DEFAULT_CURVE)}
        self._fan_saved = None
        self._cap = None
        self._confirm_left = 0
        self._confirm_timer = QTimer(self, interval=1000, timeout=self._tick_confirm)
        self._poll_timer = QTimer(self, interval=POLL_MS, timeout=self.refresh)
        self._poll_timer.start()
        self.refresh()

    # ---- polling -------------------------------------------------------------------

    @Slot()
    def refresh(self):
        def failed(e):
            if isinstance(e, LactUnavailable):
                if not installed():
                    st = "not-installed"
                elif "permission" in str(e):
                    st = "no-permission"
                else:
                    st = "not-running"
            else:
                st = "error"
            if st != self._status or str(e) != self._error:
                self._status, self._error = st, str(e)
                self.stateChanged.emit()
        run_async(lambda: read_state(self._lact), self._got, failed)

    def _got(self, s: dict):
        first = self._fan_saved is None
        self._s, self._status, self._error = s, "ok", ""
        self.stateChanged.emit()  # first, so the power slider has its range before its value
        if first:
            self._load_fan(s)
            self._cap = s["power"].get("cap_current")
            self.powerChanged.emit()

    def _load_fan(self, s):
        zt = s.get("zero_rpm_temp") or {}
        self._fan = {"mode": s["fan_mode"] if s["fan_custom"] else "auto",
                     "zero_rpm": s.get("zero_rpm"),
                     "zero_rpm_temp": zt.get("current"),
                     "speed": round(100 * (s.get("static_speed") or 0.5)),
                     "curve": dict(s["curve"])}
        self._fan_saved = self._copy_fan()
        self.fanChanged.emit()

    def _copy_fan(self):
        return {**self._fan, "curve": dict(self._fan["curve"])}

    # ---- availability / identity / live ---------------------------------------------

    status = Property(str, lambda self: self._status, notify=stateChanged)
    error = Property(str, lambda self: self._error, notify=stateChanged)
    rebootNeeded = Property(bool, lambda self: self._reboot_needed, notify=stateChanged)

    @Property("QVariantMap", notify=stateChanged)
    def info(self):
        s = self._s
        if not s:
            return {}
        p = s["power"]
        zt = s.get("zero_rpm_temp") or {}
        return {"name": s["name"], "lact": s["lact_version"], "overdrive": bool(s["overdrive"]),
                "fanControls": fan_controls_available(s), "rpm": s["rpm"], "rpmMax": s["rpm_max"],
                "pwm": s["pwm_pct"], "temps": s["temps"], "busy": s["busy"],
                "powerNow": p.get("average") or p.get("current"), "capNow": p.get("cap_current"),
                "capMin": p.get("cap_min"), "capMax": p.get("cap_max"), "capDefault": p.get("cap_default"),
                "zeroRpmSupported": s.get("zero_rpm") is not None,
                "zeroRpmRange": list(zt.get("allowed_range") or []),
                "perfLevel": s.get("perf_level") or "",
                "overdriveMethod": overdrive_plan()[0] if s["is_amd"] else ""}

    # ---- fan ---------------------------------------------------------------------

    fan = Property("QVariantMap", lambda self: {**self._fan, "curve": None}, notify=fanChanged)

    @Property("QVariantList", notify=fanChanged)
    def fanCurve(self):
        # CurveChart wants [{t, rpm}]; "rpm" holds percent here.
        return [{"t": t, "rpm": round(v * 100)} for t, v in sorted(self._fan["curve"].items())]

    fanDirty = Property(bool, lambda self: self._fan_saved is not None and self._fan != self._fan_saved,
                        notify=fanChanged)

    @Slot(str)
    def setFanMode(self, mode):
        self._fan["mode"] = mode
        self.fanChanged.emit()

    @Slot(bool)
    def setZeroRpm(self, on):
        self._fan["zero_rpm"] = on
        self.fanChanged.emit()

    @Slot(int)
    def setZeroRpmTemp(self, t):
        self._fan["zero_rpm_temp"] = t
        self.fanChanged.emit()

    @Slot(int)
    def setFixedSpeed(self, pct):
        self._fan["speed"] = max(0, min(100, pct))
        self.fanChanged.emit()

    @Slot(int, int, int)
    def setCurvePoint(self, i, t, pct):
        pts = sorted(self._fan["curve"].items())
        if not 0 <= i < len(pts):
            return
        lo = pts[i - 1][0] + 1 if i > 0 else 0
        hi = pts[i + 1][0] - 1 if i < len(pts) - 1 else 100
        pts[i] = (max(lo, min(hi, t)), max(0.0, min(1.0, pct / 100)))
        self._fan["curve"] = dict(pts)
        self.fanChanged.emit()

    @Slot()
    def revertFan(self):
        if self._fan_saved:
            self._fan = {**self._fan_saved, "curve": dict(self._fan_saved["curve"])}
            self.fanChanged.emit()

    @Slot()
    def applyFan(self):
        f = self._copy_fan()
        gid = self._s.get("id")
        if not gid:
            return
        pmfw = {}
        if f["zero_rpm"] is not None:
            pmfw["zero_rpm"] = bool(f["zero_rpm"])
        if f["zero_rpm_temp"] is not None and f["zero_rpm"]:
            pmfw["zero_rpm_threshold"] = int(f["zero_rpm_temp"])

        def work():
            if f["mode"] == "auto":
                return self._lact.apply(self._lact.set_fan, gid, False, pmfw=pmfw)
            if f["mode"] == "static":
                return self._lact.apply(self._lact.set_fan, gid, True, mode="static",
                                        static_speed=f["speed"] / 100, pmfw=pmfw)
            return self._lact.apply(self._lact.set_fan, gid, True, mode="curve", curve=f["curve"], pmfw=pmfw)

        def done(_):
            self._fan_saved = f
            self.fanChanged.emit()
            self.toast.emit("Fan settings applied — LACT keeps them across reboots")
            self.refresh()
        run_async(work, done, lambda e: self.toast.emit(f"Could not apply fan settings: {e}"))

    # ---- power limit (needs confirmation, like LACT) -----------------------------------

    powerCap = Property(float, lambda self: self._cap or 0.0, notify=powerChanged)
    confirmSeconds = Property(int, lambda self: self._confirm_left, notify=confirmChanged)

    @Slot(float)
    def setPowerCap(self, watts):
        self._cap = watts
        self.powerChanged.emit()

    @Slot()
    def applyPower(self):
        self._send_power(self._cap)

    @Slot()
    def resetPower(self):
        self._send_power(None)

    def _send_power(self, cap):
        gid = self._s.get("id")
        if not gid:
            return

        def done(timer):
            self._confirm_left = int(timer or 5)
            self._confirm_timer.start()
            self.confirmChanged.emit()
            self.refresh()
        run_async(lambda: self._lact.set_power_cap(gid, cap), done,
                  lambda e: self.toast.emit(f"Could not set the power limit: {e}"))

    def _tick_confirm(self):
        self._confirm_left -= 1
        if self._confirm_left <= 0:
            self._confirm_timer.stop()
            self.toast.emit("Power limit reverted (not confirmed in time)")
            self._cap = None
            QTimer.singleShot(800, self._reload_power)
        self.confirmChanged.emit()

    def _reload_power(self):
        def got(s):
            self._got(s)
            self._cap = s["power"].get("cap_current")
            self.powerChanged.emit()
        run_async(lambda: read_state(self._lact), got)

    @Slot(bool)
    def confirmPower(self, keep):
        self._confirm_timer.stop()
        self._confirm_left = 0
        self.confirmChanged.emit()
        run_async(lambda: self._lact.confirm(keep),
                  lambda _: (self.toast.emit("Power limit kept" if keep else "Power limit reverted"),
                             QTimer.singleShot(800, self._reload_power)),
                  lambda e: self.toast.emit(f"Could not confirm: {e}"))

    # ---- setup actions -------------------------------------------------------------

    @Slot()
    def enableControls(self):
        def log(line):
            pass

        def done(_):
            self._reboot_needed = True
            self.stateChanged.emit()
            self.toast.emit("GPU controls enabled — restart your PC to finish")
        run_async(lambda: enable_overdrive(log), done, lambda e: self.toast.emit(str(e)))

    @Slot()
    def startLact(self):
        def work():
            runner = ["pkexec"] if shutil.which("pkexec") else ["sudo", "-n"]
            r = subprocess.run(runner + ["systemctl", "enable", "--now", "lactd.service"],
                               capture_output=True, text=True)
            return r.returncode == 0
        run_async(work, lambda ok: (self.toast.emit("LACT started" if ok else "Could not start LACT"),
                                    QTimer.singleShot(1500, self.refresh)))
