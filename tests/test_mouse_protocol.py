"""Compx mouse protocol codecs, checked against bytes read from real mice (PROTOCOL.md)."""
import pytest

from rigdeck.modules.mouse import compx

# Stage records read off an X11 Ultra: (record, DPI)
STAGES = [("0f0f0037", 800), ("1f1f0017", 1600), ("3f3f00d7", 3200), ("6f6f0077", 5600),
          ("9f9f0017", 8000), ("a3a355ba", 42000), ("10100035", 850)]


@pytest.mark.parametrize("rec,dpi", STAGES)
def test_dpi_records_match_hardware(rec, dpi):
    assert compx.dpi_record(dpi).hex() == rec
    assert compx.dpi_value(bytes.fromhex(rec)) == dpi


def test_every_valid_dpi_round_trips():
    for dpi in list(range(50, 30001, 50)) + list(range(30100, 60001, 100)):
        assert compx.dpi_value(compx.dpi_record(dpi)) == dpi


def test_invalid_dpi_is_refused():
    for bad in (0, 75, 30150, 60100):
        with pytest.raises(ValueError):
            compx.dpi_record(bad)


def test_corrupt_record_reads_as_none():
    assert compx.dpi_value(bytes.fromhex("0f0f0038")) is None


def test_handshake_reply_checksum():
    # Observed reply: 08 | 01 00 00 00 08 4b b3 7c de 7c 0b 05 00 00 00 60
    body = bytes.fromhex("010000000" "84bb37cde7c0b05000000")
    assert compx.checksum(body) == 0x60


def test_pairs_and_colors():
    assert compx.pair(0x40) == bytes([0x40, 0x15])      # 8000 Hz, as stored
    assert compx.unpair(bytes([0x06, 0x4F])) == 6         # six DPI stages
    assert compx.unpair(bytes([0x06, 0x50])) is None
    assert compx.color_record((255, 255, 0)).hex() == "ffff0057"   # yellow gear
    assert compx.color_value(bytes.fromhex("ff000056")) == (255, 0, 0)


def test_packet_layout():
    p = compx.packet(compx.CMD_READ_FLASH, addr=0x00AC, length=10)
    assert p[0] == 8 and p[2:5] == bytes([0x00, 0xAC, 10]) and len(p) == 16
    assert p[15] == compx.checksum(p[:15])
