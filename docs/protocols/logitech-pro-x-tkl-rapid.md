# Logitech G PRO X TKL RAPID (`046d:c35b`): HID++ notes

Wired keyboard with magnetic analog switches. Interface 2 (`HID_PHYS …/input2`) carries HID++:
report IDs `0x10` (short, 7 bytes) and `0x11` (long, 20 bytes), device index `0xFF`.
Read on firmware **U1 70.04 build 0020** (bootloader BL2 41.01), HID++ protocol **4.2**.

## Feature list (read 2026-10-01)

| # | ID | Ver | Name (from Solaar) | Notes |
|---:|---|---:|---|---|
| 1 | `0x0001` | 2 | FEATURE_SET | |
| 2 | `0x0003` | 7 | DEVICE_FW_VERSION | 4 entries: bootloader, main app, 2 empty |
| 3 | `0x0005` | 5 | DEVICE_NAME | "PRO X RAPID" |
| 4 | `0x0020` | 0 | CONFIG_CHANGE | |
| 5 | `0x0011` | 0 | PROPERTY_ACCESS | |
| 6 | `0x8071` | 4 | RGB_EFFECTS | zone effects; software control means claiming the LEDs (see Solaar `RGBControl`) |
| 7 | `0x8081` | 0 | PER_KEY_LIGHTING_V2 | |
| 8 | `0x1b10` | 0 | CONTROL_LIST | |
| 9 | `0x4523` | 1 | KEYBOARD_DISABLE_CONTROLS | not the `0x4521` Solaar implements |
| 10 | `0x4540` | 1 | KEYBOARD_LAYOUT_2 | |
| 11 | `0x8040` | 0 | BRIGHTNESS_CONTROL | **implemented** (see below) |
| 12 | `0x8101` | 0 | PROFILE_MANAGEMENT | Solaar only uses fn 6 (`0x60`) arg 5/3 around RGB takeover |
| 13 | `0x1b05` | 1 | FULL_KEY_CUSTOMIZATION | |
| 14 | `0x8051` | 0 | LOGI_MODIFIERS | |
| 15 | `0x1b08` | 0 | **unknown** | visible (not hidden) and undocumented: prime candidate for analog actuation / Rapid Trigger |
| 16 | `0x00c3` | 1 | DFUCONTROL | firmware update — never touch |
| 17 | `0x00d0` | 3 | DFU | firmware update — never touch |
| 18–31 | `0x1802 0x1803 0x1807 0x1817 0x1805 0x18a1 0x1e00 0x1e02 0x1602 0x1eb0 0x1801 0x18b0 0x920b 0xf008` | | engineering / hidden (type `0x40`/`0x60`/`0x70`) | never touch |

`rigdeck keyboard features` prints the live list.

## Brightness (`0x8040`), verified

| Fn | Request | Reply |
|---:|---|---|
| 0 getInfo | — | `[max hi, max lo, steps|flags, caps, min hi, min lo]` = `00 64 05 03 00 00`: 0–100, 5 steps, no on/off cap |
| 1 get | — | `[value hi, value lo]` |
| 2 set | `[value hi, value lo]` | echo; any value 0–100 is accepted (50, 37 read back exactly) |

## Onboard memory (`0x8101` PROFILE_MANAGEMENT), decoded from a G HUB capture

Decoded 2026-10-02 from a usbmon capture of G HUB 2026 in the win11 VM (`~/kbd-re/ghub-session1.pcap`),
then **read back on Linux** (reads only). Analog settings are not commands: they are small files in
the keyboard's flash, written through `0x8101` and tagged with the feature they belong to
(`0x1b08` analog, `0x1b05` key customisation, `0x8101` profiles). Every file carries a CRC-32
(standard zlib `crc32`, big-endian) that the keyboard checks; all of G HUB's writes matched it.

