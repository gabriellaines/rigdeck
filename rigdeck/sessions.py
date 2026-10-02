"""Game monitor: record CPU, memory, GPU and disk telemetry once a second while you play.

The recorder is its own process (`rigdeck session start`), so it keeps going when the RigDeck
window is minimised or closed. It appends one JSON line per sample to
~/.local/share/rigdeck/sessions/<id>.jsonl and, when stopped (SIGTERM / SIGINT), writes
<id>.json with the summary. `recording.json` in the same folder says what's running.
"""
from __future__ import annotations

import glob
import json
import os
import signal
import subprocess
import sys
import time

from . import hwinfo, resources
from .sensors import CpuSensors

DIR = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "rigdeck", "sessions")
STATE = os.path.join(DIR, "recording.json")
INTERVAL = 1.0

# Processes that are never "the game"
NOT_GAMES = {"rigdeck", "rigdeck-gui", "python3", "python", "kwin_wayland", "kwin_x11", "plasmashell", "Xwayland",
             "Xorg", "gnome-shell", "mutter", "steam", "steamwebhelper", "gameoverlayui", "pipewire",
             "pipewire-pulse", "wireplumber", "pulseaudio", "systemd", "dbus-daemon", "krunner", "baloo_file",
             "kworker", "irq", "ksoftirqd", "rcu_preempt", "lactd", "tshark", "dumpcap", "reaper", "pressure-vessel",
             "srt-bwrap", "wineserver", "services.exe", "explorer.exe", "winedevice.exe", "plugplay.exe",
             "fossilize_replay", "fossilize_repla", "steamservice.exe", "steam.exe"}   # Steam shader compiling
METRICS = {   # key: (label, unit) — shown in this order
    "cpu": ("CPU load", "%"), "cpuMax": ("Busiest thread", "%"), "cpuTemp": ("CPU temperature", "°C"),
    "cpuMhz": ("CPU clock", "MHz"), "mem": ("Memory used", "GiB"), "swap": ("Swap used", "GiB"),
    "gpu": ("GPU load", "%"), "gpuTemp": ("GPU temperature", "°C"), "gpuHotspot": ("GPU hotspot", "°C"),
    "gpuMemTemp": ("GPU memory temperature", "°C"), "gpuMhz": ("GPU clock", "MHz"), "gpuPower": ("GPU power", "W"),
    "vram": ("VRAM used", "GiB"), "gpuFan": ("GPU fan", "RPM"),
}


# ---- what's running -------------------------------------------------------------------

class ProcessWatch:
    """The process using the most CPU since the previous call (cheap: one /proc/*/stat read each)."""

    def __init__(self):
        self.last: dict[int, int] = {}
        self.names: dict[int, str] = {}

    def _name(self, pid: int, comm: str) -> str:
        """Full program name: comm is cut at 15 characters; Windows games show as their .exe."""
        if pid not in self.names:
            try:
                arg0 = open(f"/proc/{pid}/cmdline", "rb").read().split(b"\0")[0].decode(errors="replace")
                base = arg0.replace("\\", "/").rsplit("/", 1)[-1]
                self.names[pid] = base if base.startswith(comm[:8]) or base.lower().endswith(".exe") else comm
            except OSError:
                self.names[pid] = comm
        return self.names[pid]

    def top(self) -> str | None:
        now, best, best_name = {}, 0, None
        for stat in glob.glob("/proc/[0-9]*/stat"):
            try:
                with open(stat) as f:
                    s = f.read()
            except OSError:
                continue
            l, r = s.find("("), s.rfind(")")
            name, fields = s[l + 1:r], s[r + 2:].split()
            pid = int(stat.split("/")[2])
            ticks = int(fields[11]) + int(fields[12])        # utime + stime
            now[pid] = ticks
            delta = ticks - self.last.get(pid, ticks)
            if delta > best and name not in NOT_GAMES and not name.startswith(("kworker", "irq/")):
                full = self._name(pid, name)
                if full not in NOT_GAMES:
                    best, best_name = delta, full
        self.last = now
        self.names = {p: n for p, n in self.names.items() if p in now}
        return best_name


# ---- sampling -------------------------------------------------------------------------

def _gib(b) -> float | None:
    return round(b / 2 ** 30, 2) if b is not None else None


