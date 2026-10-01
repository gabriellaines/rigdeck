"""GIGABYTE AORUS WATERFORCE X II AIO cooler."""
from __future__ import annotations

import logging
import time

from ... import config, servicectl
from ...sensors import CpuSensors, core_counts, cpu_name, is_amd
from ..base import Module, ServiceTask
from . import effects, media
from .device import (FAN_MODES, PUMP_MODES, Cooler, CoolerError, SpeedMode, SpeedType,
                     find_hidraw)

log = logging.getLogger("rigdeck.cooler")

SENSOR_INTERVAL = 1.5
EFFECT_INTERVAL = 1 / 30
MODE_NAMES = {m.name.lower().replace("_", "-"): m for m in SpeedMode}


def mode_name(m: SpeedMode) -> str:
    return m.name.lower().replace("_", "-")


class CoolerTask(ServiceTask):
    """Feeds CPU data to the cooler (its curves depend on it) and runs software LED effects."""

    def __init__(self):
        self.cooler: Cooler | None = None
        self.sensors = CpuSensors()
        self.cores, self.threads = core_counts()
        self.cpu, self.amd = cpu_name(), is_amd()
        self.led: dict = {}
        self.next_sensor = 0.0
        self.next_retry = 0.0
        self.t0: float | None = None

    def _connect(self, now: float) -> bool:
        if self.cooler:
            return True
        if now < self.next_retry:
            return False
        try:
            self.cooler = Cooler()
            log.info("connected to %s (%s)", self.cooler.model(), self.cooler.path)
            self.cooler.send_cpu_name(self.cpu)
            effects.apply_hardware(self.cooler, self.led)
            return True
        except CoolerError as e:
            self.next_retry = now + 5
            log.debug("cooler not available: %s", e)
            self._drop()
            return False

    def _drop(self):
        if self.cooler:
            try:
                self.cooler.close()
            except OSError:
                pass
        self.cooler = None

    def reload(self, cfg: dict):
        self.led = config.section(cfg, "cooler", "led")
        if self.cooler:
            try:
                effects.apply_hardware(self.cooler, self.led)
            except CoolerError:
                self._drop()

    def tick(self, now: float) -> float:
        if self.t0 is None:
            self.t0 = now
        if not self._connect(now):
            return max(0.5, self.next_retry - now)
        try:
            if now >= self.next_sensor:
                self.next_sensor = now + SENSOR_INTERVAL
                self.cooler.send_sensors(cpu_temp=self.sensors.temperature(), cpu_load=self.sensors.load(),
                                         ghz_tenths=self.sensors.freq_mhz() // 100,
                                         threads=self.threads, cores=self.cores, amd=self.amd)
            effect, rgb, bright = effects.settings(self.led)
            if effect in effects.SOFTWARE:
                self.cooler.led_color(*effects.frame(effect, rgb, bright, now - self.t0))
                return EFFECT_INTERVAL
            return max(0.05, self.next_sensor - now)
        except CoolerError as e:
            log.warning("lost cooler: %s", e)
            self._drop()
            self.next_retry = now + 3
            return 3.0

    def close(self):
        self._drop()


def set_led(effect: str, color: str | None = None, brightness: int | None = None) -> str:
    """Save LED settings and apply them. Returns a human message. Shared by CLI and GUI."""
    cfg = config.load()
    led = config.section(cfg, "cooler", "led")
    led["effect"] = effect
    if color:
        config.parse_color(color)
        led["color"] = color.lstrip("#").lower()
    if brightness is not None:
        led["brightness"] = max(0, min(100, int(brightness)))
    config.save(cfg)
    if servicectl.reload():
        return "applied"
    if effect in effects.SOFTWARE:
        return "saved — this effect needs the rigdeck service running"
    with Cooler() as c:
        effects.apply_hardware(c, led)
    return "applied (service not running)"


