"""Headset module: HeadsetControl output parsing, device addressing, re-applying settings."""
import json

import pytest

from rigdeck.modules import headset
from rigdeck.modules.headset import hc

HYPERX = {"status": "success", "device": "HyperX Cloud II Wireless (Kingston)", "id_vendor": "0x0951",
          "id_product": "0x1718", "capabilities": ["CAP_SIDETONE", "CAP_BATTERY_STATUS", "CAP_INACTIVE_TIME"],
          "battery": {"status": "BATTERY_AVAILABLE", "level": 31}}
OFF = {**HYPERX, "status": "partial", "battery": {"status": "BATTERY_UNAVAILABLE", "level": -1}}
MOCK = {**HYPERX, "device": "HeadsetControl Test device", "id_vendor": "0xf00b", "id_product": "0xa00c"}


def fake_run(monkeypatch, devices, actions=()):
    calls = []

    def run(*args, timeout=15):
        calls.append(args)
        return json.dumps({"devices": devices, "actions": list(actions)})
    monkeypatch.setattr(hc, "_run", run)
    return calls


def test_status_parses_battery_and_skips_mock(monkeypatch):
    fake_run(monkeypatch, [MOCK, HYPERX])
    st = hc.status()
    assert st["id"] == "0951:1718" and st["on"] and st["battery"] == 31
    assert st["caps"] == ["sidetone", "battery", "inactive_time"]
    assert st["sidetone_on_off"]


def test_headset_off_is_found_but_not_on(monkeypatch):
    fake_run(monkeypatch, [OFF])
    st = hc.status()
    assert st is not None and not st["on"] and st["battery"] is None


def test_writes_address_one_device_in_hex(monkeypatch):
    # Without 0x, HeadsetControl reads the IDs as decimal and silently matches nothing.
    calls = fake_run(monkeypatch, [HYPERX], [{"capability": "CAP_SIDETONE", "status": "success"}])
    hc.apply("0951:1718", {"sidetone": 128})
    assert calls[0][:2] == ("--device", "0x0951:0x1718")
    assert ("--sidetone", "128") == calls[0][4:6]


def test_failed_action_raises(monkeypatch):
    fake_run(monkeypatch, [HYPERX], [{"capability": "CAP_INACTIVE_TIME", "status": "failure",
                                      "error_message": "Operation timed out"}])
    with pytest.raises(hc.HeadsetError, match="inactive_time: Operation timed out"):
        hc.apply("0951:1718", {"inactive_time": 30})


def test_service_reapplies_when_headset_turns_on(monkeypatch):
    states = iter([OFF, HYPERX, HYPERX, OFF, HYPERX])
    applied = []
    monkeypatch.setattr(hc, "status", lambda: hc._device(next(states)))
    monkeypatch.setattr(hc, "apply", lambda did, s: applied.append(s))
    task = headset.HeadsetTask()
    task.reload({"headset": {"sidetone": 0, "inactive_time": 30, "lights": 1}})
    for t in range(5):
        task.tick(t)
    # applied on each off → on transition only; lights skipped (not a capability of this headset)
    assert applied == [{"sidetone": 0, "inactive_time": 30}] * 2