def _disk_temps() -> dict[str, float]:
    out = {}
    for name in os.listdir("/sys/block"):
        hw = hwinfo._hwmon(f"/sys/block/{name}/device")     # the same lookup the Storage page uses
        if hw:
            try:
                out[name] = int(open(os.path.join(hw, "temp1_input")).read()) / 1000
            except (OSError, ValueError):
                pass
    return out


class Recorder:
    def __init__(self):
        self.usage = resources.Sampler()
        self.sensors = CpuSensors()
        self.procs = ProcessWatch()
        self.cards = hwinfo.gpu_cards()
        self.t0 = time.monotonic()

    def sample(self) -> dict:
        u = self.usage.sample()
        g = hwinfo.gpu_telemetry(self.cards[0]) if self.cards else {}
        m = u["memory"]
        mhz = u["cpu"]["mhz"]
        temps = _disk_temps()
        s = {"t": round(time.monotonic() - self.t0, 2),
             "cpu": u["cpu"]["total"], "cpuMax": max(u["cpu"]["cores"] or [0]),
             "cpuTemp": self.sensors.temperature(), "cpuMhz": round(sum(mhz) / len(mhz)) if mhz else None,
             "mem": _gib(m.get("used")), "swap": _gib(m.get("swap_used")),
             "gpu": g.get("busy"), "gpuTemp": g.get("temp_edge"), "gpuHotspot": g.get("temp_junction"),
             "gpuMemTemp": g.get("temp_mem"), "gpuMhz": g.get("sclk_mhz"), "gpuPower": g.get("power_w"),
             "vram": _gib(g.get("vram_used")), "gpuFan": g.get("fan_rpm"),
             "disks": {d["name"]: {"r": round(d["read"]), "w": round(d["write"]), "temp": temps.get(d["name"])}
                       for d in u["disks"]},
             "top": self.procs.top()}
        return s


# ---- summaries ------------------------------------------------------------------------

def _stats(values: list) -> dict | None:
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    p = lambda q: v[min(len(v) - 1, int(round(q * (len(v) - 1))))]
    return {"avg": round(sum(v) / len(v), 2), "min": v[0], "max": v[-1], "p95": p(0.95), "p5": p(0.05)}


def summarize(samples: list[dict]) -> dict:
    out = {"duration": samples[-1]["t"] if samples else 0, "samples": len(samples), "metrics": {}, "disks": {}}
    for key in METRICS:
        st = _stats([s.get(key) for s in samples])
        if st:
            out["metrics"][key] = st
    disks = sorted({d for s in samples for d in s.get("disks", {})})
    for d in disks:
        rows = [s["disks"][d] for s in samples if d in s.get("disks", {})]
        out["disks"][d] = {"read": sum(r["r"] for r in rows) * INTERVAL, "written": sum(r["w"] for r in rows) * INTERVAL,
                           "temp": _stats([r.get("temp") for r in rows])}
    tops: dict[str, int] = {}
    for s in samples:
        if s.get("top"):
            tops[s["top"]] = tops.get(s["top"], 0) + 1
    out["game"] = max(tops, key=tops.get) if tops else None
    return out


# ---- files ----------------------------------------------------------------------------

def _path(sid: str, ext: str) -> str:
    return os.path.join(DIR, f"{sid}.{ext}")


def load_samples(sid: str) -> list[dict]:
    out = []
    try:
        with open(_path(sid, "jsonl")) as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass   # a line cut short by a crash
    except OSError:
        pass
    return out


def recording() -> dict | None:
    """{'id', 'pid', 'started'} if a recorder is running."""
    try:
        st = json.load(open(STATE))
        os.kill(st["pid"], 0)
        return st
    except (OSError, ValueError, KeyError):
        return None


def list_sessions() -> list[dict]:
    out = []
    live = recording() or {}
    for p in sorted(glob.glob(os.path.join(DIR, "*.jsonl")), reverse=True):
        sid = os.path.basename(p)[:-6]
        meta = {}
        try:
            meta = json.load(open(_path(sid, "json")))
        except (OSError, ValueError):
            if live.get("id") == sid:            # being recorded: label and start from the recorder
                out.append({"id": sid, "started": live.get("started", sid), "name": live.get("name") or "",
                            "game": None, "duration": None, "finished": False})
                continue
        out.append({"id": sid, "started": meta.get("started", sid), "name": meta.get("name") or "",
                    "game": (meta.get("summary") or {}).get("game"),
                    "duration": (meta.get("summary") or {}).get("duration"), "finished": bool(meta)})
    return out


