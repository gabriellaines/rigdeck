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

## Next: decoding the analog settings

Calling undocumented functions blind is unsafe (any of them may write to flash), so the plan is
to observe G HUB instead:

1. Windows VM with G HUB, keyboard passed through; USBPcap + Wireshark on the VM.
2. Capture while changing **one** thing at a time in G HUB: actuation point of one key, then all
   keys; Rapid Trigger on/off; RT sensitivity; switching profiles F2–F5.
3. Filter HID++ long reports (`0x11`) whose feature index matches `0x1b08`'s index (look it up with
   root fn 0 on the same session) and diff the payloads between captures.
4. Write down request/response layouts here, then verify each read on Linux before any write.

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
