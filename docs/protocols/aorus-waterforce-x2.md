# AORUS WATERFORCE X II 360 — USB protocol (0414:7a5e, ITE "Castor3")

Reverse-engineered for interoperability from GIGABYTE Control Center 26.08 (analysis of the
application) and confirmed with USB captures of GCC driving a real cooler (firmware 1.9).
**[code]** = taken from GCC's behavior, **[cap]** = also observed on the wire.

On the wire every report starts with **HID report ID `0x99`** (output reports 6144 bytes,
input 256), so the tables below list commands *including* that leading `0x99`.

## Transport
- One HID interface, interrupt EP 0x02 OUT, EP 0x81 IN. No report ID on the wire.
- Every command is zero-padded to the output report length (**6144 bytes** observed). [cap]
- Replies are 256 bytes and echo bytes 0–1 of the command (`99 xx`); GCC discards
  replies whose first bytes don't match. [code][cap]
- All commands start with `0x99`.

## Device / info
| Cmd | Dir | Layout | Meaning |
|---|---|---|---|
| `99 d6` | query | reply `[2]=major [3]=minor` | firmware version (ours: 1.9) [code][cap] |
| `99 de` | query | reply `[2]` 0=X II 240, 1=X II 360I, 2=X II 360 | model variant [code][cap] |
| `99 c7` | query | reply `[2]` | fan quantity |
| `99 c8 n` | set | | fan quantity |
| `99 b6` | set | | **save settings to cooler flash** (GCC sends after changes) |

## Pump / fans  (SpeedType: 1=fan, 2=pump)
SpeedMode: 0 Balanced, 1 Customized, 2 Default, 3 FixedRPM, 4 Turbo, 5 Performance, 6 Quiet, 7 ZeroRPM.
| Cmd | Layout | Meaning |
|---|---|---|
| `99 e5 type mode` | set | select mode for fan or pump. GCC's Apply always sends fan, then pump, then `99 b6` (save) [cap: fan 00/01/04/05/06/07 and pump 00/04 all seen] |
| `99 dd` | reply `[2]=fan mode [3]=pump mode` (3 is reported as 0) | get modes |
| `99 e6 00 type t0 s0hi s0lo t1 s1hi s1lo t2 … t3 s3hi s3lo` | set | custom curve: 4 points, temp °C + RPM (big-endian). Sent after `e5 01 01` (Customized) [cap: `00 03e8 1e 03e8 32 05dc 50 09c4` = 0°C/1000, 30°C/1000, 50°C/1500, 80°C/2500] |
| `99 d9 type` | reply same layout from `[4]` | get custom curve |
| `99 da` | reply `[2..4]` fan RPM (LE 24-bit), `[5..7]` pump RPM | live RPM [cap: 0x04f9=1273 fan, 0x0a88=2696 pump — matches GCC UI] |

Preset curves for X II (points at 0/30/50/65 °C), RPM:
- Fan: Balanced 1200/1200/1400/1800, Default 1200/1200/1400/2000, Turbo 2300/2300/2300/2400,
  Performance 1800/1800/1800/2400, Quiet 1000/1000/1000/1500, Customized 2250 flat.
- Pump: Balanced 2500/2500/2500/3000, Customized 2800 flat, Turbo 3000 flat.
- Fan limits for this PID: 1000–2800 RPM. Max speed constant: 3200.

## Live data — the cooler's curves follow the temperature the HOST sends
`99 e0 vendor cpuTemp threads ghz ghz_tenths cores vramTemp liquidTemp cpuUsage pwrLo pwrHi`
(13 bytes, firmware < 2.0). Sent every ~1.5 s by AorusLcdService. [code][cap]
In the VM cpuTemp was always 0 (no sensor) → fans sat at the curve's 0 °C point.
Firmware ≥ 2.0 ("Elite") uses a 24-byte variant with GPU fields.

| Cmd | Layout | Meaning |
|---|---|---|
| `99 e1 len ascii…` | set | CPU name shown on screen [cap] |
| `99 ef 00 len ascii…` | set | GPU name |

