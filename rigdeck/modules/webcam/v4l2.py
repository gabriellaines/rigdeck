"""Webcam controls through the kernel's V4L2 interface (pure Python ioctls, no v4l2-ctl).

Works for any UVC webcam: controls, their ranges and which are currently inactive (e.g. manual
focus while autofocus is on) all come from the driver.
"""
from __future__ import annotations

import ctypes
import errno
import fcntl
import glob
import os

from ..base import RigdeckError

BY_ID = "/dev/v4l/by-id"

# ioctl numbers: _IOWR('V', nr, size)
def _iowr(nr: int, size: int) -> int:
    return (3 << 30) | (size << 16) | (ord("V") << 8) | nr


class _QueryExtCtrl(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint32), ("type", ctypes.c_uint32), ("name", ctypes.c_char * 32),
                ("minimum", ctypes.c_int64), ("maximum", ctypes.c_int64), ("step", ctypes.c_uint64),
                ("default_value", ctypes.c_int64), ("flags", ctypes.c_uint32), ("elem_size", ctypes.c_uint32),
                ("elems", ctypes.c_uint32), ("nr_of_dims", ctypes.c_uint32), ("dims", ctypes.c_uint32 * 4),
                ("reserved", ctypes.c_uint32 * 32)]


class _QueryMenu(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint32), ("index", ctypes.c_uint32), ("name", ctypes.c_char * 32),
                ("reserved", ctypes.c_uint32)]


class _Control(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint32), ("value", ctypes.c_int32)]


class _Capability(ctypes.Structure):
    _fields_ = [("driver", ctypes.c_char * 16), ("card", ctypes.c_char * 32), ("bus_info", ctypes.c_char * 32),
                ("version", ctypes.c_uint32), ("capabilities", ctypes.c_uint32),
                ("device_caps", ctypes.c_uint32), ("reserved", ctypes.c_uint32 * 3)]


VIDIOC_QUERYCAP = (2 << 30) | (ctypes.sizeof(_Capability) << 16) | (ord("V") << 8) | 0  # _IOR
VIDIOC_G_CTRL = _iowr(27, ctypes.sizeof(_Control))
VIDIOC_S_CTRL = _iowr(28, ctypes.sizeof(_Control))
VIDIOC_QUERYMENU = _iowr(37, ctypes.sizeof(_QueryMenu))
VIDIOC_QUERY_EXT_CTRL = _iowr(103, ctypes.sizeof(_QueryExtCtrl))

CTRL_FLAG_NEXT_CTRL = 0x80000000
FLAG_DISABLED, FLAG_GRABBED, FLAG_READ_ONLY, FLAG_INACTIVE = 0x01, 0x02, 0x04, 0x10
TYPES = {1: "int", 2: "bool", 3: "menu", 9: "intmenu"}   # the ones a person adjusts
CAP_VIDEO_CAPTURE = 0x1


class WebcamError(RigdeckError):
    pass


class Camera:
    """One webcam, identified by its stable /dev/v4l/by-id name."""

    def __init__(self, by_id: str):
        self.by_id = by_id
        self.path = os.path.realpath(os.path.join(BY_ID, by_id))
        try:
            self.fd = os.open(self.path, os.O_RDWR | os.O_NONBLOCK)
        except OSError as e:
            if e.errno == errno.EACCES:
                raise WebcamError(f"no permission to open {self.path} — is your user in the 'video' group?") from e
            raise WebcamError(f"can't open {self.path}: {e.strerror}") from e
        cap = _Capability()
        fcntl.ioctl(self.fd, VIDIOC_QUERYCAP, cap)
        self.name = cap.card.decode(errors="replace").strip()
        self.driver = cap.driver.decode(errors="replace")

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def controls(self) -> list[dict]:
        """Adjustable controls with range, default, current value, menu entries and state."""
        out = []
        q = _QueryExtCtrl(id=CTRL_FLAG_NEXT_CTRL)
        while True:
            try:
                fcntl.ioctl(self.fd, VIDIOC_QUERY_EXT_CTRL, q)
            except OSError:
                break
            kind = TYPES.get(q.type)
            if kind and not q.flags & (FLAG_DISABLED | FLAG_READ_ONLY):
                c = {"id": q.id, "name": q.name.decode(errors="replace"), "key": _key(q.name),
                     "type": kind, "min": q.minimum, "max": q.maximum, "step": q.step or 1,
                     "default": q.default_value, "inactive": bool(q.flags & FLAG_INACTIVE),
                     "value": self.get(q.id)}
                if kind in ("menu", "intmenu"):
                    c["menu"] = self._menu(q)
                out.append(c)
            q = _QueryExtCtrl(id=q.id | CTRL_FLAG_NEXT_CTRL)
        return out

    def _menu(self, q) -> list[dict]:
        items = []
        for i in range(q.minimum, q.maximum + 1):
            m = _QueryMenu(id=q.id, index=i)
            try:
                fcntl.ioctl(self.fd, VIDIOC_QUERYMENU, m)
            except OSError:
                continue  # gaps are normal (the C920's exposure menu has only 1 and 3)
            label = (str(int.from_bytes(m.name[:8], "little", signed=True)) if q.type == 9
                     else m.name.decode(errors="replace"))
            items.append({"value": i, "label": label})
        return items

    def get(self, cid: int) -> int:
        c = _Control(id=cid)
        fcntl.ioctl(self.fd, VIDIOC_G_CTRL, c)
        return c.value

    def set(self, cid: int, value: int):
        try:
            fcntl.ioctl(self.fd, VIDIOC_S_CTRL, _Control(id=cid, value=int(value)))
        except OSError as e:
            raise WebcamError(f"the camera refused that setting ({e.strerror})") from e

    def apply(self, values: dict[str, int]) -> list[str]:
        """Set controls by key. Switches (auto modes) go first so the values they unlock take.
        Returns the keys that couldn't be set."""
        ctrls = {c["key"]: c for c in self.controls()}
        failed = [k for k in values if k not in ctrls]
        for switches in (True, False):
            if not switches:
                ctrls = {c["key"]: c for c in self.controls()}  # switches changed what's active
            for k, v in values.items():
                c = ctrls.get(k)
                if c is None or (c["type"] != "int") != switches:
                    continue
                if c["inactive"]:
                    continue  # e.g. manual focus while autofocus is on: the camera ignores it
                try:
                    self.set(c["id"], max(c["min"], min(c["max"], int(v))))
                except WebcamError:
                    failed.append(k)
        return failed


def _key(name: bytes) -> str:
    """'White Balance Temperature' -> 'white_balance_temperature' (stable config key)."""
    s = name.decode(errors="replace").lower()
    return "".join(ch if ch.isalnum() else "_" for ch in s).strip("_").replace("__", "_")


def cameras() -> list[str]:
    """by-id names of video capture nodes (index0 = the picture; index1 is metadata)."""
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(BY_ID, "*-video-index0")))


def config_key(by_id: str) -> str:
    """Stable, TOML-friendly key: 'usb-046d_HD_Pro_Webcam_C920_EF5696DF-video-index0' -> '046d_HD_Pro_Webcam_C920_EF5696DF'."""
    k = by_id.removeprefix("usb-").removesuffix("-video-index0")
    return "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in k)