def details(sid: str) -> dict:
    samples = load_samples(sid)
    meta = {}
    try:
        meta = json.load(open(_path(sid, "json")))
    except (OSError, ValueError):
        pass
    summary = meta.get("summary") or summarize(samples)
    started = meta.get("started") or (recording() or {}).get("started", "")
    frames = frames_for(sid, started, summary.get("duration", 0)) if started else None
    if frames and frames.get("game"):
        summary = {**summary, "game": frames["game"]}     # the app MangoHud logged beats the busiest process
    return {"id": sid, "meta": meta, "summary": summary, "samples": samples, "frames": frames}


def delete(sid: str):
    for ext in ("jsonl", "json"):
        try:
            os.remove(_path(sid, ext))
        except FileNotFoundError:
            pass


def export_csv(sid: str, path: str) -> str:
    samples = load_samples(sid)
    disks = sorted({d for s in samples for d in s.get("disks", {})})
    cols = ["t"] + list(METRICS) + [f"{d}_{k}" for d in disks for k in ("read_Bps", "write_Bps", "temp")] + ["top_process"]
    with open(path, "w") as f:
        f.write(",".join(cols) + "\n")
        for s in samples:
            row = [s.get("t")] + [s.get(k) for k in METRICS]
            for d in disks:
                dd = s.get("disks", {}).get(d, {})
                row += [dd.get("r"), dd.get("w"), dd.get("temp")]
            row.append(s.get("top") or "")
            f.write(",".join("" if v is None else str(v) for v in row) + "\n")
    return path


# ---- the recorder process -------------------------------------------------------------

def run(name: str = "") -> str:
    """Record until SIGTERM / SIGINT. Returns the session id."""
    os.makedirs(DIR, exist_ok=True)
    if recording():
        raise RuntimeError("a session is already being recorded")
    sid = time.strftime("%Y%m%d-%H%M%S")
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    json.dump({"id": sid, "pid": os.getpid(), "started": started, "name": name}, open(STATE, "w"))
    stop = {"now": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.update(now=True))
    signal.signal(signal.SIGINT, lambda *_: stop.update(now=True))
    rec = Recorder()
    samples = []
    next_t = time.monotonic() + INTERVAL
    try:
        with open(_path(sid, "jsonl"), "a") as out:
            while not stop["now"]:
                time.sleep(max(0.0, next_t - time.monotonic()))
                next_t += INTERVAL
                s = rec.sample()
                samples.append(s)
                out.write(json.dumps(s, separators=(",", ":")) + "\n")
                out.flush()
    finally:
        json.dump({"id": sid, "started": started, "ended": time.strftime("%Y-%m-%d %H:%M:%S"), "name": name,
                   "interval": INTERVAL, "summary": summarize(samples)}, open(_path(sid, "json"), "w"))
        try:
            os.remove(STATE)
        except FileNotFoundError:
            pass
    return sid


def start_background(name: str = "") -> None:
    """Start a recorder process that outlives the caller (the GUI)."""
    if recording():
        return
    cmd = [sys.executable, "-m", "rigdeck", "session", "record"] + (["--name", name] if name else [])
    subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    for _ in range(30):                       # wait until it has registered itself
        if recording():
            return
        time.sleep(0.1)


def stop() -> str | None:
    st = recording()
    if not st:
        return None
    os.kill(st["pid"], signal.SIGTERM)
    for _ in range(50):
        if not recording():
            break
        time.sleep(0.1)
    return st["id"]


# ---- frames, from MangoHud logs -------------------------------------------------------

FRAMES_DIR = os.path.join(os.path.dirname(DIR), "frametimes")
MANGOHUD_CONF = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                             "MangoHud", "MangoHud.conf")
MANGOHUD_LINES = [f"output_folder={FRAMES_DIR}", "autostart_log=1", "log_interval=0"]
MARKER = "# Added by RigDeck (Game monitor): log every frame so sessions get FPS and frametimes."


