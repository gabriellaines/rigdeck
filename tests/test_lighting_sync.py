"""Lighting sync: the snapshot from before the first sync is what Restore puts back."""
import pytest

from rigdeck.modules import lighting as L


class Fake(L.Target):
    def __init__(self, tid, color="111111", fail=False):
        self.id = self.name = tid
        self.color, self.fail, self.here = color, fail, True

    def present(self):
        return self.here

    def snapshot(self):
        return {"color": self.color}

    def apply(self, color):
        if self.fail:
            raise OSError("unplugged")
        self.color = color
        return ""

    def restore(self, snap):
        self.color = snap["color"]
        return ""


@pytest.fixture
def devices(monkeypatch, tmp_path):
    kb, mouse = Fake("keyboard", "aaaaaa"), Fake("mouse", "bbbbbb")
    monkeypatch.setattr(L, "TARGETS", [kb, mouse])
    monkeypatch.setattr(L, "STATE", str(tmp_path / "sync.json"))
    return kb, mouse


def test_sync_twice_then_restore_goes_back_to_before_the_first(devices):
    kb, mouse = devices
    assert L.sync("#FF0000") == {}
    assert L.sync("00ff00") == {}
    assert (kb.color, mouse.color) == ("00ff00", "00ff00")
    assert L.status()["color"] == "00ff00" and L.status()["active"]
    assert L.restore() == ({}, [])
    assert (kb.color, mouse.color) == ("aaaaaa", "bbbbbb")
    assert not L.status()["active"]


def test_only_some_devices(devices):
    kb, mouse = devices
    L.sync("ff0000", only=["mouse"])
    assert (kb.color, mouse.color) == ("aaaaaa", "ff0000")
    assert [d["synced"] for d in L.status()["devices"]] == [False, True]


def test_a_device_missing_at_restore_keeps_its_snapshot(devices):
    kb, mouse = devices
    L.sync("ff0000")
    mouse.here = False
    errors, _ = L.restore()
    assert set(errors) == {"mouse"} and kb.color == "aaaaaa"
    mouse.here = True
    assert L.restore() == ({}, []) and mouse.color == "bbbbbb"


def test_bad_colour_is_refused(devices):
    with pytest.raises(ValueError):
        L.sync("red")


def test_a_device_that_fails_to_change_is_not_marked_synced(devices):
    kb, mouse = devices
    mouse.fail = True
    assert set(L.sync("ff0000")) == {"mouse"}
    assert [d["synced"] for d in L.status()["devices"]] == [True, False]
    mouse.fail = False
    L.sync("00ff00")                      # it joins later, with its lighting from before that
    assert L.restore() == ({}, []) and (kb.color, mouse.color) == ("aaaaaa", "bbbbbb")


def test_a_device_plugged_in_later_joins_the_sync(devices):
    kb, mouse = devices
    kb.here = False
    L.sync("ff0000")
    assert L.join_new() == {} and kb.color == "aaaaaa"      # still unplugged
    kb.here = True
    assert L.join_new() == {} and kb.color == "ff0000"
    assert L.restore() == ({}, []) and (kb.color, mouse.color) == ("aaaaaa", "bbbbbb")


def test_a_device_switched_off_stays_out_when_it_reconnects(devices):
    kb, mouse = devices
    L.sync("ff0000", only=["keyboard"])
    assert L.status()["skip"] == ["mouse"]
    mouse.here = False
    L.join_new()
    mouse.here = True
    L.join_new()
    assert mouse.color == "bbbbbb"
    L.sync("00ff00")                      # included again: it's synced and no longer skipped
    assert mouse.color == "00ff00" and L.status()["skip"] == []


def test_the_service_waits_a_minute_before_asking_a_failing_device_again(devices):
    kb, mouse = devices
    mouse.here = False
    L.sync("ff0000")
    mouse.here, mouse.fail = True, True
    task = L.LightingTask()
    task.tick(100.0)
    assert "mouse" in task.retry_at and not L.status()["devices"][1]["synced"]
    mouse.fail = False
    task.tick(130.0)                      # still waiting
    assert mouse.color == "bbbbbb"
    task.tick(161.0)
    assert mouse.color == "ff0000" and L.status()["devices"][1]["synced"]


def test_nothing_happens_without_a_sync(devices):
    kb, _ = devices
    L.LightingTask().tick(0.0)
    assert kb.color == "aaaaaa"
