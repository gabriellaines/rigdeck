#!/usr/bin/env bash
# rigdeck installer — works on any distro, installs into your home directory.
#
#   ./install.sh              install (asks whether you want the GUI)
#   ./install.sh --gui        install with the GUI, no questions
#   ./install.sh --cli-only   install the command-line tool only
#   ./install.sh --uninstall  remove rigdeck (keeps ~/.config/rigdeck)
#
# Root (sudo) is only used for system packages and the udev rule.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
APP_ID=io.github.rigdeck.RigDeck
PREFIX="$HOME/.local"
VENV="$PREFIX/share/rigdeck/venv"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UDEV_RULE=/etc/udev/rules.d/71-rigdeck.rules
GUI=ask
SUDO=${SUDO:-sudo}                         # the in-app updater sets SUDO=pkexec
UNATTENDED=${RIGDECK_UNATTENDED:-}         # no questions (used by the updater)

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31merror: %s\033[0m\n' "$*" >&2; exit 1; }

detect_pm() {
    if command -v pacman >/dev/null; then echo pacman
    elif command -v apt-get >/dev/null; then echo apt
    elif command -v dnf >/dev/null; then echo dnf
    elif command -v zypper >/dev/null; then echo zypper
    else echo unknown; fi
}

pkg_install() {  # pkg_install <role> ; role = core | gui
    local pm role=$1 pkgs
    pm=$(detect_pm)
    case "$pm:$role" in
        pacman:core) pkgs="python ffmpeg" ;;
        pacman:gui)  pkgs="pyside6 qt6-svg qt6-declarative" ;;
        apt:core)    pkgs="python3 python3-venv ffmpeg" ;;
        apt:gui)     pkgs="python3-pyside6.qtquick python3-pyside6.qtquickcontrols2 python3-pyside6.qtsvg qml6-module-qtquick-controls qml6-module-qtquick-layouts qml6-module-qtquick-dialogs qml6-module-qtquick-effects qml6-module-qtquick-templates" ;;
        dnf:core)    pkgs="python3 ffmpeg-free" ;;
        dnf:gui)     pkgs="python3-pyside6" ;;
        zypper:core) pkgs="python3 ffmpeg" ;;
        zypper:gui)  pkgs="python3-PySide6" ;;
        *) warn "Unknown package manager — install the $role dependencies yourself (see README)."; return 0 ;;
    esac
    bold "Installing $role dependencies: $pkgs"
    case "$pm" in
        pacman) $SUDO pacman -S --needed --noconfirm $pkgs ;;
        apt)    $SUDO apt-get install -y $pkgs ;;
        dnf)    $SUDO dnf install -y $pkgs ;;
        zypper) $SUDO zypper install -y $pkgs ;;
    esac
}

have_gui_deps() {
    python3 -c 'import PySide6.QtQuick, PySide6.QtQuickControls2, PySide6.QtSvg' 2>/dev/null
}

uninstall() {
    bold "Removing rigdeck"
    systemctl --user disable --now rigdeck.service 2>/dev/null || true
    rm -f "$UNIT_DIR/rigdeck.service" "$PREFIX/bin/rigdeck" "$PREFIX/bin/rigdeck-gui" \
          "$PREFIX/share/applications/$APP_ID.desktop" \
          "$PREFIX/share/icons/hicolor/scalable/apps/$APP_ID.svg"
    rm -rf "$PREFIX/share/rigdeck"
    systemctl --user daemon-reload || true
    if [ -f "$UDEV_RULE" ]; then
        $SUDO rm -f "$UDEV_RULE" && $SUDO udevadm control --reload
    fi
    bold "Done. Your settings in ~/.config/rigdeck were kept."
    exit 0
}

for arg in "$@"; do
    case "$arg" in
        --gui) GUI=yes ;;
        --cli-only) GUI=no ;;
        --uninstall) uninstall ;;
        -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) die "unknown option $arg (see --help)" ;;
    esac
done

[ "$(id -u)" -ne 0 ] || die "run as your normal user, not root (sudo is used where needed)"

