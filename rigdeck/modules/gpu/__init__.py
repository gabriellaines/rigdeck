"""GPU module: monitoring (sysfs) plus fan / power control through LACT's daemon."""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess

from ..base import Module, RigdeckError
from .lact import Lact, LactError, LactUnavailable, installed, service_state

OVERDRIVE_BIT = 0x4000  # PP_OVERDRIVE_MASK in amdgpu
LIMINE_DEFAULTS = "/etc/default/limine"
DEFAULT_CURVE = {40: 0.30, 50: 0.35, 60: 0.50, 70: 0.75, 80: 1.00}  # LACT's default


# ---- state shared by CLI and GUI -----------------------------------------------

def read_state(lact: Lact | None = None) -> dict:
    """Everything the GPU page shows. Raises LactUnavailable if lactd can't be reached."""
    lact = lact or Lact()
    sysinfo = lact.system_info()
    devices = [d for d in lact.devices() if d.get("device_type", "Dedicated") == "Dedicated"] or lact.devices()
    if not devices:
        raise LactError("lactd found no GPU")
    dev = devices[0]
    gid = dev["id"]
    stats = lact.stats(gid)
    cfg = lact.config(gid)
    fan = stats.get("fan") or {}
    pmfw = fan.get("pmfw_info") or {}
    settings = cfg.get("fan_control_settings") or {}
    curve = settings.get("curve") or fan.get("curve") or DEFAULT_CURVE
    return {
        "id": gid,
        "name": dev.get("name") or gid,
        "lact_version": sysinfo.get("version"),
        "overdrive": sysinfo.get("amdgpu_overdrive_enabled"),
        "is_amd": gid.startswith("1002:"),
        "fan_custom": bool(fan.get("control_enabled")),
        "fan_mode": (fan.get("control_mode") or settings.get("mode") or "curve") if fan.get("control_enabled") else "auto",
        "static_speed": fan.get("static_speed", settings.get("static_speed", 0.5)),
        "curve": {int(k): float(v) for k, v in curve.items()},
        "rpm": fan.get("speed_current"),
        "rpm_max": fan.get("speed_max"),
        "pwm_pct": round(100 * fan["pwm_current"] / (fan.get("pwm_max") or 255)) if fan.get("pwm_current") is not None else None,
        "zero_rpm": pmfw.get("zero_rpm_enable"),
        "zero_rpm_temp": pmfw.get("zero_rpm_temperature"),
        "min_pwm": pmfw.get("minimum_pwm"),
        "target_temp": pmfw.get("target_temp"),
        "power": stats.get("power") or {},
        "temps": {k: (v.get("current") if isinstance(v, dict) else v) for k, v in (stats.get("temps") or {}).items()},
        "busy": stats.get("busy_percent"),
        "perf_level": stats.get("performance_level"),
        "pmfw_config": cfg.get("pmfw_options") or {},
    }


def fan_controls_available(state: dict) -> bool:
    return bool(state.get("overdrive")) or not state.get("is_amd")


# ---- enabling AMD overdrive (needed for fan control on RDNA3/4) -----------------------

def overdrive_plan() -> tuple[str, str]:
    """(method, root shell script). Limine systems get a kernel argument, because LACT's
    initramfs route (`mkinitcpio -P`) is a no-op there; everything else uses LACT's own."""
    try:
        current = int(open("/sys/module/amdgpu/parameters/ppfeaturemask").read().strip(), 0)
    except (OSError, ValueError):
        current = 0xFFF7BFFF
    mask = f"0x{(current | OVERDRIVE_BIT) & 0xFFFFFFFF:x}"
    arg = f"amdgpu.ppfeaturemask={mask}"
    if os.path.exists(LIMINE_DEFAULTS) and shutil.which("limine-update"):
        f = shlex.quote(LIMINE_DEFAULTS)
        script = (
            f"set -e; grep -q 'amdgpu.ppfeaturemask' {f} && "
            f"sed -i 's/amdgpu\\.ppfeaturemask=[^ \"]*/{arg}/' {f} || "
            f"sed -i '0,/^KERNEL_CMDLINE\\[default\\]+=\"/s/^\\(KERNEL_CMDLINE\\[default\\]+=\".*\\)\"$/\\1 {arg}\"/' {f}; "
            f"grep -q '{arg}' {f}; limine-update"
        )
        return "limine", script
    return "lact", ""


