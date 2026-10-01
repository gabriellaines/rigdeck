# Changelog

Release notes are collected automatically: every commit with a user-visible change ends with a
`Changelog: …` line, and `scripts/bump-version.sh X.Y.Z` gathers those lines (plus anything
written by hand under **Unreleased**) into the new version's section. Preview the next release's
notes with `scripts/unreleased.sh`. The text becomes the GitHub release notes, which RigDeck shows
in its update dialog — write for users, not developers.

## Unreleased

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
