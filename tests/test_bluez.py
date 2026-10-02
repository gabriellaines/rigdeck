"""Bluetooth devices from BlueZ, sorted into the categories that pick their page."""
from rigdeck import bluez

DATA = {
    "/org/bluez/hci0": {"org.bluez.Adapter1": {"Alias": {"data": "waterforce"}, "Address": {"data": "8C:86:DD:71:4F:4B"},
                                               "Powered": {"data": True}}},
    "/org/bluez/hci0/dev_AA": {"org.bluez.Device1": {"Alias": {"data": "Earbuds"}, "Icon": {"data": "audio-headset"},
                                                     "Paired": {"data": True}, "Connected": {"data": True},
                                                     "Adapter": {"data": "/org/bluez/hci0"}},
                               "org.bluez.Battery1": {"Percentage": {"data": 80}}},
    "/org/bluez/hci0/dev_CC": {"org.bluez.Device1": {"Alias": {"data": "MX Master"}, "Icon": {"data": "input-mouse"},
                                                     "Paired": {"data": True}, "Connected": {"data": False}}},
    "/org/bluez/hci0/dev_DD": {"org.bluez.Device1": {"Alias": {"data": "Pad"}, "Icon": {"data": "input-gaming"},
                                                     "Paired": {"data": True}, "Connected": {"data": True}}},
    "/org/bluez/hci0/dev_BB": {"org.bluez.Device1": {"Alias": {"data": "Someone's phone"}, "Icon": {"data": "phone"},
                                                     "Paired": {"data": False}, "Connected": {"data": False}}},
}


def test_adapters_and_your_devices():
    adapters, devices = bluez.parse(DATA)
    assert adapters == [{"path": "/org/bluez/hci0", "name": "waterforce", "address": "8C:86:DD:71:4F:4B", "powered": True}]
    # connected first, then by name; strangers' devices nearby are left out
    assert [(d["name"], d["category"], d["connected"], d["battery"]) for d in devices] == [
        ("Earbuds", "headset", True, 80), ("Pad", "controller", True, None), ("MX Master", "mouse", False, None)]
    assert devices[0]["icon"] == "headphones" and devices[1]["icon"] == "bluetooth"
