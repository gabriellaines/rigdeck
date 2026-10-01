# Changelog

Release notes are collected automatically: every commit with a user-visible change ends with a
`Changelog: …` line, and `scripts/bump-version.sh X.Y.Z` gathers those lines (plus anything
written by hand under **Unreleased**) into the new version's section. Preview the next release's
notes with `scripts/unreleased.sh`. The text becomes the GitHub release notes, which RigDeck shows
in its update dialog — write for users, not developers.

## Unreleased

## 0.5.0 — 2026-10-01

- The "Water Cooler" page is now called "Cooler"
- New Monitors page: brightness (for one monitor or all at once), contrast, color preset, volume and input, for monitors with DDC/CI
- New Motherboard page: board model, BIOS version, board temperatures and fan headers
- New Wi-Fi & Bluetooth page: Wi-Fi signal and speed, Ethernet link speed, Bluetooth on/off and the battery levels of your Bluetooth devices
- The Overview shows Wi-Fi and connected Bluetooth devices too
- Control ASUS Aura motherboard lighting from the Motherboard page: off, static color, breathing, flashing, color cycle and rainbow, for the board and its RGB and ARGB headers
- Updating asks for your password once more, to let RigDeck reach the motherboard lighting controller
- Fixed: pages could stop updating, or keep settings greyed out, after a device didn't answer once (e.g. the headset after changing auto-off, the mouse after switching between cable and receiver)
- The Mouse page notices plugging, unplugging and switching between cable and receiver within seconds, and switching between mice no longer blanks the page
- The Overview lists every connected mouse with its battery
- The mouse and webcam switchers sit side by side instead of one per line
- The Headset page notices the headset turning on or off within a few seconds
- Fixed: the headset beeped every few seconds and could ignore setting changes while the RigDeck app was open
- The headset's auto power-off only offers times the headset supports (up to 30 minutes on the HyperX Cloud II Wireless)

## 0.4.0 — 2026-10-01

- New Headset page: battery level, hearing yourself (sidetone), turning off when idle and lights, for headsets supported by HeadsetControl such as the HyperX Cloud II Wireless
- The Overview lists your peripherals with their battery levels
- New Webcam page: adjust brightness, white balance, exposure, focus and zoom with a live preview; works with any standard webcam such as the Logitech C920
- Webcam settings are remembered and re-applied whenever the camera is plugged in
- New Mouse page for the Pulsar Xlite V3 and Attack Shark X11 Ultra: battery level, DPI stages, polling rate (up to 8000 Hz), motion sync, angle snapping, ripple control and light
- Mouse settings are saved on the mouse itself, and RigDeck backs them up before its first change
- This update asks for your password once, to let RigDeck reach your mouse and keyboard
- New Keyboard page for the Logitech G PRO X TKL RAPID: lighting brightness; actuation and Rapid Trigger aren't adjustable from RigDeck yet

## 0.3.1 — 2026-10-01

- Install with one line, no git needed: `curl -fsSL https://raw.githubusercontent.com/gabriellaines/rigdeck/main/get.sh | bash`
- The installer no longer stops when it can't ask a question; it uses the default answer

## 0.3.0 — 2026-10-01

### GPU controls

RigDeck can now control your graphics card, not just monitor it. It uses
[LACT](https://github.com/ilya-zlobintsev/LACT)'s background service, which applies
the settings and keeps them across reboots and suspend.

- **Fan:** automatic, custom curve (drag the points), or fixed speed
- **Zero RPM:** choose whether the fans may stop while the GPU is cool
- **Power limit:** within the card's allowed range; you confirm the change, or it reverts on its own after a few seconds
- **CLI:** `rigdeck gpu status | fan | power | enable-controls`

**AMD RDNA3/RDNA4 cards:** fan control needs the driver's *overdrive* option.
Go to **Graphics → Enable GPU controls** (or run `rigdeck gpu enable-controls`), then reboot.
On Limine systems such as CachyOS, RigDeck adds the kernel option for you.

### Also in this release

- On/off switches now use the accent color, including in dark mode
- The power-limit slider now shows the current limit when the page first opens

## 0.2.0

- New Qt 6 / QML desktop app (replaces GTK), dark and light themes
- Overview with live temperatures, fan and pump speed, fan curve and devices
- Water Cooler page: cooling modes and curve editor, lighting, screen (carousel, ordering, upload, delete, rotation)
- Graphics, Processor, Memory and Storage pages
- Update checks and in-app updates

## 0.1.0

- First release: AORUS WATERFORCE X II support (fans, pump, curves, RGB, LCD screen), CLI and GTK app