def mangohud_state() -> str:
    """'missing' (not installed), 'ready' (logs where RigDeck reads them), 'setup' (no config yet),
    'conflict' (a config exists that RigDeck didn't write)."""
    import shutil
    if not shutil.which("mangohud"):
        return "missing"
    try:
        text = open(MANGOHUD_CONF).read()
    except FileNotFoundError:
        return "setup"
    return "ready" if all(line in text for line in MANGOHUD_LINES) else "conflict"


def setup_mangohud() -> str:
    """Create a MangoHud config that logs every frame for RigDeck. Never overwrites an existing one."""
    if os.path.exists(MANGOHUD_CONF):
        raise RuntimeError(f"{MANGOHUD_CONF} already exists — add these lines to it: " + ", ".join(MANGOHUD_LINES))
    os.makedirs(os.path.dirname(MANGOHUD_CONF), exist_ok=True)
    os.makedirs(FRAMES_DIR, exist_ok=True)
    with open(MANGOHUD_CONF, "w") as f:
        f.write(MARKER + "\n" + "\n".join(MANGOHUD_LINES) + "\n# Hide the overlay while still logging; Right Shift+F12 shows it.\nno_display\n")
    return MANGOHUD_CONF


def parse_mangohud(path: str) -> tuple[float, list[tuple[float, float]]]:
    """(log start as a Unix time, [(seconds since start, frametime ms)]) from one MangoHud CSV."""
    stamp = os.path.basename(path)[:-4].rsplit("_", 2)
    start = time.mktime(time.strptime(f"{stamp[-2]}_{stamp[-1]}", "%Y-%m-%d_%H-%M-%S"))
    frames, cols = [], None
    with open(path) as f:
        for line in f:
            p = line.strip().split(",")
            if cols is None:
                if p and p[0] == "fps":
                    cols = {name: i for i, name in enumerate(p)}
                continue
            try:
                frames.append((int(p[cols["elapsed"]]) / 1e9, float(p[cols["frametime"]])))
            except (ValueError, IndexError, KeyError):
                continue
    return start, frames


def frame_stats(frametimes: list[float]) -> dict | None:
    """CapFrameX-style figures: average FPS, 1% / 0.1% lows (from the 99th / 99.9th percentile
    frametime), frametime percentiles."""
    ft = sorted(t for t in frametimes if t > 0)
    if len(ft) < 10:
        return None
    pct = lambda q: ft[min(len(ft) - 1, int(q * (len(ft) - 1)))]
    return {"frames": len(ft), "avgFps": round(1000 * len(ft) / sum(ft), 1),
            "low1": round(1000 / pct(0.99), 1), "low01": round(1000 / pct(0.999), 1),
            "ftAvg": round(sum(ft) / len(ft), 2), "ftP99": round(pct(0.99), 2), "ftMax": round(ft[-1], 2)}


def frames_for(sid: str, started: str, duration: float) -> dict | None:
    """MangoHud frames recorded during a session: stats, the game, and fps per second for graphs."""
    try:
        t0 = time.mktime(time.strptime(started, "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return None
    t1 = t0 + max(duration, 1)
    frames, game = [], None
    for path in sorted(glob.glob(os.path.join(FRAMES_DIR, "*.csv"))):
        if path.endswith("_summary.csv"):
            continue
        try:
            start, rows = parse_mangohud(path)
        except (OSError, ValueError, IndexError):
            continue
        hits = [(start + e - t0, ft) for e, ft in rows if t0 <= start + e <= t1]
        if hits:
            frames += hits
            game = game or os.path.basename(path).rsplit("_", 2)[0]
    if not frames:
        return None
    stats = frame_stats([ft for _, ft in frames])
    per_sec: dict[int, list[float]] = {}
    for t, ft in frames:
        per_sec.setdefault(int(t), []).append(ft)
    fps = [round(1000 * len(v) / sum(v), 1) if sum(v) else 0 for _, v in sorted(per_sec.items())]
    step = max(1, len(frames) // 2000)                     # frametime graph: at most ~2000 points
    return {**(stats or {}), "game": game, "fps": fps, "frametimes": [round(ft, 2) for _, ft in frames[::step]]}
