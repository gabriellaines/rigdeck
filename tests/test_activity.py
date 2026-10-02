"""AdaptiveTimer: polling follows what's on screen (needs PySide6)."""
import pytest

QtCore = pytest.importorskip("PySide6.QtCore")


def test_intervals_follow_window_and_page():
    from rigdeck.gui.activity import AdaptiveTimer, activity
    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    a = activity()
    a.set(True, "overview")
    calls = []
    owner = QtCore.QObject()
    t = AdaptiveTimer(owner, lambda: calls.append(1), page="mouse", page_ms=10000, visible_ms=60000)
    assert t.isActive() and t.interval() == 60000 and calls == []      # another page: background rate

    a.set(True, "mouse")
    assert t.interval() == 10000 and calls == [1]                      # its page opened: refresh now

    a.set(False, "mouse")
    assert not t.isActive()                                            # minimised: no polling at all

    a.set(True, "mouse")
    assert t.isActive() and t.interval() == 10000 and calls == [1, 1]  # back: refresh right away

    page_only = AdaptiveTimer(owner, lambda: None, page="motherboard", page_ms=2000)
    assert not page_only.isActive()                                    # nothing to do off its page
    a.set(True, "overview")
    del app
