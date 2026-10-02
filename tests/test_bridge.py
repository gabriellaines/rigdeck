"""bridge.run_async: results and errors reach the main thread (needs PySide6)."""
import pytest

QtCore = pytest.importorskip("PySide6.QtCore")


def run(fn):
    from rigdeck.gui import bridge
    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    bridge.init()
    got = {}
    bridge.run_async(fn, lambda r: got.update(result=r), lambda e: got.update(error=e))
    loop = QtCore.QEventLoop()
    timer = QtCore.QTimer(singleShot=True, interval=50)
    timer.timeout.connect(lambda: loop.quit() if got else timer.start())
    timer.start()
    QtCore.QTimer.singleShot(3000, loop.quit)
    loop.exec()
    return got


def test_result_is_delivered():
    assert run(lambda: 42) == {"result": 42}


def test_error_is_delivered():
    # Regression: the exception used to be gone by the time the callback ran (NameError),
    # so pages never cleared their busy / polling flags after a failure.
    got = run(lambda: 1 / 0)
    assert isinstance(got.get("error"), ZeroDivisionError)
