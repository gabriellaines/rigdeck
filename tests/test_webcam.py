"""Webcam module: control grouping, config keys, re-applying settings when a camera appears."""
from rigdeck.modules import webcam
from rigdeck.modules.webcam import v4l2

C920 = "usb-046d_HD_Pro_Webcam_C920_EF5696DF-video-index0"


def ctrl(key, type_="int", lo=0, hi=255, value=128, inactive=False, menu=()):
    return {"id": 1, "name": key.replace("_", " ").title(), "key": key, "type": type_, "min": lo, "max": hi,
            "step": 1, "default": value, "inactive": inactive, "value": value, "menu": list(menu)}


def test_key_from_driver_name():
    assert v4l2._key(b"White Balance, Automatic") == "white_balance_automatic"
    assert v4l2._key(b"Exposure Time, Absolute") == "exposure_time_absolute"


def test_config_key_is_stable_and_toml_friendly():
    assert webcam.v4l2.config_key(C920) == "046d_HD_Pro_Webcam_C920_EF5696DF"


def test_describe_groups_and_names():
    groups = webcam.describe([
        ctrl("brightness"),
        ctrl("backlight_compensation", lo=0, hi=1, value=0),
        ctrl("auto_exposure", "menu", 0, 3, 3, menu=[{"value": 1, "label": "Manual Mode"},
                                                     {"value": 3, "label": "Aperture Priority Mode"}]),
        ctrl("some_vendor_thing"),
    ])
    titles = [g["title"] for g in groups]
    assert titles == ["Image", "Exposure", "Other"]
    image = {c["key"]: c for c in groups[0]["controls"]}
    assert image["backlight_compensation"]["type"] == "bool"      # 0..1 int shown as a switch
    exposure = groups[1]["controls"][0]
    assert [m["label"] for m in exposure["menu"]] == ["Manual", "Automatic"]


def test_service_applies_saved_settings_when_camera_appears(monkeypatch):
    present = [[], [C920], [C920], [], [C920]]
    applied = []

    class FakeCam:
        name = "HD Pro Webcam C920"

        def __init__(self, by_id):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def apply(self, values):
            applied.append(dict(values))
            return []

    monkeypatch.setattr(v4l2, "cameras", lambda: present.pop(0))
    monkeypatch.setattr(v4l2, "Camera", FakeCam)
    task = webcam.WebcamTask()
    task.reload({"webcam": {"046d_HD_Pro_Webcam_C920_EF5696DF": {"brightness": 140}}})
    for t in range(5):
        task.tick(t)
    assert applied == [{"brightness": 140}] * 2   # each time it's plugged in, not every tick
