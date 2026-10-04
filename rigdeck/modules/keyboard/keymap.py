"""Key ids used by the PRO X TKL RAPID's analog settings (0x1b08 files and live depth stream).

Mapped 2026-10-02 by pressing each key with the live stream on and matching the HID usage of the
same press (ANSI layout). 0x47 never sends a HID usage: it sits between Right Alt and Menu, so it's Fn.
The keyboard's actuation table also lists 0x57–0x5c, 0x64–0x6a, 0x6e, 0x6f: keys of other layouts.
"""

KEYS = {
    0x00: "Esc", 0x01: "F1", 0x02: "F2", 0x03: "F3", 0x04: "F4", 0x05: "F5", 0x06: "F6", 0x07: "F7",
    0x08: "F8", 0x09: "F9", 0x0a: "F10", 0x0b: "F11", 0x0c: "F12", 0x0d: "`", 0x0e: "1", 0x0f: "2",
    0x10: "3", 0x11: "4", 0x12: "5", 0x13: "6", 0x14: "7", 0x15: "8", 0x16: "9", 0x17: "0",
    0x18: "-", 0x19: "=", 0x1a: "Backspace", 0x1b: "Tab", 0x1c: "Q", 0x1d: "W", 0x1e: "E", 0x1f: "R",
    0x20: "F", 0x21: "D", 0x22: "S", 0x23: "A", 0x24: "CapsLock", 0x25: "LShift", 0x26: "Z", 0x27: "X",
    0x28: "C", 0x29: "T", 0x2a: "Y", 0x2b: "U", 0x2c: "I", 0x2d: "O", 0x2e: "L", 0x2f: "K",
    0x30: "J", 0x31: "H", 0x32: "G", 0x33: "V", 0x34: "B", 0x35: "N", 0x36: "M", 0x37: ",",
    0x38: "P", 0x39: "[", 0x3a: "]", 0x3b: "\\", 0x3c: "Enter", 0x3d: "'", 0x3e: ";", 0x3f: ".",
    0x40: "/", 0x41: "RShift", 0x42: "LCtrl", 0x43: "LSuper", 0x44: "LAlt", 0x45: "Space", 0x46: "RAlt", 0x47: "Fn",
    0x48: "Menu", 0x49: "RCtrl", 0x4a: "PrtSc", 0x4b: "ScrollLock", 0x4c: "Pause", 0x4d: "PgUp", 0x4e: "Home", 0x4f: "Insert",
    0x50: "Delete", 0x51: "End", 0x52: "PgDn", 0x53: "Up", 0x54: "Right", 0x55: "Down", 0x56: "Left",
}


def _row(y: float, x: float, keys: list) -> list:
    """[(name, width)…] placed left to right from x; a None name is a gap of that width."""
    out = []
    for name, w in keys:
        if name is not None:
            out.append((name, x, y, w))
        x += w
    return out


# ANSI TKL in key units (1 u = one letter key): (name, x, y, width). Drawn by the Keyboard page.
LAYOUT = (
    _row(0, 0, [("Esc", 1), (None, 1), ("F1", 1), ("F2", 1), ("F3", 1), ("F4", 1), (None, .5),
                ("F5", 1), ("F6", 1), ("F7", 1), ("F8", 1), (None, .5), ("F9", 1), ("F10", 1), ("F11", 1),
                ("F12", 1), (None, .25), ("PrtSc", 1), ("ScrollLock", 1), ("Pause", 1)])
    + _row(1.25, 0, [("`", 1), *[(c, 1) for c in "1234567890-="], ("Backspace", 2), (None, .25),
                     ("Insert", 1), ("Home", 1), ("PgUp", 1)])
    + _row(2.25, 0, [("Tab", 1.5), *[(c, 1) for c in "QWERTYUIOP[]"], ("\\", 1.5), (None, .25),
                     ("Delete", 1), ("End", 1), ("PgDn", 1)])
    + _row(3.25, 0, [("CapsLock", 1.75), *[(c, 1) for c in "ASDFGHJKL;'"], ("Enter", 2.25)])
    + _row(4.25, 0, [("LShift", 2.25), *[(c, 1) for c in "ZXCVBNM,./"], ("RShift", 2.75), (None, 1.25),
                     ("Up", 1)])
    + _row(5.25, 0, [("LCtrl", 1.25), ("LSuper", 1.25), ("LAlt", 1.25), ("Space", 6.25), ("RAlt", 1.25),
                     ("Fn", 1.25), ("Menu", 1.25), ("RCtrl", 1.25), (None, .25), ("Left", 1), ("Down", 1),
                     ("Right", 1)])
)
LABELS = {"Backspace": "⌫", "CapsLock": "Caps", "LShift": "Shift", "RShift": "Shift", "LCtrl": "Ctrl",
          "RCtrl": "Ctrl", "LSuper": "Super", "LAlt": "Alt", "RAlt": "Alt", "ScrollLock": "ScrLk",
          "PrtSc": "PrtSc", "Delete": "Del", "Insert": "Ins", "Space": "", "Up": "↑", "Down": "↓",
          "Left": "←", "Right": "→", "Enter": "Enter", "Tab": "Tab", "Pause": "Pause"}

# Lighting zones (0x8081) are numbered by HID usage, not by the analog key ids above:
# zone = usage - 3 (letters, digits, F-keys, navigation), modifiers 0xe0–0xe7 -> 0x68–0x6f.
USAGES = {
    **{chr(65 + i): 4 + i for i in range(26)}, **{str((i + 1) % 10): 0x1e + i for i in range(10)},
    "Enter": 0x28, "Esc": 0x29, "Backspace": 0x2a, "Tab": 0x2b, "Space": 0x2c, "-": 0x2d, "=": 0x2e,
    "[": 0x2f, "]": 0x30, "\\": 0x31, ";": 0x33, "'": 0x34, "`": 0x35, ",": 0x36, ".": 0x37, "/": 0x38,
    "CapsLock": 0x39, **{f"F{i + 1}": 0x3a + i for i in range(12)}, "PrtSc": 0x46, "ScrollLock": 0x47,
    "Pause": 0x48, "Insert": 0x49, "Home": 0x4a, "PgUp": 0x4b, "Delete": 0x4c, "End": 0x4d, "PgDn": 0x4e,
    "Right": 0x4f, "Left": 0x50, "Down": 0x51, "Up": 0x52, "Menu": 0x65,
    "LCtrl": 0xe0, "LShift": 0xe1, "LAlt": 0xe2, "LSuper": 0xe3, "RCtrl": 0xe4, "RShift": 0xe5, "RAlt": 0xe6,
}
# Keys without a magnetic switch (no analog settings), only an LED. Zones found 2026-10-02 by lighting
# them one by one. Fn has no LED of its own.
MEDIA_ZONES = {"Light": 0x96, "Play": 0x98, "Mute": 0x99, "Next": 0x9a, "Prev": 0x9b}


def zone(name: str) -> int | None:
    if name in MEDIA_ZONES:
        return MEDIA_ZONES[name]
    u = USAGES.get(name)
    if u is None:
        return None
    return u - 0x78 if u >= 0xe0 else u - 3


# The media / lighting keys sit above the navigation block.
MEDIA_LAYOUT = [("Light", 13.25, -1.1, 1), ("Prev", 14.5, -1.1, 1), ("Play", 15.5, -1.1, 1),
                ("Next", 16.5, -1.1, 1), ("Mute", 17.5, -1.1, .75)]
LABELS.update({"Light": "☀", "Prev": "⏮", "Play": "⏯", "Next": "⏭", "Mute": "🔇", "Menu": "☰"})