class Screen:
    """The cooler's stored animations: play order, which ones are on, seconds each."""

    def __init__(self, files: list[str], playing: list[str], interval: int, ids: dict[str, int]):
        self.files, self.playing, self.interval, self.ids = files, playing, interval, ids

    @classmethod
    def read(cls, c: Cooler) -> "Screen":
        files, ids = c.file_ids()
        positions, interval = c.carousel()
        playing = [files[p] for p in positions if p < len(files)]
        return cls(files, playing, interval or 5, ids)

    def write(self, c: Cooler, files: list[str], playing: list[str], interval: int | None = None):
        """files: all stored names in the desired order; playing: names to show."""
        if sorted(files) != sorted(self.ids):
            raise ValueError("file list is out of date; reload")
        c.set_carousel([self.ids[n] for n in files], [files.index(n) for n in playing],
                       interval or self.interval)
        self.files, self.playing = list(files), [n for n in files if n in playing]
        if interval:
            self.interval = interval


def add_to_carousel(c: Cooler, name: str) -> Screen:
    """After an upload: put the new file at the end and switch it on (GCC leaves it off)."""
    time.sleep(1.0)  # let the cooler finish writing before listing
    s = Screen.read(c)
    files = [n for n in s.files if n != name] + [name]
    s.write(c, files, s.playing + [name])
    return s


def delete_media(c: Cooler, name: str, before: Screen | None = None) -> Screen:
    """Delete a file, keeping the order and selection of the others (IDs shift after a delete).

    Pass the Screen you already have to save one read of the cooler."""
    before = before or Screen.read(c)
    if name not in before.files:
        raise ValueError(f"no file named {name!r} on the cooler")
    c.delete_media(name)
    time.sleep(1.0)
    after = Screen.read(c)
    if after.files:
        files = [n for n in before.files if n in after.ids]
        files += [n for n in after.files if n not in files]
        playing = [n for n in before.playing if n in after.ids] or files[:1]
        after.write(c, files, playing, before.interval)
    return after


# ---- CLI -----------------------------------------------------------------

def _curve(points: list[str]) -> list[tuple[int, int]]:
    try:
        return [(int(t), int(s)) for t, s in (p.split(":") for p in points)]
    except ValueError:
        raise ValueError("curve points look like TEMP:RPM, e.g. 50:1400")


def cli_status(a):
    with Cooler() as c:
        s = c.status()
        print(f"Model     {c.model()}  (firmware {c.firmware()}, {c.path})")
        print(f"Fan       {s.fan_rpm:5d} rpm   {mode_name(s.fan_mode)}")
        print(f"Pump      {s.pump_rpm:5d} rpm   {mode_name(s.pump_mode)}")
        print("Custom    " + ", ".join(f"{t}°C→{r}" for t, r in c.curve(SpeedType.FAN)))
        print(f"Storage   {c.storage_free_kb() / 1024:.2f} MB free")
    st = servicectl.state()
    print(f"Service   {st}" + ("" if st == "active" else "   ⚠ the cooler is NOT getting CPU temperature"))


def cli_mode(a):
    with Cooler() as c:
        fan, pump = c.modes()
        if a.fan:
            fan = MODE_NAMES[a.fan]
        if a.pump:
            pump = MODE_NAMES[a.pump]
        if a.curve:
            fan = SpeedMode.CUSTOMIZED
        curve = _curve(a.curve) if a.curve else (c.curve(SpeedType.FAN) if fan == SpeedMode.CUSTOMIZED else None)
        c.set_modes(fan, pump, curve)
    print(f"fan {mode_name(fan)}, pump {mode_name(pump)} — saved to the cooler")


def cli_led(a):
    print(f"LED {a.effect}: {set_led(a.effect, a.color, a.brightness)}")


