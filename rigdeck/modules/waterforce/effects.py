"""LED effects. The cooler only has Static and Rainbow Wave in hardware; the rest are
generated on the PC by streaming colours (exactly what GIGABYTE Control Center does)."""
from __future__ import annotations

import colorsys
import math

from ...config import parse_color
from .device import Cooler

HARDWARE = ("static", "rainbow-wave", "off")
SOFTWARE = ("pulse", "flash", "dflash", "cycle")
ALL = ("static", "pulse", "flash", "dflash", "cycle", "rainbow-wave", "off")
LABELS = {"static": "Static", "pulse": "Pulse", "flash": "Flash", "dflash": "Double flash",
          "cycle": "Color cycle", "rainbow-wave": "Rainbow wave", "off": "Off"}
USES_COLOR = ("static", "pulse", "flash", "dflash")

DEFAULTS = {"effect": "rainbow-wave", "color": "ffffff", "brightness": 100}


def settings(led: dict) -> tuple[str, tuple[int, int, int], int]:
    effect = led.get("effect", DEFAULTS["effect"])
    if effect not in ALL:
        effect = DEFAULTS["effect"]
    try:
        rgb = parse_color(str(led.get("color", DEFAULTS["color"])))
    except ValueError:
        rgb = (255, 255, 255)
    bright = max(0, min(100, int(led.get("brightness", DEFAULTS["brightness"]))))
    return effect, rgb, bright


def apply_hardware(cooler: Cooler, led: dict):
    """Put the cooler in the right base state for the configured effect."""
    effect, rgb, bright = settings(led)
    if effect == "rainbow-wave":
        cooler.led_rainbow_wave()
    elif effect == "static":
        cooler.led_static(*rgb, brightness=bright)
    else:  # off, or a software effect about to stream colours
        cooler.led_off()


def frame(effect: str, rgb: tuple[int, int, int], bright: int, t: float) -> tuple[int, int, int]:
    """Colour of a software effect at time t (seconds)."""
    if effect == "cycle":
        cr, cg, cb = colorsys.hsv_to_rgb((t / 6.0) % 1.0, 1.0, 1.0)
        rgb, k = (cr * 255, cg * 255, cb * 255), 1.0
    elif effect == "pulse":  # 2 s breathe
        k = (1 - math.cos(2 * math.pi * t / 2.0)) / 2
    elif effect == "flash":  # on/off, 0.75 s period
        k = 1.0 if (t % 0.75) < 0.375 else 0.0
    elif effect == "dflash":  # two quick flashes per 1.2 s
        p = t % 1.2
        k = 1.0 if p < 0.12 or 0.24 <= p < 0.36 else 0.0
    else:
        k = 1.0
    k *= bright / 100
    return tuple(round(c * k) for c in rgb)