| Fn | Request | Reply / meaning |
|---:|---|---|
| 0 getInfo | — | `01 02 00 80 05 80 7f 7f 07 14 ff ff ff 20 03 07` |
| 1 list file slots | `[0, offset, 0]`, offsets 0x00/0x10/0x20 | `01 02 12 13 03 0c 0d 0e 0f 07 30 40` then 3-byte slots `e0 1b 08`, `e1 1b 08` … (`0x1b08` e0–e3, `0x1b05` e1–e3), `ff` ends |
| 2 start write | `[len hi, len lo, 0]` | — |
| 3 write chunk | 16 data bytes | reply `[0, chunk counter]` |
| 6 | `0f` / `00` / `05` | `0f` reads a status (`03 00 01` in onboard mode, profile 1; G HUB's `05` changes it) — only `0f` is sent by RigDeck |
| 8 open for read | `[bank, sector, len hi, len lo]` | — (read-verified on Linux) |
| 9 commit | `[feature hi, lo][file][02][len 3 B][crc32 4 B]` | stores the written buffer as that feature's file |
| 9 activate | `[feature hi, lo][file][00][dir entry][len 2 B][crc32 4 B]` | points the file back at an existing stored copy (G HUB's "reset to default") |
| 12 read | `[offset hi, offset lo]` | next 16 bytes of the opened sector (read-verified) |

**Banks / sectors** (fn 8): bank 1 = factory copies (sector 0 directory, 1–3 profiles, 4 a 0xbe file);
bank 0 = writable flash. Bank 0 sector 0 is the directory (0x400 bytes): 4-byte header, entry count,
then 10-byte entries `[entry id][feature 2 B][flags|len hi][len lo][crc32 4 B][sector]`; `ff` ends.
Read on 2026-10-02: entries 1–3 = `0x8101` profiles (0x6d bytes, sectors 8/9/0a, UTF-16 name
`PROFILE_NAME` inside), 4 = `0x1b08` 0xbe file (sector 0b, 94 keys × `05`), 7 = `0x1b08` actuation
(0xce bytes, sector 10).

### `0x1b08` files

All are `[count hi, count lo]` + `count` × `[key id, value]`, values in **0.1 mm**.

| File | Meaning | Seen |
|---:|---|---|
| 0 | actuation point per key | 102 keys, default `0x14` = 2.0 mm; one key → 1.0 mm; "all keys" changed the 87 physical keys (0x00–0x56); the other 15 ids are other layouts' keys |
| 1 | Rapid Trigger keys + sensitivity | empty = off; `00 01 1d 0a` = key 0x1d at 1.0 mm, then `1d 05` = 0.5 mm |
| 2, 3 | unknown (always written empty `00 00`) | |

Key ids (mapped 2026-10-02 with the live stream, ANSI; full map in `rigdeck/modules/keyboard/keymap.py`):

| Ids | Keys |
|---|---|
| `00`–`0c` | Esc F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12 |
| `0d`–`1a` | \` 1 2 3 4 5 6 7 8 9 0 - = Backspace |
| `1b`–`24` | Tab Q W E R F D S A CapsLock |
| `25`–`36` | LShift Z X C T Y U I O L K J H G V B N M |
| `37`–`41` | , P [ ] \ Enter ' ; . / RShift |
| `42`–`49` | LCtrl LSuper LAlt Space RAlt Fn Menu RCtrl |
| `4a`–`56` | PrtSc ScrollLock Pause PgUp Home Insert Delete End PgDn Up Right Down Left |

The order snakes through the switch matrix (… R `1f`, F `20`, D `21`, S `22`, A `23` …), so it can't be
derived from the layout. `0x47` is Fn (no HID usage). `0x57`–`0x6f` in the actuation file are
keys of other layouts; G HUB's "all keys" changes only `0x00`–`0x56`. `0x1b05` files 1–3 were also
written empty at G HUB start.

**Applying** (G HUB order): file 0 then 1 then 3, each as fn 2 (length) → fn 3 chunks → fn 9 commit.
Changes take effect at once.

**Verified on Linux 2026-10-02** (keyboard in normal onboard mode, `0x8101` fn 6 `0f` → `03 00 01`,
no G HUB "software mode" needed): writing file 0 with only W (0x1d) at 1.0 mm was accepted (CRC
`f41d75cf`, identical to G HUB's) and W then fired at 1.0 mm while E fired at 2.0 mm (measured with
the live depth stream at the moment of the HID key-down). **These writes are live, not stored**: the
directory and the profiles were unchanged afterwards. fn 9 *activate* `1b 08 00 00 07 00 ce <crc of
entry 7>` put it back to the stored file (W 2.0 mm again).

**Profile switches wipe live settings** (Fn+F3 → Fn+F2: W back to 2.0 mm). `0x8101` fn 6 `0f` →
`03 00 <active profile 1–3>` reports the switch, so RigDeck's service polls it and re-applies
(verified: W at 1.0 mm again within ~1 s). **Rapid Trigger also needs `0x1b08` fn 2 `[1]`** (master
switch; `[0]` off) — with only file 1 written, keys still released at ~1.5 mm; with fn 2 `[1]`, E at
0.5 mm released 0.5 mm off the bottom (3.3–3.5 mm after 4.0). G HUB sends fn 2 before the files.

### `0x1b08` functions

| Fn | Request | Meaning |
|---:|---|---|
| 0 getInfo | — | `01 05 80 28`: 0x28 = 4.0 mm total travel (0.1 mm units) |
| 1 | — | `00 …` |
| 2 | `[0/1]` | Rapid Trigger master switch (verified) |
| 3 | `[0/1]` | live key-depth stream on/off: events `fn 0 [key id][depth 0.1 mm]`, e.g. key 0x42 0→0x28→0. **Lossy** when typing fast (events dropped, keys left "half pressed"): fine for a one-key-at-a-time UI, not for tracking real typing |

## Lighting (`0x8071` RGB_EFFECTS)

Colour changes in G HUB were single fn 1 calls, not files:
`fn1 [zone 0][effect 01 = static][R G B][02 …][… 01]`, e.g. `00 01 f8 2f 25 02 00 00 00 00 00 00 01`.
Each is followed by `0x1b05` fn 1 (reply `01`).

## Still to decode

- `0x8101` fn 6 values other than `0f` (G HUB's `05` = software mode?).
- Onboard profile switching (G HUB re-committed profile files 1→2→3→1 at 171–178 s).
- How "save lighting to onboard memory" is stored (no lighting file write was seen).

## Capture session guide (G HUB in a Windows VM, recorded on Linux)

A USB device passed through to a VM still goes through Linux's USB stack, so `usbmon` on the host
records G HUB's traffic; nothing needs installing in Windows besides G HUB.

**While the keyboard is in the VM, Linux has no keyboard** — the capture below stops by itself, and
everything else is done with the mouse.

1. On Linux, start the recording (bus 3 is where the keyboard is plugged; check with
   `lsusb | grep c35b`). It stops after 15 minutes:

   ```
   sudo modprobe usbmon
   sudo timeout 900 tshark -i usbmon3 -w ~/gh-capture.pcapng
   ```

2. Start the `win11` VM, then pass the keyboard to it: virt-manager → the VM → *Add Hardware* →
   *USB Host Device* → *Logitech PRO X RAPID*. (Remove it again at the end the same way.)
3. In Windows, open G HUB and wait until it shows the keyboard. Then do these one at a time, and
   **between steps press Caps Lock 3 times** (the keyboard's LED reports mark the boundaries in
   the capture), waiting ~5 s before and after:
   1. Change the actuation point of one key (e.g. W) to a clearly different value (e.g. 1.0 mm).
   2. Change the actuation point of all keys.
   3. Turn Rapid Trigger on for one key; then change its sensitivity.
   4. Change lighting to a static red, and save it to the keyboard's onboard memory.
   5. Switch to another onboard profile in G HUB, then back.
   6. Undo everything (back to how it was) the same way, one step at a time.
4. Remove the keyboard from the VM (or shut the VM down) and wait for the recording to stop.
5. Hand over `~/gh-capture.pcapng`. Then, on Linux, filter the HID++ traffic of the keyboard's
   device number (`lsusb`: "Device 003") with
   `tshark -r gh-capture.pcapng -Y "usb.device_address == 3 && usb.capdata" -T fields -e frame.time_relative -e usb.endpoint_address -e usb.capdata`
   and diff the `11 ff <feature index> …` reports between the steps.