def enable_overdrive(log=print) -> str:
    """Turn overdrive on for the next boot. Asks for the admin password (pkexec/sudo)."""
    method, script = overdrive_plan()
    if method == "lact":
        msg = Lact().enable_overdrive()
        log(msg or "LACT enabled overdrive")
        return "reboot"
    runner = ["pkexec"] if not os.isatty(0) and shutil.which("pkexec") else ["sudo"]
    r = subprocess.run(runner + ["sh", "-c", script], capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        log(line)
    if r.returncode != 0:
        raise RigdeckError("could not enable overdrive (cancelled, or the boot config is unusual)")
    return "reboot"


# ---- CLI ------------------------------------------------------------------------------

def _pct(x):
    return "—" if x is None else f"{round(x * 100)}%"


def cli_status(a):
    s = read_state()
    t = s["temps"]
    print(f"GPU       {s['name']}  (LACT {s['lact_version']})")
    print(f"Temps     edge {t.get('edge')} °C, hotspot {t.get('junction')} °C, memory {t.get('mem')} °C")
    print(f"Fan       {s['rpm']} rpm ({s['pwm_pct']}%)  mode: {s['fan_mode']}")
    if s["zero_rpm"] is not None:
        zt = s["zero_rpm_temp"] or {}
        print(f"Zero RPM  {'on' if s['zero_rpm'] else 'off'}" + (f" (fans stop below {zt.get('current')} °C)" if zt else ""))
    p = s["power"]
    print(f"Power     {p.get('average')} W, limit {p.get('cap_current')} W (range {p.get('cap_min')}–{p.get('cap_max')}, default {p.get('cap_default')})")
    if s["fan_mode"] == "curve" and s["fan_custom"]:
        print("Curve     " + ", ".join(f"{k}°C→{_pct(v)}" for k, v in sorted(s["curve"].items())))
    if not fan_controls_available(s):
        print("Note      fan control needs AMD overdrive: run `rigdeck gpu enable-controls`, then reboot")


def cli_fan(a):
    lact = Lact()
    s = read_state(lact)
    if not fan_controls_available(s):
        raise RigdeckError("fan control needs AMD overdrive: run `rigdeck gpu enable-controls`, then reboot")
    pmfw = {}
    if a.zero_rpm is not None:
        pmfw["zero_rpm"] = a.zero_rpm == "on"
    if a.zero_rpm_temp is not None:
        pmfw["zero_rpm_threshold"] = a.zero_rpm_temp
    if a.mode == "auto":
        lact.apply(lact.set_fan, s["id"], False, pmfw=pmfw)
    elif a.mode == "fixed":
        if a.speed is None:
            raise ValueError("fixed mode needs --speed PERCENT")
        lact.apply(lact.set_fan, s["id"], True, mode="static", static_speed=a.speed / 100, pmfw=pmfw)
    else:
        curve = s["curve"]
        if a.curve:
            try:
                curve = {int(t): int(p) / 100 for t, p in (x.split(":") for x in a.curve)}
            except ValueError:
                raise ValueError("curve points look like TEMP:PERCENT, e.g. 60:45")
        lact.apply(lact.set_fan, s["id"], True, mode="curve", curve=curve, pmfw=pmfw)
    print("fan settings applied (LACT keeps them across reboots)")


def cli_power(a):
    lact = Lact()
    s = read_state(lact)
    p = s["power"]
    if a.watts == "default":
        cap = None
    else:
        cap = float(a.watts)
        lo, hi = p.get("cap_min"), p.get("cap_max")
        if lo is not None and hi is not None and not lo <= cap <= hi:
            raise ValueError(f"power limit must be between {lo:g} and {hi:g} W")
    lact.apply(lact.set_power_cap, s["id"], cap)
    print(f"power limit: {'default' if cap is None else f'{cap:g} W'}")


def cli_enable(a):
    method, _ = overdrive_plan()
    print(f"Enabling AMD overdrive via {'the Limine kernel command line' if method == 'limine' else 'LACT'}…")
    enable_overdrive()
    print("Done. Reboot to unlock GPU fan control.")


class GpuModule(Module):
    id = "gpu"
    title = "Graphics"
    icon = "monitor"
    kind = "system"
    order = 20

    def detect(self) -> bool:
        return True

    def add_cli(self, sub):
        p = sub.add_parser("gpu", help="graphics card: fans, zero-RPM, power limit (via LACT)")
        gs = p.add_subparsers(dest="gpu_cmd", required=True)
        gs.add_parser("status", help="temperatures, fan, power and current settings").set_defaults(func=cli_status)
        f = gs.add_parser("fan", help="fan mode, curve and zero-RPM")
        f.add_argument("mode", choices=["auto", "curve", "fixed"])
        f.add_argument("--speed", type=int, metavar="PERCENT", help="for fixed mode")
        f.add_argument("--curve", nargs="+", metavar="TEMP:PERCENT", help="e.g. 40:30 60:50 80:100")
        f.add_argument("--zero-rpm", choices=["on", "off"], help="let fans stop when the GPU is cool")
        f.add_argument("--zero-rpm-temp", type=int, metavar="°C", help="fans stop below this temperature")
        f.set_defaults(func=cli_fan)
        pw = gs.add_parser("power", help="power limit in watts, or 'default'")
        pw.add_argument("watts")
        pw.set_defaults(func=cli_power)
        gs.add_parser("enable-controls", help="enable AMD overdrive (needed for fan control); reboot after")\
            .set_defaults(func=cli_enable)

    def qml_page(self):
        return os.path.join(os.path.dirname(__file__), "qml", "GpuPage.qml")

    def qt_backend(self, app):
        from .qt import GpuBackend
        return GpuBackend()


__all__ = ["GpuModule", "read_state", "enable_overdrive", "overdrive_plan", "LactError", "LactUnavailable",
           "installed", "service_state"]
