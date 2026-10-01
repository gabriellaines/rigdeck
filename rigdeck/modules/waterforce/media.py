"""Convert any GIF/video/image into the format the cooler's screen plays."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from ..base import RigdeckError

MAX_NAME_BYTES = 64


class MediaError(RigdeckError):
    pass


def target_name(src: str) -> str:
    name = os.path.splitext(os.path.basename(src))[0] + ".mkv"
    if len(name.encode("utf-8")) > MAX_NAME_BYTES:
        raise MediaError(f"file name too long: max {MAX_NAME_BYTES} bytes (UTF-8) including .mkv")
    return name


def convert(src: str) -> bytes:
    """Centre-crop to square, 320x320, 25 fps, H.264 in Matroska with GCC's exact encoder settings.

    The cooler's decoder can't handle B-frames (they show up as green, blocky garbage), so this
    mirrors GCC: Main profile, level 3.1, 1000 kbit/s, no B-frames, default preset.
    """
    if not shutil.which("ffmpeg"):
        raise MediaError("ffmpeg is not installed")
    vf = "crop='min(iw,ih)':'min(iw,ih)',scale=320:320:flags=lanczos,fps=25,format=yuv420p"
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "out.mkv")
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", vf, "-an",
                            "-c:v", "libx264", "-profile:v", "main", "-level", "3.1",
                            "-b:v", "1000k", "-bf", "0",
                            "-f", "matroska", out], capture_output=True, text=True)
        if r.returncode != 0:
            raise MediaError("ffmpeg failed: " + (r.stderr.strip().splitlines() or ["unknown error"])[-1])
        with open(out, "rb") as f:
            return f.read()
