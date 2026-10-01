"""Motherboard module: which sensors are shown, fan header states (fake sysfs from an NCT6798)."""
from rigdeck.modules import motherboard

FILES = {
    "name": "nct6798",
    "temp1_input": "40000", "temp1_label": "SYSTIN",
    "temp2_input": "32500", "temp2_label": "CPUTIN",
    "temp3_input": "78000", "temp3_label": "AUXTIN0",          # unconnected input: garbage
    "temp8_input": "32000", "temp8_label": "PECI Agent 0 Calibration",
    "temp10_input": "0", "temp10_label": "PCH_CHIP_TEMP",       # not available: reads 0
    "temp13_input": "32400", "temp13_label": "TSI0_TEMP",
    "fan1_input": "0", "pwm1": "158", "pwm1_enable": "5",
    "fan2_input": "1200", "pwm2": "128", "pwm2_enable": "1",
    "fan7_input": "0", "pwm7": "255", "pwm7_enable": "0",
}


def test_reads_board_sensors(tmp_path, monkeypatch):
    for name, content in FILES.items():
        (tmp_path / name).write_text(content)
    monkeypatch.setattr(motherboard, "sensor_dir", lambda: str(tmp_path))
    s = motherboard.read()
    assert s["chip"] == "nct6798"
    assert [(t["label"], t["c"]) for t in s["temps"]] == [
        ("Motherboard", 40.0), ("CPU socket", 32.5), ("CPU (reported to the board)", 32.4)]
    assert [(f["n"], f["connected"], f["duty"], f["mode"]) for f in s["fans"]] == [
        (1, False, 62, "BIOS curve"), (2, True, 50, "Manual"), (7, False, 100, "Full speed")]


def test_no_sensor_driver(monkeypatch):
    monkeypatch.setattr(motherboard, "sensor_dir", lambda: None)
    s = motherboard.read()
    assert s["chip"] == "" and s["temps"] == [] and s["fans"] == []
