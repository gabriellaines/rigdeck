"""Check GitHub for a newer release and, for install.sh installs, update in place.

Packaged installs (AUR, distro packages) are owned by the package manager, so for those
we only report that an update exists.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request

from . import REPO, __version__

API = f"https://api.github.com/repos/{REPO}/releases/latest"
USER_VENV = os.path.expanduser("~/.local/share/rigdeck/venv")


class UpdateError(Exception):
    pass


def parse_version(v: str) -> tuple[int, ...]:
    out = []
    for part in v.lstrip("vV").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


def install_method() -> str:
    """'installer' (install.sh, can self-update), 'package' (pacman/AUR…), or 'source'."""
    prefix = os.path.realpath(sys.prefix)
    if prefix == os.path.realpath(USER_VENV):
        return "installer"
    here = os.path.realpath(__file__)
    if "site-packages" not in here and "dist-packages" not in here:
        return "source"  # running from a git checkout
    if prefix.startswith("/usr"):
        return "package"
    return "source"


def latest_release(timeout: float = 8) -> dict:
    """{'version', 'tag', 'url', 'tarball', 'notes'} of the newest GitHub release."""
    req = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": f"rigdeck/{__version__}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise UpdateError("no releases published yet") from e
        raise UpdateError(f"GitHub answered {e.code}") from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise UpdateError(f"could not reach GitHub: {e}") from e
    tag = data.get("tag_name", "")
    return {"version": tag.lstrip("vV"), "tag": tag, "url": data.get("html_url"),
            "tarball": data.get("tarball_url"), "notes": data.get("body") or ""}


def check() -> dict:
    """Latest release plus whether it's newer and whether we can self-update."""
    rel = latest_release()
    rel["current"] = __version__
    rel["newer"] = parse_version(rel["version"]) > parse_version(__version__)
    rel["method"] = install_method()
    return rel


def apply(release: dict, log=print) -> None:
    """Download the release and run its install.sh (same options as the current install)."""
    if install_method() != "installer":
        raise UpdateError("this copy is managed by your package manager — update it there")
    if not release.get("tarball"):
        raise UpdateError("release has no source archive")
    with tempfile.TemporaryDirectory(prefix="rigdeck-update-") as td:
        archive = os.path.join(td, "src.tar.gz")
        log(f"Downloading rigdeck {release['version']}…")
        req = urllib.request.Request(release["tarball"], headers={"User-Agent": f"rigdeck/{__version__}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r, open(archive, "wb") as f:
                shutil.copyfileobj(r, f)
        except (urllib.error.URLError, TimeoutError) as e:
            raise UpdateError(f"download failed: {e}") from e
        with tarfile.open(archive) as t:
            t.extractall(td, filter="data")
        roots = [d for d in os.listdir(td) if os.path.isdir(os.path.join(td, d))]
        if len(roots) != 1 or not os.path.exists(os.path.join(td, roots[0], "install.sh")):
            raise UpdateError("unexpected archive layout")
        src = os.path.join(td, roots[0])
        gui = "--gui" if os.path.exists(os.path.join(USER_VENV, "bin", "rigdeck-gui")) and _has_gui() else "--cli-only"
        log("Installing…")
        env = dict(os.environ, RIGDECK_UNATTENDED="1")
        if not sys.stdin.isatty():
            env["SUDO"] = "pkexec"  # graphical password prompt when run from the app
        r = subprocess.run(["bash", os.path.join(src, "install.sh"), gui], cwd=src, env=env,
                           capture_output=True, text=True)
        for line in (r.stdout + r.stderr).splitlines():
            if line.strip():
                log(line.replace("\x1b[1m", "").replace("\x1b[0m", "").replace("\x1b[33m", "")
                    .replace("\x1b[31m", ""))
        if r.returncode != 0:
            raise UpdateError("installer failed (see log above)")
    log(f"Updated to {release['version']}.")


def _has_gui() -> bool:
    try:
        import PySide6.QtQuick  # noqa: F401
        return True
    except ImportError:
        return False
