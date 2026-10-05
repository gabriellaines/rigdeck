"""Resource sampling: cache sizes, and disk rates computed from /proc/diskstats deltas."""
from rigdeck import resources as r


def test_cache_sizes():
    assert r._size("32K") == 32768 and r._size("32768K") == 32 * 1024 ** 2 and r._size("1M") == 1024 ** 2


def test_disk_rates_from_counters(monkeypatch):
    stats = [{"nvme0n1": (0, 0, 0)}, {"nvme0n1": (1_000_000, 500_000, 250)}]   # bytes read, written, ms busy
    clock = iter([100.0, 101.0])                                                 # created, then +1 s
    monkeypatch.setattr(r, "_diskstats", lambda: stats.pop(0))
    monkeypatch.setattr(r, "_disks", lambda: ["nvme0n1"])
    monkeypatch.setattr(r, "_netdevs", lambda: [])
    monkeypatch.setattr(r.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(r.hwinfo, "gpu_cards", lambda: [])
    s = r.Sampler()
    d = s.sample()["disks"][0]
    assert (d["read"], d["write"]) == (1_000_000, 500_000)
    assert d["active"] == 25.0                     # 250 ms busy in 1000 ms


def test_system_activity(monkeypatch):
    files = {"/proc/loadavg": "0.18 0.32 0.46 1/2164 38375", "/proc/uptime": "93784.52 1400000.10"}
    monkeypatch.setattr(r, "_read", lambda path: files.get(path, ""))
    monkeypatch.setattr(r.os, "listdir", lambda path: ["1", "42", "self", "cpuinfo", "977"])
    assert r.system_activity() == {"processes": 3, "threads": 2164, "uptime": 93784}
