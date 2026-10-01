# rigdeck

A lightweight control panel for PC hardware on Linux — as a **command-line tool** and a
**modern GTK4 / libadwaita app**. Both are always installed; use whichever you like.

Built because vendor tools (GIGABYTE Control Center, …) are Windows-only, heavy, and
the only way to control some hardware.

| Device | Status |
|---|---|
| GIGABYTE **AORUS WATERFORCE X II** 240 / 360 / 360 ICE (USB `0414:7a5e`) | ✅ fans, pump, curves, RGB, LCD screen |
| GIGABYTE AORUS ELITE 240 / 360 AIOs (`0414:7a69`–`7a6c`) | 🧪 same protocol family, untested |
| AMD GPUs (fan modes, zero-RPM, clocks) | 🛠️ planned |
| System overview: CPU, GPU, Mesa / Vulkan / kernel driver, VBIOS | ✅ |

## Install

```sh
git clone https://github.com/gabriellaines/rigdeck
cd rigdeck
./install.sh            # asks whether you want the graphical app
```

Options: `./install.sh --gui`, `./install.sh --cli-only`, `./install.sh --uninstall`.
Changed your mind later? Run `./install.sh --gui` again to add the app.

The installer works on Arch / CachyOS / Manjaro, Fedora, Debian / Ubuntu and openSUSE. It:

1. installs Python ≥ 3.11 and ffmpeg (and GTK4 + libadwaita if you want the app) from your distro,
2. installs rigdeck into `~/.local` (its own virtualenv — nothing touches system Python),
3. adds a **udev rule** so your user can talk to the cooler without root (asks for `sudo` once),
4. enables the **`rigdeck` user service**.

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
rigdeck cooler screen list
```

Fan and pump modes are saved on the cooler itself. Lighting settings live in
`~/.config/rigdeck/config.toml` and are applied by the service.

## The app

`rigdeck-gui` (or **rigdeck** in your app menu). A sidebar lists your hardware; the cooler
page has **Cooling** (modes + drag-to-edit fan curve), **Lighting** and **Screen** tabs with
live RPM and temperature on top. Open a page directly with `rigdeck-gui --page cooler`.

## Notes

- **Virtual machines:** if you pass the cooler through to a Windows VM, Linux loses access
  while the VM runs; the service reconnects automatically when it's back.
- The protocol was reverse-engineered for interoperability from GIGABYTE Control Center
  (application analysis + USB captures) and is documented in [`docs/protocols/aorus-waterforce-x2.md`](docs/protocols/aorus-waterforce-x2.md).
  Only commands observed from GCC are sent; rigdeck never touches firmware updates.

## Adding hardware

Each device is a module in `rigdeck/modules/` implementing `Module`
([`base.py`](rigdeck/modules/base.py)): CLI subcommands, an optional service task and an
optional GUI page. Register it in `rigdeck/modules/__init__.py`.

## License

GPL-3.0-or-later. Not affiliated with GIGABYTE.
