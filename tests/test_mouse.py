"""Mouse module: decoding a real settings dump, and the writes changes produce."""
import pytest

from rigdeck.modules import mouse
from rigdeck.modules.mouse import compx

# Settings area (first 192 bytes) read from a Pulsar Xlite V3 on its 4K receiver.
PULSAR = bytes.fromhex(
    "1045015400550055005501540f0f00370f0f00371f1f00173f3f00d73f3f00d73f3f00d73f3f00d73f3f00d7"
    "00ffff570000ff56ff00ff57ffffff58ffffff58ffffff58ffffff58ffffff58025380d502530154ff00ff57"
    "005580d5035200550101005301020052010400500108004c01100044020100520108004c0110004407000"
    "04e08040049040a0344000000550000005500000055000000550000005501ff00ff070946005500550154"
    "064f0055005500550055064f01540a4bffffff")


class FakeMouse:
    """Serves reads from a flash image and records writes."""

    def __init__(self, node, flash=PULSAR, info=None):
        self.flash = bytearray(flash) + bytearray(256 - len(flash))
        self.info = info or {"cid": 6, "mid": 15, "type": 1}
        self.writes = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def read(self, addr, n):
        return bytes(self.flash[addr:addr + n])

    def write(self, addr, data):
        self.writes.append((addr, bytes(data)))
        self.flash[addr:addr + len(data)] = data

    def write_pair(self, addr, v):
        self.write(addr, compx.pair(v))

    def battery(self):
        return {"level": 15, "charging": False, "mv": 3553}

    def backup(self):
        return bytes(self.flash)


DEV = {"node": "/dev/hidraw1", "pid": 0xF509, "model": "pulsar"}


@pytest.fixture
def fake(monkeypatch, tmp_path):
    m = FakeMouse(DEV["node"])
    monkeypatch.setattr(compx, "Mouse", lambda node: m)
    monkeypatch.setattr(mouse, "BACKUP_DIR", str(tmp_path))
    mouse._backed_up.clear()
    return m


def test_reads_real_pulsar_settings(fake):
    s = mouse.read_state(DEV)
    assert s["name"] == "Pulsar Xlite V3" and s["connection"] == "wireless"
    assert s["maxRate"] == 4000 and s["rate"] == 2000
    assert s["stageCount"] == 1 and s["currentStage"] == 0 and s["stages"][0] == 800
    assert s["led"] == {"mode": 2, "brightness": 5, "speed": 2, "on": True}
    assert s["motionSync"] and not s["angleSnap"] and not s["ripple"]
    assert s["colors"][0] == "#00ffff"


def test_asleep_when_reads_fail(monkeypatch):
    class Sleeping(FakeMouse):
        def read(self, addr, n):
            raise compx.MouseError("no answer")
    monkeypatch.setattr(compx, "Mouse", lambda node: Sleeping(node))
    s = mouse.read_state(DEV)
    assert s["asleep"] and s["name"] == "Pulsar Xlite V3"


def test_first_write_backs_up_then_writes_one_pair(fake, tmp_path):
    mouse.change(DEV, {"angleSnap": True})
    assert fake.writes == [(compx.OFF_ANGLE_SNAP, bytes([1, 0x54]))]
    assert len(list(tmp_path.glob("pulsar-*.bin"))) == 1


def test_rate_above_connection_limit_refused(fake):
    with pytest.raises(compx.MouseError, match="125, 250, 500, 1000, 2000, 4000"):
        mouse.change(DEV, {"rate": 8000})
    assert fake.writes == []


def test_dpi_limits_follow_the_sensor(fake):
    mouse.change(DEV, {"stage": (1, 26000)})
    assert fake.writes[-1] == (compx.OFF_DPI + 4, compx.dpi_record(26000))
    with pytest.raises(compx.MouseError):
        mouse.change(DEV, {"stage": (1, 30000)})     # PAW3395 tops out at 26000


def test_fewer_stages_moves_the_active_stage(fake):
    fake.flash[compx.OFF_STAGES:compx.OFF_STAGES + 2] = compx.pair(4)
    fake.flash[compx.OFF_CURRENT_STAGE:compx.OFF_CURRENT_STAGE + 2] = compx.pair(3)
    mouse.change(DEV, {"stageCount": 2})
    assert mouse.read_state(DEV)["currentStage"] == 1
