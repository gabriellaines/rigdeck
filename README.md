# rigdeck

A lightweight control panel for PC hardware on Linux — as a **command-line tool** and a
**Qt 6 / QML desktop app** in a calm, Breeze-style design (dark and light). Use whichever you like.

Built because vendor tools (GIGABYTE Control Center, …) are Windows-only, heavy, and
the only way to control some hardware.

| Device | Status |
|---|---|
| GIGABYTE **AORUS WATERFORCE X II** 240 / 360 / 360 ICE (USB `0414:7a5e`) | ✅ fans, pump, curves, RGB, LCD screen |
| GIGABYTE AORUS ELITE 240 / 360 AIOs (`0414:7a69`–`7a6c`) | 🧪 same protocol family, untested |
| GPUs: temperatures, fan, power, clocks, VRAM, drivers | ✅ monitoring |
| GPU fan mode, curve, **zero-RPM on/off**, power limit (via [LACT](https://github.com/ilya-zlobintsev/LACT)) | ✅ |
| Processor, memory (incl. zram), storage (incl. NVMe temperature) | ✅ monitoring |
| Headsets supported by [HeadsetControl](https://github.com/Sapd/HeadsetControl) (HyperX, SteelSeries, Logitech, Corsair…): battery, sidetone, auto power-off, lights | ✅ (needs HeadsetControl) |
| Wireless mice: **Pulsar Xlite V3**, **Attack Shark X11 Ultra** (Compx 3554): battery, DPI stages, polling rate up to 8K, motion sync, angle snapping, ripple control, light | ✅ |
| Webcams (any UVC camera, e.g. Logitech C920): brightness, white balance, exposure, focus, zoom, live preview | ✅ |

## Install

Open a terminal, paste this line and press Enter:

```sh
curl -fsSL https://raw.githubusercontent.com/gabriellaines/rigdeck/main/get.sh | bash
```

It downloads the latest release, asks for your password once (to install system packages and
give your user access to the cooler), and asks whether you want the graphical app — press
Enter for yes. When it finishes, open **RigDeck** from your app menu. Updates are offered
inside the app from then on.

Works on Arch / CachyOS / Manjaro, Fedora, Debian / Ubuntu and openSUSE. If `curl` is
missing, install it with your package manager first (e.g. `sudo apt install curl`).

<details>
<summary>Options, uninstalling, and what the installer changes</summary>

Pass options after `bash -s --`:

```sh
curl -fsSL https://raw.githubusercontent.com/gabriellaines/rigdeck/main/get.sh | bash -s -- --gui        # app, no questions
curl -fsSL https://raw.githubusercontent.com/gabriellaines/rigdeck/main/get.sh | bash -s -- --cli-only   # terminal tool only
curl -fsSL https://raw.githubusercontent.com/gabriellaines/rigdeck/main/get.sh | bash -s -- --uninstall  # remove (keeps your settings)
```

`RIGDECK_VERSION=v0.3.0` before `bash` installs a specific release. From a git checkout,
`./install.sh` takes the same options.

The installer:

1. installs Python ≥ 3.11 and ffmpeg (and Qt 6 for Python — PySide6 — if you want the app) from your distro,
2. installs rigdeck into `~/.local` (its own virtualenv — nothing touches system Python),
3. adds a **udev rule** so your user can talk to the cooler without root,
4. enables the **`rigdeck` user service**,
5. on Arch-based systems, offers to install [LACT](https://github.com/ilya-zlobintsev/LACT) for GPU
   fan and power controls (elsewhere, see LACT's [installation guide](https://github.com/ilya-zlobintsev/LACT#installation)).

</details>

**Arch / AUR:** a `PKGBUILD` is in [`packaging/arch`](packaging/arch). After installing the
package run `systemctl --user enable --now rigdeck`.

### Why a background service?

The WATERFORCE doesn't measure CPU temperature itself — **the PC has to send it**, every
second or two, and the fan/pump curves react to that number. On Windows, GCC's
`AorusLcdService` does this; on Linux, `rigdeck service` does. Without it the cooler keeps
using the last temperature it received. The service also animates the lighting effects
that the cooler can't run on its own (pulse, flash, color cycle).

## Command line

```sh
rigdeck info                                   # CPU, GPU, Mesa/Vulkan/driver versions, detected devices
rigdeck cooler status                          # RPM, modes, custom curve, storage
rigdeck cooler mode --fan quiet --pump balanced
rigdeck cooler mode --curve 30:1000 50:1400 65:1900 80:2500   # custom fan curve
rigdeck cooler led static ff0000 -b 60         # static | pulse | flash | dflash | cycle | rainbow-wave | off
rigdeck cooler screen upload my.gif            # any GIF / video / image → 320×320 animation
rigdeck cooler screen rotate 90
rigdeck cooler screen list                     # ▶ marks what's playing
rigdeck cooler screen play 3 0 2               # play files 3, 0, 2 in that order (`play 2` = just one)
rigdeck cooler screen delete old.mkv
rigdeck gpu status                             # temperatures, fan, zero-RPM, power limit
rigdeck gpu fan auto --zero-rpm off            # driver curve, but fans never stop
rigdeck gpu fan curve --curve 40:30 60:50 80:100
rigdeck gpu power 280                          # watts, or `default`
rigdeck gpu enable-controls                    # one-time: AMD overdrive, then reboot
rigdeck headset status                         # battery and settings
rigdeck headset sidetone off                   # or on, or a level 0–128
rigdeck headset auto-off 30                    # minutes idle before it turns off (0 = never)
rigdeck mouse status                           # battery, DPI stages, polling rate, light
rigdeck mouse set --dpi 800 1600 --rate 2000   # saved on the mouse itself
rigdeck webcam status                          # all controls and their values
rigdeck webcam set brightness=140 focus_automatic_continuous=off
rigdeck update                                 # update to the latest GitHub release
```

### GPU controls

RigDeck is a friendly front-end for [LACT](https://github.com/ilya-zlobintsev/LACT)'s background
service, which applies GPU settings as root and re-applies them after reboot and suspend (it also
supports NVIDIA and Intel cards). On AMD RDNA3/RDNA4 cards, fan control additionally needs the
driver's *overdrive* switch: **Graphics → Enable GPU controls** (or `rigdeck gpu enable-controls`)
turns it on and asks you to reboot. On Limine-based systems (e.g. CachyOS) RigDeck adds the kernel
option through `/etc/default/limine`, because the initramfs route doesn't apply there.
Power-limit changes ask you to confirm within a few seconds, or they revert.

Fan and pump modes are saved on the cooler itself. Lighting settings live in
`~/.config/rigdeck/config.toml` and are applied by the service.

## The app

`rigdeck-gui` (or **RigDeck** in your app menu). The **Overview** shows live CPU/GPU
temperatures, fan and pump speed, the fan curve and your devices; the sidebar has a page per
device plus **Graphics, Processor, Memory, Storage** and **Settings**. The **Water Cooler** page
has **Cooling** (modes + drag-to-edit curve), **Lighting** (effects, color, brightness, speed) and
**Screen** (preview, one animation or a carousel with ordering, upload, delete, rotation).
Open a page directly with `rigdeck-gui --page cooler`.

**Updates:** RigDeck checks GitHub for a new release when it starts (turn off in Settings).
If you installed with the command above, *Settings → Update now* downloads and installs it; with the
AUR package, update through your package manager.

## Notes

- **Virtual machines:** if you pass the cooler through to a Windows VM, Linux loses access
  while the VM runs; the service reconnects automatically when it's back.
- The protocol was reverse-engineered for interoperability from GIGABYTE Control Center
  (application analysis + USB captures) and is documented in [`docs/protocols/aorus-waterforce-x2.md`](docs/protocols/aorus-waterforce-x2.md).
  Only commands observed from GCC are sent; rigdeck never touches firmware updates.

## Adding hardware

Each device is a module in `rigdeck/modules/` implementing `Module`
([`base.py`](rigdeck/modules/base.py)): CLI subcommands, an optional service task, and an optional
GUI page (a QML file + a Qt backend object exposed under the module's id). The sidebar is built
from the registered modules. Shared QML components (metric cards, panels, device rows, curve
chart…) live in `rigdeck/gui/qml/RigDeck`.

## Development and releases

The full process is in [CONTRIBUTING.md](CONTRIBUTING.md). In short:


- Work happens on **`develop`**; `main` always matches the latest release.
- End each commit that changes something users notice with a trailer line written for them, e.g.
  `Changelog: GPU fans can now stop when the card is cool`. These lines become the release notes
  ([`CHANGELOG.md`](CHANGELOG.md)); preview them with `scripts/unreleased.sh`.
- `scripts/check.sh` runs the same validations as CI (GitHub Actions runs them on every push to
  `develop` and every pull request).
- **To release:** on `develop` run `scripts/bump-version.sh X.Y.Z`, commit and push, then open a
  pull request `develop → main`. Merging it publishes release `vX.Y.Z` with the changelog section
  as its notes, and the app's updater offers it to everyone.

## License

GPL-3.0-or-later. Icons from [Lucide](https://lucide.dev) (ISC). Not affiliated with GIGABYTE.
