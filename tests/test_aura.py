"""ASUS Aura USB: zones from a real config table (TUF GAMING B550M-PLUS) and the packets sent."""
from rigdeck.modules.motherboard import aura

# Bytes 4..63 of the 0xB0 reply from firmware AULA3-AR42-0222
TABLE = bytes.fromhex("1e9f01010000" "783c00000000" + "00" * 15 + "050602" "01f400000000" + "00" * 24)


def test_zones_from_real_table():
    assert len(TABLE) == 60
    zones = aura.zones_from_table(TABLE)
    assert [(z["id"], z["channel"], z["first"], z["leds"], z["label"]) for z in zones] == [
        ("board", 0, 0, 5, "Board and 2 RGB headers"), ("argb1", 1, 5, 1, "ARGB header")]


class Recorder(aura.Aura):
    def __init__(self):
        self.sent = []

    def _send(self, *data):
        self.sent.append(bytes(data))


def test_static_color_on_the_board_zone():
    a = Recorder()
    board, _ = aura.zones_from_table(TABLE)
    a.set(board, "static", (0x10, 0x20, 0x30))
    gen1, effect, color, commit = a.sent
    assert gen1 == bytes([0x52, 0x53, 0x00, 0x01])
    assert effect == bytes([0x35, 0, 0, 0, aura.MODES["static"]])
    assert color[:4] == bytes([0x36, 0x00, 0x1F, 0x00])          # mask: LEDs 0..4
    assert color[4:4 + 15] == bytes([0x10, 0x20, 0x30] * 5)
    assert commit == bytes([0x3F, 0x55])


def test_argb_zone_uses_its_slot_and_off_sends_no_color():
    a = Recorder()
    _, argb = aura.zones_from_table(TABLE)
    a.set(argb, "breathing", (1, 2, 3), keep=False)
    assert a.sent[1] == bytes([0x35, 1, 0, 0, 2])
    assert a.sent[2][:3] == bytes([0x36, 0x00, 0x20])               # mask: LED 5
    assert a.sent[2][4 + 15:4 + 18] == bytes([1, 2, 3])
    assert len(a.sent) == 3                                       # keep=False: no commit
    a.sent.clear()
    a.set(argb, "off", (0, 0, 0))
    assert [p[0] for p in a.sent] == [0x52, 0x35, 0x3F]
