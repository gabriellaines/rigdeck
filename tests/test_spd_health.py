"""SPD decoding and SMART parsing, with values read from this project's test PC."""
from rigdeck import disk_health, spd


def ballistix() -> bytes:
    """The fields of a Crucial Ballistix BL16G32C16U4B (DDR4-3200 CL16, 16 GB, 2 ranks)."""
    b = bytearray(512)
    b[2], b[3], b[4], b[12], b[13] = 0x0C, 0x02, 0x85, 0x09, 0x03
    b[18], b[125] = 8, 0xC1                         # 1.000 ns - 63 ps -> 2133
    b[320], b[321] = 0x05, 0x9B                     # JEP106 bank 6, code 0x9B
    b[329:349] = b"BL16G32C16U4B".ljust(20)
    b[384:386] = b"\x0c\x4a"                        # XMP 2.0
    b[393], b[396], b[431] = 0xA3, 5, 0             # 1.35 V, 0.625 ns -> 3200
    return bytes(b)


def test_ddr4_module():
    m = spd.decode(ballistix())
    assert m == {"type": "DDR4", "form": "UDIMM", "sizeGB": 16, "ranks": 2, "jedecMTs": 2133, "maker": "Crucial",
                 "part": "BL16G32C16U4B", "xmpMTs": 3200, "xmpVolts": 1.35}


def test_speed_bins_and_makers():
    assert spd.mts_from_period(6, 0) == 2666                     # 0.750 ns
    assert spd.maker(0x80, 0x2C) == "Micron" and spd.maker(0x01, 0x98) == "Kingston"
    assert spd.maker(0x7F, 0x01) == "JEDEC 128/0x01"


def test_nvme_health():
    ctrl = {"SmartTemperature": 318, "SmartPowerOnHours": 25166, "SmartSelftestStatus": "success",
            "SmartCriticalWarning": []}
    attrs = {"avail_spare": {"data": 100}, "spare_thresh": {"data": 32}, "percent_used": {"data": 8},
             "total_data_written": {"data": 131287046144000}, "media_errors": {"data": 0},
             "unsafe_shutdowns": {"data": 193}}
    h = disk_health.parse_nvme(ctrl, attrs)
    assert (h["ok"], h["temperature"], h["wear"], h["written"]) == (True, 45, 8, 131287046144000)
    worn = disk_health.parse_nvme(ctrl, {**attrs, "avail_spare": {"data": 20}})
    assert not worn["ok"]                                        # spare below the drive's own threshold


def test_ata_health():
    ata = {"SmartSupported": True, "SmartEnabled": True, "SmartFailing": False, "SmartTemperature": 309.0,
           "SmartPowerOnSeconds": 18129600, "SmartNumBadSectors": 0, "SmartNumAttributesFailing": 0}
    h = disk_health.parse_ata(ata)
    assert (h["ok"], h["temperature"], h["powerOnHours"]) == (True, 36, 5036)
    assert not disk_health.parse_ata({**ata, "SmartNumBadSectors": 3})["ok"]
