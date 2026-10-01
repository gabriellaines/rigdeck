import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    readonly property var s: connectivity.state
    readonly property var net: s.network || []
    readonly property var adapters: s.adapters || []
    readonly property var bt: s.bluetooth || []

    Connections { target: connectivity; function onToast(m) { root.showToast(m) } }

    PageHeader {
        title: "Wi-Fi & Bluetooth"
        subtitle: "Connections and pairing are managed in your desktop's settings"
        status: page.net.some(d => d.state === "connected") ? "Online" : connectivity.loaded ? "Offline" : "Looking…"
        tone: page.net.some(d => d.state === "connected") ? theme.live : theme.warning
    }

    Banner {
        visible: connectivity.loaded && !page.s.nmcli
        text: "Network status needs NetworkManager (nmcli), which this system doesn't use."
    }
    Banner {
        visible: (page.s.error || "") !== ""
        tone: "error"
        text: page.s.error || ""
    }

    // ---- network adapters
    Panel {
        Layout.fillWidth: true
        visible: page.net.length > 0
        title: "Network"
        headerExtra: Button { visible: connectivity.canOpenSettings; text: "Network settings"
                              onClicked: connectivity.openSettings("network") }
        padding: 0
        Repeater {
            model: page.net
            DeviceRow {
                readonly property var w: modelData.wifi || null
                showDivider: index > 0
                icon: modelData.type === "wifi" ? (w ? (w.signal >= 67 ? "wifi" : w.signal >= 34 ? "wifi-high" : "wifi-low") : "wifi-off")
                                                : "ethernet-port"
                title: modelData.hardware || modelData.device
                detail: [modelData.type === "wifi" ? "Wi-Fi" : "Ethernet", modelData.device,
                         w ? w.ssid + " · " + w.band + " · " + w.rate + " · " + w.security
                           : (modelData.speed ? modelData.speed + " Mbit/s" : ""),
                         modelData.driver ? "driver " + modelData.driver : ""].filter(t => t).join(" · ")
                status: w && w.signal !== null ? w.signal + "% signal"
                        : modelData.state === "connected" ? "Connected" : modelData.state
                tone: modelData.state === "connected" ? theme.live : theme.muted
            }
        }
    }

    // ---- Bluetooth
    Repeater {
        model: page.adapters
        Panel {
            id: ad
            readonly property var a: modelData
            Layout.fillWidth: true
            title: "Bluetooth"
            subtitle: (a.hardware || a.path) + " · visible to others as \"" + a.name + "\" · " + a.address
            headerExtra: Button { visible: connectivity.canOpenSettings; text: "Pair a device"
                                  onClicked: connectivity.openSettings("bluetooth") }
            SettingRow {
                title: "Bluetooth"
                description: ad.a.powered ? "On" : "Off — devices can't connect"
                Toggle { checked: ad.a.powered; Accessible.name: "Bluetooth"
                         onToggled: connectivity.setBluetooth(ad.a.path, checked) }
            }
            Label {
                visible: page.bt.filter(d => d.adapter === ad.a.path).length === 0
                text: "No paired devices yet."
                color: theme.muted; font.pixelSize: 12
            }
            Repeater {
                model: page.bt.filter(d => d.adapter === ad.a.path)
                KeyValue {
                    key: modelData.name
                    value: (modelData.connected ? "Connected" : "Paired, not connected")
                           + (modelData.battery !== null && modelData.battery !== undefined ? " · " + modelData.battery + "% battery" : "")
                }
            }
        }
    }
    Banner {
        visible: connectivity.loaded && page.adapters.length === 0
        tone: "info"
        text: "No Bluetooth adapter found."
    }
}