def cli_screen(a):
    with Cooler() as c:
        if a.screen_cmd == "list":
            s = Screen.read(c)
            for i, n in enumerate(s.files):
                print(f"{i:3d}  {'▶' if n in s.playing else ' '} {n}")
            kind = "showing one animation" if len(s.playing) == 1 else f"carousel, {s.interval} s each"
            print(f"▶ = on ({kind}).  {c.storage_free_kb() / 1024:.2f} MB free")
        elif a.screen_cmd == "delete":
            delete_media(c, a.name)
            print(f"deleted {a.name}")
        elif a.screen_cmd == "play":
            s = Screen.read(c)
            if len(set(a.index)) != len(a.index) or not all(0 <= i < len(s.files) for i in a.index):
                raise ValueError(f"give distinct file numbers 0-{len(s.files) - 1} (see `screen list`)")
            chosen = [s.files[i] for i in a.index]
            # Chosen files first, in the order given; the rest keep their order after them.
            s.write(c, chosen + [n for n in s.files if n not in chosen], chosen, a.interval)
            print(("showing: " if len(chosen) == 1 else "playing in order: ") + ", ".join(chosen))
        elif a.screen_cmd == "rotate":
            c.set_rotation(a.degrees)
            c.save()
        elif a.screen_cmd == "unit":
            c.set_temp_unit(a.unit == "f")
            c.save()
        elif a.screen_cmd == "upload":
            name = media.target_name(a.file)
            print("converting …")
            data = media.convert(a.file)
            if len(data) > c.storage_free_kb() * 1024:
                raise ValueError("not enough space on the cooler")
            c.upload_media(data, name, lambda d, t: print(f"\ruploading {name}: {100 * d // t:3d}%",
                                                          end="", flush=True))
            print()
            add_to_carousel(c, name)
            print(f"{name} added to the carousel")


class WaterforceModule(Module):
    id = "cooler"
    title = "AIO Cooler"
    icon = "rigdeck-cooler-symbolic"

    def detect(self) -> bool:
        return bool(find_hidraw())

    def add_cli(self, sub):
        p = sub.add_parser("cooler", help="AORUS WATERFORCE X II AIO cooler")
        cs = p.add_subparsers(dest="cooler_cmd", required=True)
        cs.add_parser("status", help="RPM, modes, curve, storage").set_defaults(func=cli_status)

        m = cs.add_parser("mode", help="fan / pump mode (saved on the cooler)")
        m.add_argument("--fan", choices=[mode_name(x) for x in FAN_MODES])
        m.add_argument("--pump", choices=[mode_name(x) for x in PUMP_MODES])
        m.add_argument("--curve", nargs=4, metavar="TEMP:RPM",
                       help="custom fan curve (implies --fan customized), e.g. 30:1000 50:1400 65:1900 80:2500")
        m.set_defaults(func=cli_mode)

        l = cs.add_parser("led", help="lighting effect")
        l.add_argument("effect", choices=effects.ALL)
        l.add_argument("color", nargs="?", help="RRGGBB hex, e.g. ff0000")
        l.add_argument("-b", "--brightness", type=int, metavar="0-100")
        l.set_defaults(func=cli_led)

        s = cs.add_parser("screen", help="LCD screen")
        ss = s.add_subparsers(dest="screen_cmd", required=True)
        ss.add_parser("list", help="files stored on the cooler")
        r = ss.add_parser("rotate")
        r.add_argument("degrees", type=int, choices=[0, 90, 180, 270])
        u = ss.add_parser("unit", help="temperature unit")
        u.add_argument("unit", choices=["c", "f"])
        pl = ss.add_parser("play", help="show one file, or several in a carousel (in the order given)")
        pl.add_argument("index", type=int, nargs="+",
                        help="file numbers from `screen list`, e.g. `play 2` or `play 3 0 2`")
        pl.add_argument("--interval", type=int, metavar="SECONDS", help="time per file")
        de = ss.add_parser("delete", help="delete a stored file (name from `screen list`)")
        de.add_argument("name")
        up = ss.add_parser("upload", help="convert a GIF/video/image, store it and add it to the carousel")
        up.add_argument("file")
        s.set_defaults(func=cli_screen)

    def service_task(self):
        return CoolerTask()

    def gui_page(self, window):
        from .page import CoolerPage
        return CoolerPage(window)