## LCD screen
| Cmd | Layout | Meaning |
|---|---|---|
| `99 e7 mode+1 param` / `99 e8` | set/get | screen mode |
| `99 e2 b0..b5 ×4` | set | which info widgets are shown (4 groups × 6 flags) / `99 df` get |
| `99 e4 mode+1 R G B ×4` | set | zone colours for a screen mode / `99 ea` get |
| `99 ce angle/30` / `99 ff` | set/get | rotation (0/30/…; UI uses 0/90/180/270) |
| `99 aa i1 i2 i3` / `99 ab` | set/get | refresh intervals |
| `99 ac unit` / `99 ad` | set/get | temperature unit |
| `99 ae on` / `99 af` | set/get | show CPU name |
| `99 c0 text logo info` / `99 c1` | set/get | show text / AORUS logo / info |
| `99 fb interval m1+1 m2+1 …` / `99 fc` | set/get | rotate between screen modes |
| `99 fa disk` | reply `[2]=n, [3..]` LE size in KB | free space; GCC sends disk `0x42`='B' [cap: `02 59 ba` = 47705 KB = 46.56 MB shown in UI] |
| `99 fe len path` | set | delete a file on the cooler, e.g. `B:/spidey.mkv` |
| `99 f3/f4/f5` | | list stored media |
| `99 f0 mode+1 idx+1…` / `99 f6 mode+1 interval idx+1…` / `99 fd` | | media list / loop selection |
| `99 c2` | reply `[2]` | flash write progress % |

### Image / GIF upload (`SendImage`)
1. `99 f1 01 size(BE32) nameLen+1 name…` — begin upload, file name in UTF-8.
2. Repeated `99 f2 fd <payload…>` — data chunks of (reportLen − 3) = 6141 bytes; the final chunk
   has byte 2 = (remaining & 0xFF) instead of `fd` (truncated to a byte, so the cooler must rely
   on the declared size). [cap]
3. `99 f1 mode size(BE32)` — commit (mode 2 for GIF). Then poll `99 c2` (flash %) every 2 s. [cap]
4. The upload is stored but **not played** until it's added to the carousel (below). [cap]

### Carousel (which stored files play, and in what order)  [cap + verified on hardware]
All use screen mode `07` (Custom GIF). Two different numberings are involved:

- **File ID** — fixed, 1-based, in upload order (survives reordering; renumbered after a delete).
- **Position** — 1-based place in the current play order.

The `f5` listing returns files **in play order** (positions), not by ID.

| Cmd | Layout | Meaning |
|---|---|---|
| `99 f0 07 id id …` | set | play order, as **file IDs** (every file once) |
| `99 f6 07 secs pos pos …` | set | which **positions** of that order play, seconds each; then `99 b6` |
| `99 fd 07` | reply `[3]=secs [4..]=positions` (0-terminated) | read the selection |

Finding the IDs: send `f0 07 01 02 … n` (identity), list with `f3/f4/f5` → that listing is in ID
order; then send `f0` again to restore the previous order. Verified: with order
`spider, spidey, Aorus, spid2` (IDs 2,3,1,4), `f6 07 05 03` showed **Aorus** (position 3), not
spidey (ID 3). One file selected = a single static animation; GCC's UI offers 5/10/15… s.

**File format:** GCC only accepts GIFs, crops them in a dialog, then converts with its bundled
ffmpeg into **Matroska + H.264 (Main, yuv420p), 320×320, 25 fps**, stored as `<name>.mkv`.
Encoder settings matter: GCC uses `-profile:v main -level 3.1 -b:v 1000K -bf 0` (default preset →
ref=3). **The cooler's decoder can't handle B-frames** — a file encoded with them plays as green,
blocky garbage. [verified]

**Delete:** `99 fe len "B:/<name>.mkv"` (path format from GCC for this screen mode). File indexes
shift afterwards, so re-send the carousel.
File name ≤ 64 bytes UTF-8. A captured upload was reassembled byte-exact and plays back correctly.
`99 e8` reply `[2]=07` while in "Custom Gif" mode.

## LEDs  [cap — built inside native GcLedLib.dll, so wire-only]
Only two LED commands appear on the wire:
| Cmd | Layout | Meaning |
|---|---|---|
| `99 c9 effect 64 p4 p5 p6` | set | hardware effect. Seen: `01 64 0a cc` = Static, `08 64 09 cc cc` = Rainbow Wave. Byte 3 = 0x64 (100) always; bytes 4–6 meaning unknown → replay verbatim |
| `99 cd R G B` | set | the colour shown in Static mode |

- **Brightness is applied on the PC side**: GCC scales the RGB before sending (white at
  default = `cc cc cc`, lower brightness = `99 99 99`, max = `ff ff ff`).
- **Off** = Static + `99 cd 00 00 00`.
- **Only Static (`01`) and Rainbow Wave (`08`) are hardware effects.** Everything else is GCC
  streaming `99 cd` from the PC while it runs (stops when GCC/the PC is off): [cap]
  - Pulse: ramp 0 → ff → 0 in 0x19 steps every ~33 ms (~1 s period).
  - Flash: colour / black toggling, ~0.75 s period.
  - Dflash: two quick flashes per ~1.2 s period.
  - Cycle: hue sweep (ff1900, ff3300 … ) — smooth colour wheel.
