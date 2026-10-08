# Changelog

Written automatically when a release is published: each commit's `Changelog: …` lines, or its
summary line when it has none (internal-only commits are left out), plus anything written by hand
under **Unreleased**. Preview the next release's notes with `scripts/unreleased.sh`. The text
becomes the GitHub release notes, which RigDeck shows in its update dialog.

## Unreleased

## 0.8.1 — 2026-10-08

- The Lighting page now updates by itself when you plug a device in or unplug it
- While lighting is synced, devices you connect later get the colour automatically (the ones you switched off are left alone)
- The left menu now scrolls, so every page stays reachable in a small window

## 0.8.0 — 2026-10-06

- New Lighting page: put one colour on your cooler, motherboard, keyboard and mice at once, like SignalRGB
- Restore puts every device back to the lighting it had before you synced them
- When a new version is out, a button next to the light/dark switch says so; click it to update from Settings
- RigDeck now also looks for updates every few hours while it's open, not only when it starts
- Settings files: export all your device settings (DPI, polling rate, colours, fan curve, key actuation…) to one file, and import a file to set everything at once
- An imported file is checked first; any mistake is pointed out and nothing changes until it's fixed

## 0.7.1 — 2026-10-05

- Resources > CPU can now show a separate graph for each logical processor, like Task Manager
- Resources > CPU now shows running processes and threads, up time, max boost clock, virtualization and cache sizes

## 0.7.0 — 2026-10-03

- New Game monitor: record CPU, GPU, memory and disk readings while you play, then review averages, peaks and graphs for each session
- With MangoHud, game sessions also get FPS, frametimes and 1% / 0.1% lows (the Game monitor page can set it up; the MangoHud overlay shows in games)
- Monitors: new colour vibrance slider for each screen, like NVIDIA's Digital Vibrance (KDE Plasma on Wayland)
- Keyboard: the page now shows each onboard profile's actuation point and Rapid Trigger settings (PRO X TKL RAPID)
- New `rigdeck keyboard analog` command lists the same settings
- Keyboard: set the actuation point and Rapid Trigger for each onboard profile, for all keys or key by key (PRO X TKL RAPID)
- Your keyboard settings come back automatically after switching profiles with Fn + F2 / F3 / F4 or plugging the keyboard back in
- New `rigdeck keyboard analog-set` and `analog-reset` commands
- Keyboard: a picture of the keyboard where you select keys and set their actuation point, Rapid Trigger and colour
- Keyboard: per-key colours (and a background colour) for each onboard profile, kept after profile switches
- Keyboard: selecting all keys and changing their colour works (it failed with an error)
- Graphs no longer flicker when they update: new readings slide in smoothly
- Cleaner buttons and sliders, and the sidebar is grouped into Monitoring, Hardware and Devices
- Keyboard page reorganised: pick a profile, then set every key at once or individual keys; Rapid Trigger is now "Release: Rapid" with a release distance
- Overview, Motherboard, Graphics and Mouse pages are simpler, with clearer wording
- Fan curve charts no longer flash while the page refreshes
- Changing keyboard settings (brightness, keys, colours) no longer makes the page flicker
- After sleep, a reboot or replugging, the keyboard goes back to the profile you were using, with your RigDeck settings
- Pages no longer flicker when their numbers update: lists and graphs stay in place and just change
- Keyboard page simplified: select keys (or none for all keys) and set them in one place, with a picture of the key's travel showing where it types and lets go
- Game monitor: alt-tabs during a session are detected (KDE Plasma) and listed, with those moments shaded on the graphs
- Game monitor: Average FPS and 1% low also show in-game figures that leave the alt-tab time out
- Exported session CSVs now include FPS for each second, the focused window, every alt-tab and an FPS summary

## 0.6.0 — 2026-10-01

- New Network page with Ethernet and Wi-Fi tabs: link speed or signal, live download and upload, addresses, and nearby Wi-Fi networks
- Bluetooth now has its own page, shown only while a Bluetooth device is connected
- Bluetooth headphones, mice and keyboards appear on the Headset, Mouse and Keyboard pages with their battery level
- New Resources page: live graphs of CPU, memory, each disk, each network adapter and the graphics card over the last minute, like Task Manager's Performance tab
- The Processor page shows a load graph for every thread and the CPU's specifications: base and boost clocks, caches, virtualization, instruction sets and frequency driver
- The Memory page lists your memory modules: maker, part number, size and rated (XMP) speed, plus a usage graph
- The Storage page shows each drive's health: SSD wear, data written, hours powered on and bad sectors, with live read and write speeds
- The Overview is reorganised: cooling, a live usage panel and system summary on the left, your devices on the right, with full device names
- Metric cards in a row now all have the same height
- RigDeck uses about a third of the CPU it used before, and nothing while its window is minimised
- Attack Shark X11 Ultra: competitive ("Hunting Shark") mode, sensor power mode, 20K FPS scanning, lift-off distance, angle tuning and button debounce on the Mouse page

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
