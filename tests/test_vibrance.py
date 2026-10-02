"""Colour vibrance: profile maths, kscreen-doctor parsing, and old-profile cleanup."""
import os

import pytest

from rigdeck import config, vibrance

DOCTOR = """\x1b[01;32mOutput: \x1b[0;0m1 DP-3 3e2b5b5d
\tenabled
\tconnected
\tHDR: disabled
\tICC profile: /x/rigdeck-vibrance-DP-3-65.icc
\tColor profile source: ICC
Output: 2 DP-2 247b2904
\tenabled
\tconnected
\tHDR: enabled
\tICC profile: none
\tColor profile source: sRGB
Output: 3 HDMI-A-1 0000
\tdisabled
\tdisconnected
"""


def test_neutral_profile_is_plain_srgb():
    expected = vibrance._mul(vibrance.BRADFORD_D65_D50, vibrance.SRGB)
    for c, col in enumerate(vibrance.colorants(vibrance.NEUTRAL)):
        assert col == pytest.approx([expected[r][c] for r in range(3)], abs=1e-9)


def test_profile_header_size_matches():
    p = vibrance.profile(75, "test")
    assert int.from_bytes(p[:4], "big") == len(p) and p[36:40] == b"acsp"


def test_outputs_parses_kscreen_doctor(monkeypatch):
    monkeypatch.setattr(vibrance, "_doctor", lambda *a: DOCTOR)
    outs = vibrance.outputs()
    assert [o["name"] for o in outs] == ["DP-3", "DP-2"]          # disconnected HDMI left out
    assert outs[0]["level"] == 65 and not outs[0]["hdr"]
    assert outs[1]["level"] == vibrance.NEUTRAL and outs[1]["hdr"] and outs[1]["icc"] == ""


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(vibrance, "DIR", str(tmp_path / "vibrance"))
    monkeypatch.setattr(config, "PATH", str(tmp_path / "config.toml"))
    os.makedirs(vibrance.DIR)
    for n in ("DP-2-60", "DP-2-65", "DP-2-1-80", "DP-3-90"):
        open(os.path.join(vibrance.DIR, f"rigdeck-vibrance-{n}.icc"), "wb").close()
    open(os.path.join(vibrance.DIR, "notes.txt"), "w").close()
    return tmp_path


def test_apply_removes_only_that_monitors_old_profiles(sandbox, monkeypatch):
    calls = []
    monkeypatch.setattr(vibrance, "outputs", lambda: [{"name": "DP-2", "hdr": False, "icc": "",
                                                        "source": "sRGB", "level": 50}])
    monkeypatch.setattr(vibrance, "_doctor", lambda *a: calls.append(a) or "")
    vibrance.apply("DP-2", 75)
    assert sorted(os.listdir(vibrance.DIR)) == ["notes.txt", "rigdeck-vibrance-DP-2-1-80.icc",
                                                 "rigdeck-vibrance-DP-2-75.icc", "rigdeck-vibrance-DP-3-90.icc"]
    vibrance.apply("DP-2", vibrance.NEUTRAL)
    assert calls[-1] == ("output.DP-2.colorProfileSource.sRGB",)
    assert "rigdeck-vibrance-DP-2-75.icc" not in os.listdir(vibrance.DIR)


def test_failed_apply_keeps_old_profiles(sandbox, monkeypatch):
    monkeypatch.setattr(vibrance, "outputs", lambda: [{"name": "DP-2", "hdr": False, "icc": "",
                                                        "source": "sRGB", "level": 50}])

    def fail(*a):
        raise vibrance.VibranceError("kscreen-doctor failed")
    monkeypatch.setattr(vibrance, "_doctor", fail)
    with pytest.raises(vibrance.VibranceError):
        vibrance.apply("DP-2", 75)
    assert "rigdeck-vibrance-DP-2-65.icc" in os.listdir(vibrance.DIR)
