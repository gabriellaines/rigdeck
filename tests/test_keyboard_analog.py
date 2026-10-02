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
