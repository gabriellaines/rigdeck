"""Connectivity module: nmcli and BlueZ parsing."""
from rigdeck.modules import connectivity as c

DEVICES = """enp6s0:ethernet:connected:Wired connection 1
wlan0:wifi:connected:SobralLaines
docker0:bridge:connected (externally):docker0
veth45e93a2:ethernet:unmanaged:
lo:loopback:connected (externally):lo"""

WIFI = """ :Neighbour\\:5G:40:5745 MHz:540 Mbit/s:WPA2
*:SobralLaines:92:5220 MHz:270 Mbit/s:WPA2
 :Other:20:2437 MHz:65 Mbit/s:"""


def test_physical_devices_only(monkeypatch):
    monkeypatch.setattr(c.os.path, "exists", lambda p: "veth" not in p)   # veth has no device link
    assert [(d["device"], d["type"]) for d in c.parse_devices(DEVICES)] == [("enp6s0", "ethernet"), ("wlan0", "wifi")]


def test_wifi_in_use_and_escaped_colons():
    w = c.parse_wifi(WIFI)
    assert w == {"ssid": "SobralLaines", "signal": 92, "band": "5 GHz", "rate": "270 Mbit/s", "security": "WPA2"}
    assert c._split("x:Neighbour\\:5G:40") == ["x", "Neighbour:5G", "40"]


def test_bluez_adapters_and_own_devices():
    data = {
        "/org/bluez/hci0": {"org.bluez.Adapter1": {"Alias": {"data": "waterforce"}, "Address": {"data": "8C:86:DD:71:4F:4B"},
                                                   "Powered": {"data": True}}},
        "/org/bluez/hci0/dev_AA": {"org.bluez.Device1": {"Alias": {"data": "Earbuds"}, "Paired": {"data": True},
                                                         "Connected": {"data": True}, "Adapter": {"data": "/org/bluez/hci0"}},
                                   "org.bluez.Battery1": {"Percentage": {"data": 80}}},
        "/org/bluez/hci0/dev_BB": {"org.bluez.Device1": {"Alias": {"data": "Someone's phone"}, "Paired": {"data": False},
                                                         "Connected": {"data": False}}},
    }
    adapters, devices = c.parse_bluez(data)
    assert adapters == [{"path": "/org/bluez/hci0", "name": "waterforce", "address": "8C:86:DD:71:4F:4B", "powered": True}]
    assert [(d["name"], d["connected"], d["battery"]) for d in devices] == [("Earbuds", True, 80)]   # neighbours skipped
