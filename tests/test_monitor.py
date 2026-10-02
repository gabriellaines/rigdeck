"""Monitor module: ddcutil output parsing (from real AOC / LG output) and the controls offered."""
from rigdeck.modules import monitor
from rigdeck.modules.monitor import ddc

DETECT = """Display 1
   I2C bus:          /dev/i2c-8
   DRM connector:    card1-DP-2
   drm_connector_id: 458
   Monitor:          AOC:27G2G4:

Display 2
   I2C bus:          /dev/i2c-9
   DRM connector:    card1-DP-3
   drm_connector_id: 465
   Monitor:          GSM:LG ULTRAGEAR:307AZDB1M074

Invalid display
   I2C bus:          /dev/i2c-4
"""

CAPS_LG = """Model: FALCON
VCP Features:
   Feature: 10 (Brightness)
   Feature: 12 (Contrast)
   Feature: 14 (Select color preset)
      Values:
         01: sRGB
         05: 6500 K
         0b: User 1
   Feature: 60 (Input Source)
      Values:
         01: VGA-1
         03: DVI-1
   Feature: 62 (Audio speaker volume)
   Feature: 8D (Audio Mute)
   Feature: FF (Manufacturer specific feature)
"""

VCP_AOC = "VCP 10 C 60 100\nVCP 12 C 60 100\nVCP 14 CNC x00 x0b x00 x05\nVCP 60 SNC x0f\nVCP 62 CNC x00 x64 x00 x32\nVCP 8D ERR\n"


def test_detect_skips_invalid_displays():
    ds = ddc.parse_detect(DETECT)
    assert [(d["bus"], d["connector"], d["mfg"], d["model"], d["serial"]) for d in ds] == [
        (8, "DP-2", "AOC", "27G2G4", ""), (9, "DP-3", "GSM", "LG ULTRAGEAR", "307AZDB1M074")]


def test_capabilities_with_value_lists():
    caps = ddc.parse_capabilities(CAPS_LG)
    assert set(caps) == {0x10, 0x12, 0x14, 0x60, 0x62, 0x8D, 0xFF}
    assert caps[0x60]["values"] == {1: "VGA-1", 3: "DVI-1"}
    assert caps[0x14]["values"][0x0B] == "User 1"


def test_getvcp_formats():
    v = ddc.parse_getvcp(VCP_AOC)
    assert v[0x10] == {"cur": 60, "max": 100}
    assert v[0x14] == {"cur": 5, "max": None}          # CNC preset: one of a list
    assert v[0x62] == {"cur": 50, "max": 100}          # CNC volume: continuous
    assert v[0x60] == {"cur": 0x0F, "max": None}
    assert 0x8D not in v                                # ERR = unsupported


def test_controls_follow_capabilities(monkeypatch):
    monkeypatch.setattr(ddc, "detect", lambda: ddc.parse_detect(DETECT)[1:])
    monkeypatch.setattr(ddc, "capabilities", lambda bus: ddc.parse_capabilities(CAPS_LG))
    monkeypatch.setattr(ddc, "get", lambda bus, codes: ddc.parse_getvcp(
        "VCP 10 C 40 100\nVCP 12 C 70 100\nVCP 14 SNC x0b\nVCP 60 SNC x03\nVCP 62 C 100 100\nVCP 8D SNC x02\n"))
    monitor._caps.clear()
    (lg,) = monitor.monitors()
    assert lg["name"] == "LG ULTRAGEAR"                     # brand already in the model name
    keys = [c["key"] for c in lg["controls"]]
    assert keys == ["brightness", "contrast", "preset", "volume", "mute", "input"]
    mute = next(c for c in lg["controls"] if c["key"] == "mute")
    assert mute["value"] == 0                               # 02 = not muted


def test_mute_is_written_as_mccs_values(monkeypatch):
    sent = []
    monkeypatch.setattr(ddc, "set", lambda bus, code, value: sent.append((code, value)))
    monitor.set_value(9, ddc.MUTE, 1)
    monitor.set_value(9, ddc.MUTE, 0)
    monitor.set_value(9, ddc.BRIGHTNESS, 55)
    assert sent == [(0x8D, 1), (0x8D, 2), (0x10, 55)]


def test_brand_names():
    assert monitor._name({"mfg": "AOC", "model": "27G2G4"}) == "AOC 27G2G4"
    assert monitor._name({"mfg": "DEL", "model": "U2723QE"}) == "Dell U2723QE"
