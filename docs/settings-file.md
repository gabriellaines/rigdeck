# Settings files

A settings file holds your device settings — DPI, polling rate, sensor options, colours, fan
curve, key actuation… — in one [JSON](https://www.json.org) file. Import it to set everything at
once: on a new install, after a reset, or to switch between setups.

- **App:** Settings → *Settings file* → **Import settings file…** / **Export current settings…**
- **Terminal:** `rigdeck export my-setup.json`, `rigdeck import my-setup.json`
  (`--check` only checks the file).

The easiest start is to **export your current settings** and edit that file. A full example is in
[`example-settings.json`](example-settings.json).

## How it works

- **Every part is optional.** Leave out a device, or a setting, and it stays as it is. This is a
  complete file that only changes the DPI of every mouse:

  ```json
  { "mice": [ { "dpi": [800, 1600] } ] }
  ```

- **The whole file is checked first.** A mistake (a typo, a value out of range) means nothing is
  changed, and you get a list of every problem with where it is, e.g.
  `mice[0].dpis: unknown setting — did you mean 'dpi'?`
- **Each device is set on its own.** If one isn't connected (or the mouse is asleep), the others
  are still set, and the result says which one was skipped. Import again once it's back.
- Colours are written `"ff0000"` or `"#ff0000"`. Distances are in millimetres, times in the units
  shown below.

## Sections

### `cooler` — AORUS WATERFORCE

| Setting | Values |
|---|---|
| `fan` | `default`, `zero-rpm`, `quiet`, `balanced`, `performance`, `turbo`, `custom` |
| `pump` | `balanced`, `turbo` |
| `curve` | 4 points `[temperature °C, fan rpm]`, temperatures going up, e.g. `[[30, 1000], [50, 1400], [65, 1900], [80, 2500]]` (sets `fan` to `custom`) |
| `lighting` | `{"effect", "color", "brightness" (0–100), "speed" (1–10)}`; effects: `static`, `pulse`, `flash`, `dflash`, `cycle`, `rainbow-wave`, `off` |

### `motherboard` — ASUS Aura lighting

`"lighting": {zone: {"effect", "color"}}`. Zones are listed by `rigdeck motherboard lighting`
(e.g. `board`, `argb1`); `all` means every zone. Effects: `off`, `static`, `breathing`,
`flashing`, `cycle`, `rainbow`.

### `keyboard` — Logitech G PRO X TKL RAPID

| Setting | Values |
|---|---|
| `brightness` | 0–100 (%) |
| `profiles` | `"1"` (Fn+F2), `"2"` (Fn+F3), `"3"` (Fn+F4), each with the settings below |

In a profile:

| Setting | Values |
|---|---|
| `actuation` | every key's actuation point, 0.1–4.0 (mm) |
| `rapidTrigger` | Rapid Trigger sensitivity for every key, 0.1–4.0 (mm), or `"off"` |
| `keys` | per key: `{"W": {"actuation": 0.8, "rapidTrigger": 0.2}}` |
| `color` | colour of every key |
| `keyColors` | per key: `{"W": "ff0000"}` |

Key names are the ones on the Keyboard page (`Esc`, `F1`, `` ` ``, `1`, `Q`, `LShift`, `Space`,
`Up`…). Profile settings are kept by RigDeck and put on the keyboard when that profile is active,
so they're used even if the keyboard is unplugged while you import.

### `mice` — Pulsar Xlite V3, Attack Shark X11 Ultra

A list; each entry applies to the mouse named in `model`, or to every mouse without it.
Settings are stored on the mouse.

| Setting | Values |
|---|---|
| `model` | `Pulsar Xlite V3`, `Attack Shark X11 Ultra` (optional) |
| `pollingRate` | 125, 250, 500, 1000, 2000, 4000, 8000 (Hz, up to what the receiver supports) |
| `dpi` | 1–8 DPI stages, e.g. `[800, 1600, 3200]` |
| `stage` | the active stage, 1 = first |
| `stageColors` | colour of each stage's light |
| `light` | `{"effect": "steady" / "breathing" / "off", "brightness": 1–10, "speed": 1–5}` |
| `motionSync`, `angleSnapping`, `rippleControl` | `true` / `false` |
| `debounce` | 0–15 (ms) |
| `liftOff` | `0.7`, `1`, `2` (mm) — X11 Ultra |
| `sensorMode` | `"low power"`, `"high performance"` — X11 Ultra |
| `competitive`, `fps20k` | `true` / `false` — X11 Ultra |
| `competitiveTimer` | `"10 s"`, `"30 s"`, `"1 min"`, `"2 min"`, `"5 min"`, `"10 min"`, `"15 min"` — X11 Ultra |
| `angleTune` | −30 to 30 (degrees), or `"off"` — X11 Ultra |

### `headset` — through HeadsetControl

`sidetone` (0–128), `autoOffMinutes` (0 = never), `lights`, `voicePrompts`, `rotateToMute`
(`true` / `false`). The headset has to be on.

### `lighting` — one colour everywhere

`{"sync": "00c8ff"}` puts one colour on every device with lighting, like the Lighting page. It's
applied last, so it wins over colours set above; *Restore previous lighting* on the Lighting page
undoes it.

### `rigdeck`

The format version, `1`. Optional.
