"""PRO X TKL RAPID analog settings: parsing the onboard files (bytes as read from a real keyboard)."""
import zlib

from rigdeck.modules.keyboard import analog
from rigdeck.modules.keyboard.keymap import KEYS

DIRECTORY = bytes.fromhex(
    "81de21ba05" "0181014​06de8821b2108".replace("​", "") + "0281 01406d2f2898ef09".replace(" ", "")
    + "038101406d0036857 00a".replace(" ", "") + "041b0840bedfa3847b0b" + "071b0800ced59619fc10" + "ff")
PROFILE_1 = bytes.fromhex(
    "0001ffffffff00500052004f00460049004c0045005f004e0041004d00000000000000000000000000000100dcff0200"
    "0000000000000000000000000000000000000000000000000000000000000000000000080100010000000014000007ff"
    "ffffffffffffffffffffffffff"
)
PROFILE_3 = bytes(83) + bytes.fromhex("0801000100000000" "1401ffff0004") + b"\xff" * 12


def test_directory_entries():
    d = analog.parse_directory(DIRECTORY)
    assert sorted(d) == [1, 2, 3, 4, 7]
    assert d[1] == {"feature": 0x8101, "length": 0x6D, "crc": 0xE8821B21, "sector": 8}
    assert d[7] == {"feature": 0x1B08, "length": 0xCE, "crc": 0xD59619FC, "sector": 0x10}


def test_profile_analog_table():
    p = analog.parse_profile(PROFILE_1)
    assert len(PROFILE_1) == analog.PROFILE_LEN
    assert p == {"default": 20, "rapidTrigger": False, "refs": [(0, 7), None, None, None], "name": "PROFILE_NAM"}
    p3 = analog.parse_profile(PROFILE_3)
    assert p3["rapidTrigger"] and p3["refs"][:2] == [None, (0, 4)] and p3["name"] == ""


def test_pairs_and_summary():
    one_key = bytes.fromhex("0001" "1d0a")                     # G HUB: Rapid Trigger on W at 1.0 mm
    assert zlib.crc32(one_key) == 0x3F3F3029                  # the CRC G HUB sent with it
    assert analog.parse_pairs(one_key) == {0x1D: 10}
    values = {k: 20 for k in KEYS} | {0x1D: 10}
    assert analog.summary(values) == [("2.0 mm", [n for k, n in sorted(KEYS.items()) if k != 0x1D]), ("1.0 mm", ["W"])]


def test_keymap_covers_a_tkl():
    assert len(KEYS) == 87 and KEYS[0x1D] == "W" and KEYS[0x47] == "Fn"


class FakeKeyboard:
    """Records feature calls; answers fn 6 `0f` with the active profile."""

    def __init__(self, profile=1):
        self.calls, self.profile = [], profile

    def feature(self, feature, function, params=b""):
        self.calls.append((feature, function, bytes(params)))
        if (feature, function) == (0x8101, 6):
            return bytes([3, 0, self.profile]) + bytes(13)
        return bytes(16)


def test_apply_sends_g_hub_sequence():
    k = FakeKeyboard()
    analog.apply(k, 20, {0x1D: 10}, {})
    assert k.calls[0] == (0x1B08, 2, b"\x00")                       # Rapid Trigger switch off
    commits = [c for c in k.calls if c[1] == 9]
    assert [c[2][2] for c in commits] == [0, 1, 3]                  # files in G HUB's order
    assert commits[0][2] == bytes.fromhex("1b08000200 00ce f41d75cf".replace(" ", ""))  # = G HUB's bytes
    chunks = b"".join(c[2] for c in k.calls if c[1] == 3)
    assert chunks.startswith(bytes.fromhex("0066 0014 0114"))


def test_apply_rapid_trigger_turns_switch_on_and_validates():
    k = FakeKeyboard()
    analog.apply(k, 20, {}, {0x1E: 5})
    assert k.calls[0] == (0x1B08, 2, b"\x01")
    import pytest
    with pytest.raises(ValueError):
        analog.apply(FakeKeyboard(), 20, {0x1D: 0}, {})              # 0 mm is not a valid actuation
    with pytest.raises(ValueError):
        analog.apply(FakeKeyboard(), 41, {}, {})


def test_custom_settings_round_trip(tmp_path, monkeypatch):
    from rigdeck import config
    from rigdeck.modules import keyboard
    monkeypatch.setattr(config, "PATH", str(tmp_path / "config.toml"))
    assert keyboard.custom(1) is None
    s = {"actuation": 12, "rapid": 3, "keys": {0x45: 25}, "rapidKeys": {0x1D: 1}}
    keyboard.save_custom(2, s)
    assert keyboard.custom(2) == s and keyboard.custom(1) is None
    default, keys, rapid = keyboard.effective(s)
    assert default == 12 and keys == {0x45: 25} and len(rapid) == 87 and rapid[0x1D] == 1 and rapid[0x00] == 3
    keyboard.save_custom(2, None)
    assert keyboard.custom(2) is None


def test_one_keyboard_user_at_a_time(tmp_path, monkeypatch):
    import pytest
    from rigdeck.modules.keyboard import hidpp
    monkeypatch.setattr(hidpp, "LOCK", str(tmp_path / "kb.lock"))
    monkeypatch.setattr(hidpp, "LOCK_WAIT", 0.1)
    node = tmp_path / "hidraw"
    node.write_bytes(b"")
    with hidpp.Device(str(node)):
        with pytest.raises(hidpp.HidppError, match="busy"):
            hidpp.Device(str(node))
    hidpp.Device(str(node)).close()                                  # free again once closed


def test_lighting_paint_matches_g_hub():
    from rigdeck.modules.keyboard import lighting
    from rigdeck.modules.keyboard.keymap import zone
    assert (zone("A"), zone("W"), zone("Esc"), zone("Menu"), zone("LCtrl"), zone("Light")) == (1, 0x17, 0x26, 0x62, 0x68, 0x96)
    assert zone("Fn") is None
    k = FakeKeyboard()
    lighting.paint(k, "00ffff", {"W": "f82f25", "Fn": "ffffff"})
    ranges = [c[2] for c in k.calls if c[:2] == (0x8081, 5)]
    assert ranges[0] == bytes.fromhex("012e00ffff" "304f00ffff" "686f00ffff")      # G HUB's first fill message
    assert (0x8081, 1, bytes.fromhex("17f82f25")) in k.calls                         # Fn (no LED) skipped
    assert k.calls[-1] == (0x8081, 7, bytes(16))


def test_lighting_settings_round_trip(tmp_path, monkeypatch):
    import pytest
    from rigdeck import config
    from rigdeck.modules import keyboard
    monkeypatch.setattr(config, "PATH", str(tmp_path / "config.toml"))
    keyboard.save_lighting(1, {"base": "#202040", "keys": {"W": "FF0000", "Play": "00ff00"}})
    assert keyboard.custom_lighting(1) == {"base": "202040", "keys": {"W": "ff0000", "Play": "00ff00"}}
    with pytest.raises(ValueError):
        keyboard.save_lighting(1, {"base": "red", "keys": {}})
    keyboard.save_lighting(1, None)
    assert keyboard.custom_lighting(1) is None
