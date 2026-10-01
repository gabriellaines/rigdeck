#!/usr/bin/env bash
# rigdeck web installer — downloads the latest release and runs its install.sh.
#
#   curl -fsSL https://raw.githubusercontent.com/gabriellaines/rigdeck/main/get.sh | bash
#   curl -fsSL …/get.sh | bash -s -- --gui          # options are passed to install.sh
#   curl -fsSL …/get.sh | bash -s -- --uninstall
#
# RIGDECK_VERSION=v0.3.0 picks a specific release instead of the latest.
set -euo pipefail

REPO=gabriellaines/rigdeck

# Everything lives in a function that runs on the last line, so a download cut off
# halfway can't execute a partial script.
main() {
    bold() { printf '\033[1m%s\033[0m\n' "$*"; }
    die()  { printf '\033[31merror: %s\033[0m\n' "$*" >&2; exit 1; }

    [ "$(id -u)" -ne 0 ] || die "run this as your normal user, not with sudo (it asks for your password when needed)"
    for tool in curl tar; do
        command -v "$tool" >/dev/null || die "'$tool' is needed — install it with your package manager and try again"
    done

    local tag=${RIGDECK_VERSION:-}
    if [ -z "$tag" ]; then
        # github.com/…/releases/latest redirects to …/releases/tag/<tag>; no API token or jq needed
        local url
        url=$(curl -fsSLo /dev/null -w '%{url_effective}' "https://github.com/$REPO/releases/latest") \
            || die "could not reach GitHub — check your internet connection"
        tag=${url##*/tag/}
        [ "$tag" != "$url" ] && [ -n "$tag" ] || die "no rigdeck release found on GitHub"
    fi

    tmp=$(mktemp -d)  # global: the EXIT trap runs after main() returns
    trap 'rm -rf "$tmp"' EXIT
    bold "Downloading rigdeck ${tag#v}…"
    curl -fsSL -o "$tmp/rigdeck.tar.gz" "https://github.com/$REPO/archive/refs/tags/$tag.tar.gz" 2>/dev/null \
        || die "could not download rigdeck $tag — check the version and your internet connection"
    tar -xzf "$tmp/rigdeck.tar.gz" -C "$tmp" --strip-components=1 || die "the download is damaged — try again"
    [ -f "$tmp/install.sh" ] || die "the release archive has no install.sh"

    # When piped into bash, our stdin is the script itself; give the installer the keyboard.
    if [ -t 0 ] || ! (exec </dev/tty) 2>/dev/null; then
        bash "$tmp/install.sh" "$@"
    else
        bash "$tmp/install.sh" "$@" </dev/tty
    fi
}

main "$@"
