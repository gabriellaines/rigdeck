"""Network module: nmcli parsing (from this PC's Realtek Ethernet and TP-Link Wi-Fi)."""
from rigdeck.modules import network as n

DEVICES = """enp6s0:ethernet:connected:Wired connection 1
wlan0:wifi:disconnected:
docker0:bridge:connected (externally):docker0
veth45e93a2:ethernet:unmanaged:
lo:loopback:connected (externally):lo"""

WIFI = """ :Neighbour\\:5G:40:5745 MHz:540 Mbit/s:WPA2
*:SobralLaines:92:5220 MHz:270 Mbit/s:WPA2
 :SobralLaines:60:2437 MHz:130 Mbit/s:WPA2
 :Open café:20:2412 MHz:65 Mbit/s:
 ::30:2412 MHz:65 Mbit/s:WPA2"""

DETAILS = """GENERAL.HWADDR:B0:82:E2:4B:94:BB
IP4.ADDRESS[1]:192.168.68.61/22
IP4.GATEWAY:192.168.68.1
IP4.DNS[1]:187.50.250.115
IP4.DNS[2]:187.50.250.215
IP6.ADDRESS[1]:fe80::1dd3:e128:20d8:38c9/64"""


def test_physical_devices_only(monkeypatch):
    monkeypatch.setattr(n.os.path, "exists", lambda p: "veth" not in p)   # veth has no device link
    assert [(d["device"], d["type"], d["state"]) for d in n.parse_devices(DEVICES)] == [
        ("enp6s0", "ethernet", "connected"), ("wlan0", "wifi", "disconnected")]


def test_wifi_list_in_use_first_one_per_name():
    nets = n.parse_wifi_list(WIFI)
    assert [(x["ssid"], x["signal"], x["band"], x["inUse"]) for x in nets] == [
        ("SobralLaines", 92, "5 GHz", True), ("Neighbour:5G", 40, "5 GHz", False), ("Open café", 20, "2.4 GHz", False)]
    assert nets[2]["security"] == "open"                    # hidden networks (no name) are left out


def test_details():
    d = n.parse_details(DETAILS)
    assert d == {"mac": "B0:82:E2:4B:94:BB", "ipv4": ["192.168.68.61/22"], "ipv6": [],   # link-local IPv6 hidden
                 "gateway": "192.168.68.1", "dns": ["187.50.250.115", "187.50.250.215"]}