# 1. dependencies -------------------------------------------------------------
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null \
   || ! command -v ffmpeg >/dev/null \
   || ! python3 -c 'import venv, ensurepip' 2>/dev/null; then
    pkg_install core
fi
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' || die "Python 3.11 or newer is required"

if [ "$GUI" = ask ]; then
    if have_gui_deps; then GUI=yes
    elif [ -n "$UNATTENDED" ]; then GUI=no
    else
        read -rp "Install the graphical app too (Qt 6 / PySide6)? [Y/n] " ans
        case "${ans:-y}" in [nN]*) GUI=no ;; *) GUI=yes ;; esac
    fi
fi
if [ "$GUI" = yes ] && ! have_gui_deps; then
    pkg_install gui
    have_gui_deps || warn "GUI libraries still not importable; rigdeck-gui will explain what's missing."
fi

# 1b. LACT — optional, powers GPU fan / power controls ------------------------------
if ! command -v lact >/dev/null; then
    if [ "$(detect_pm)" = pacman ] && [ -z "$UNATTENDED" ]; then
        read -rp "Install LACT for GPU fan and power controls? [Y/n] " ans
        case "${ans:-y}" in
            [nN]*) ;;
            *) $SUDO pacman -S --needed --noconfirm lact && $SUDO systemctl enable --now lactd.service ;;
        esac
    elif [ "$(detect_pm)" != pacman ]; then
        warn "Optional: install LACT for GPU controls — https://github.com/ilya-zlobintsev/LACT#installation"
    fi
fi

# 2. the app (own virtualenv; sees system PySide6) ---------------------------------
bold "Installing rigdeck into $VENV"
rm -rf "$VENV"
python3 -m venv --system-site-packages "$VENV"
rm -rf "$HERE/build" "$HERE"/*.egg-info   # stale build output would leak old files into the install
"$VENV/bin/pip" install --quiet --disable-pip-version-check "$HERE"
mkdir -p "$PREFIX/bin"
ln -sf "$VENV/bin/rigdeck" "$PREFIX/bin/rigdeck"
ln -sf "$VENV/bin/rigdeck-gui" "$PREFIX/bin/rigdeck-gui"

if [ "$GUI" = yes ]; then
    install -Dm644 "$HERE/data/$APP_ID.desktop" "$PREFIX/share/applications/$APP_ID.desktop"
    sed -i "s|^Exec=rigdeck-gui|Exec=$PREFIX/bin/rigdeck-gui|" "$PREFIX/share/applications/$APP_ID.desktop"
    install -Dm644 "$HERE/data/$APP_ID.svg" "$PREFIX/share/icons/hicolor/scalable/apps/$APP_ID.svg"
    command -v update-desktop-database >/dev/null && update-desktop-database "$PREFIX/share/applications" || true
fi

# 3. device access (udev, needs root once) ---------------------------------------
if ! cmp -s "$HERE/packaging/71-rigdeck.rules" "$UDEV_RULE" 2>/dev/null; then
    bold "Installing udev rule (lets your user access the cooler without root)"
    $SUDO install -Dm644 "$HERE/packaging/71-rigdeck.rules" "$UDEV_RULE"
    $SUDO udevadm control --reload
    $SUDO udevadm trigger --subsystem-match=hidraw
fi

# 4. background service (systemd --user) -------------------------------------------
mkdir -p "$UNIT_DIR"
sed "s|^ExecStart=/usr/bin/rigdeck|ExecStart=$PREFIX/bin/rigdeck|" "$HERE/packaging/rigdeck.service" \
    > "$UNIT_DIR/rigdeck.service"
systemctl --user daemon-reload
systemctl --user enable --now rigdeck.service
systemctl --user restart rigdeck.service

echo
bold "rigdeck is installed."
echo "  Terminal:  rigdeck info   |   rigdeck cooler status   |   rigdeck --help"
[ "$GUI" = yes ] && echo "  App:       rigdeck-gui  (or search 'rigdeck' in your app menu)"
[ "$GUI" = no ]  && echo "  App:       not installed — run ./install.sh --gui any time to add it"
case ":$PATH:" in *":$PREFIX/bin:"*) ;; *) warn "Add $PREFIX/bin to your PATH to use the commands." ;; esac
