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
