"""Settings files: checking finds every mistake first; applying maps friendly names to devices."""
import json
import os

import pytest

from rigdeck import config, setupfile
from rigdeck.modules import keyboard, mouse

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "docs", "example-settings.json")


def test_the_documented_example_is_valid():
    with open(EXAMPLE) as f:
        setupfile.parse(f.read())


def test_every_problem_is_reported_with_where_it_is():
    with pytest.raises(setupfile.FileError) as e:
        setupfile.check({"mice": [{"dpis": [800], "pollingRate": 999}], "cooler": {"fan": "silent"},
                         "keyboard": {"profiles": {"1": {"color": "red", "actuation": 9}}}})
    p = e.value.problems
    assert "mice[0].dpis: unknown setting — did you mean 'dpi'?" in p
    assert any(x.startswith("mice[0].pollingRate: 999") for x in p)
    assert any(x.startswith("cooler.fan: 'silent'") for x in p)
    assert any(x.startswith("keyboard.profiles.1.color") for x in p)
    assert any(x.startswith("keyboard.profiles.1.actuation: 9") for x in p)


def test_not_json_says_where():
    with pytest.raises(setupfile.FileError, match="line 1, column"):
        setupfile.parse('{"mice": [')


def test_mouse_settings_become_device_changes(monkeypatch):
    calls = []
    monkeypatch.setattr(mouse, "connected", lambda: [{"node": "/dev/hidraw9", "pid": 0xF517, "model": "x11-ultra"}])
    monkeypatch.setattr(mouse, "change", lambda dev, ch: calls.append(ch))
    data = {"mice": [{"model": "attack shark x11 ultra", "dpi": [800, 1600], "stage": 2, "pollingRate": 4000,
                      "stageColors": ["#FF0000"], "light": {"effect": "breathing", "brightness": 6},
                      "liftOff": 0.7, "sensorMode": "High Performance", "angleTune": "off", "angleSnapping": True}]}
    setupfile.check(data)
    [r] = setupfile.apply(data)
    assert r["ok"], r
    assert calls[:3] == [{"stage": (0, 800)}, {"stage": (1, 1600)}, {"color": (0, "#ff0000")}]
    assert calls[3] == {"stageCount": 2, "currentStage": 1, "rate": 4000, "angleSnap": True, "lod": 3,
                        "sensorMode": 1, "angleTuneOn": False, "led": {"brightness": 6, "mode": 2}}


def test_a_mouse_that_is_not_connected_is_reported(monkeypatch):
    monkeypatch.setattr(mouse, "connected", lambda: [{"node": "n", "pid": 0xF509, "model": "pulsar"}])
    [r] = setupfile.apply({"mice": [{"model": "Attack Shark X11 Ultra", "dpi": [800]}]})
    assert not r["ok"] and "isn't connected" in r["message"]


def test_keyboard_profiles_are_saved_in_tenths_of_a_mm(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr(keyboard, "connected", lambda: [])
    monkeypatch.setattr(setupfile.servicectl, "reload", lambda: False)
    data = {"keyboard": {"profiles": {"2": {"actuation": 1.2, "rapidTrigger": "off",
                                             "keys": {"W": {"actuation": 0.8, "rapidTrigger": 0.3}},
                                             "color": "#00C8FF", "keyColors": {"W": "ff0000"}}}}}
    setupfile.check(data)
    [r] = setupfile.apply(data)
    assert r["ok"] and "when the keyboard is connected" in r["message"]
    w = next(k for k, v in keyboard.KEYS.items() if v == "W")
    assert keyboard.custom(2) == {"actuation": 12, "rapid": 0, "keys": {w: 8}, "rapidKeys": {w: 3}}
    assert keyboard.custom_lighting(2) == {"base": "00c8ff", "keys": {"W": "ff0000"}}
    assert setupfile._export_keyboard()["profiles"]["2"]["keys"]["W"] == {"actuation": 0.8, "rapidTrigger": 0.3}


def test_written_files_are_compact_and_read_back():
    data = {"rigdeck": 1, "mice": [{"dpi": [800, 1600], "light": {"effect": "steady", "brightness": 5}}]}
    text = setupfile.dumps(data)
    assert '"dpi": [800, 1600]' in text and '"light": {"effect": "steady", "brightness": 5}' in text
    assert json.loads(text) == data
