"""Keyboard module: HID++ reply handling and brightness limits."""
import pytest

from rigdeck.modules import keyboard
from rigdeck.modules.keyboard import hidpp


class FakeKeyboard(hidpp.Device):
    """Answers HID++ calls from a table instead of a device."""

    def __init__(self, node="/dev/null"):
        self._index = {hidpp.ROOT: 0}
        self.brightness = 100
        self.calls = []

    def close(self):
        pass

    def call(self, index, function, params=b""):
        self.calls.append((index, function, params))
        if index == 0:   # root: feature id -> index
            fid = int.from_bytes(params[:2], "big")
            return bytes([{hidpp.DEVICE_NAME: 3, hidpp.FW_VERSION: 2, hidpp.BRIGHTNESS: 11}.get(fid, 0)]) + bytes(15)
        if index == 3:
            name = b"PRO X RAPID"
            return bytes([len(name)]) + bytes(15) if function == 0 else name[params[0]:params[0] + 16].ljust(16, b"\0")
        if index == 2:
            return bytes([1]) + bytes(15) if function == 0 else bytes([0]) + b"U1\0" + bytes([0x70, 0x04, 0x00, 0x20]) + bytes(8)
        if index == 11:
            if function == 0:
                return bytes([0, 100, 5, 3, 0, 0]) + bytes(10)
            if function == 1:
                return self.brightness.to_bytes(2, "big") + bytes(14)
            if function == 2:
                self.brightness = int.from_bytes(params[:2], "big")
                return bytes(16)
        raise hidpp.HidppError("keyboard refused the request (invalid function)")


@pytest.fixture
def kb(monkeypatch):
    k = FakeKeyboard()
    monkeypatch.setattr(hidpp, "Device", lambda node: k)
    return k


DEV = {"node": "/dev/hidraw5", "pid": 0xC35B, "model": "Logitech G PRO X TKL RAPID"}


def test_reads_name_firmware_brightness(kb):
    s = keyboard.read_state(DEV)
    assert s["deviceName"] == "PRO X RAPID"
    assert s["firmware"] == "U1 70.04 build 0020"
    assert (s["brightness"], s["brightnessMin"], s["brightnessMax"]) == (100, 0, 100)


def test_set_brightness_in_range(kb):
    keyboard.set_brightness(DEV, 37)
    assert kb.brightness == 37
    with pytest.raises(keyboard.RigdeckError):
        keyboard.set_brightness(DEV, 101)
    assert kb.brightness == 37


def test_unsupported_feature_is_reported(kb):
    with pytest.raises(hidpp.HidppError, match="not supported"):
        kb.feature(0x1B08, 0)       # unknown feature id -> index 0 -> refused before sending
