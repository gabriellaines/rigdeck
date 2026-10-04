import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    readonly property var s: network.state
    readonly property var all: s.adapters || []
    readonly property var tabTypes: ["ethernet", "wifi"].filter(t => all.some(a => a.type === t))
    readonly property string tab: tabTypes[Math.min(tabs.currentIndex, Math.max(0, tabTypes.length - 1))] || ""
    readonly property var shownAdapters: all.filter(a => a.type === tab)
    readonly property bool online: (s.internet || "") !== ""

    function speed(bps) {
        if (bps === undefined) return "—"
        const bits = bps * 8
        return bits >= 1e9 ? (bits / 1e9).toFixed(1) + " Gbit/s" : bits >= 1e6 ? (bits / 1e6).toFixed(1) + " Mbit/s"
             : bits >= 1e3 ? Math.round(bits / 1e3) + " kbit/s" : Math.round(bits) + " bit/s"
    }

    PageHeader {
        title: "Network"
        subtitle: page.online ? "Internet through " + (page.all.find(a => a.device === page.s.internet) || {}).hardware
                              : network.loaded ? "No internet connection" : ""
        status: page.online ? "Online" : network.loaded ? "Offline" : "Looking…"
        tone: page.online ? theme.live : theme.warning
    }

    Banner {
        visible: network.loaded && page.s.nmcli === false
        text: "Network details need NetworkManager (nmcli), which this system doesn't use."
    }
    Banner {
        visible: (page.s.error || "") !== ""
        tone: "error"
        text: page.s.error || ""
    }

    RowLayout {
        Layout.fillWidth: true
        visible: page.tabTypes.length > 0
        Segmented {
            id: tabs
            Layout.fillWidth: true
            model: page.tabTypes.map(t => t === "wifi" ? "Wi-Fi" : "Ethernet")
            currentIndex: 0
            chipHeight: 34
            onActivated: (i) => currentIndex = i
        }
        Button { visible: network.canOpenSettings; text: "Network settings"; onClicked: network.openSettings() }
    }

    // ---- one panel per adapter of the selected type
    Repeater {
        model: LiveModel { values: page.shownAdapters }
        Panel {
            id: ad
            readonly property var a: modelData
            readonly property var w: a.wifi || null
            readonly property var r: network.rates[a.device] || ({})
            Layout.fillWidth: true
            title: a.hardware || a.device
            subtitle: [a.device, "driver " + a.driver, a.device === page.s.internet ? "carries your internet" : ""]
                      .filter(t => t).join(" · ")

            GridLayout {
                Layout.fillWidth: true
                columns: page.pageWidth >= 900 ? 4 : 2
                columnSpacing: 12; rowSpacing: 12; uniformCellWidths: true
                MetricCard {
                    Layout.fillWidth: true
                    icon: ad.a.type === "wifi" ? "wifi" : "ethernet-port"
                    label: ad.a.type === "wifi" ? "Signal" : "Link"
                    value: ad.w ? ad.w.signal : ad.a.speed ? (ad.a.speed >= 1000 ? ad.a.speed / 1000 : ad.a.speed) : "—"
                    unit: ad.w ? "%" : ad.a.speed ? (ad.a.speed >= 1000 ? "Gbit/s" : "Mbit/s") : ""
                    detail: ad.w ? ad.w.ssid + " · " + ad.w.band : ad.a.state === "connected" ? "Cable connected"
                                                                                               : "Not connected"
                }
                MetricCard { Layout.fillWidth: true; icon: "arrow-down"; label: "Download"
                             value: page.speed(ad.r.rx).split(" ")[0]; unit: page.speed(ad.r.rx).split(" ")[1] || ""
                             detail: "right now" }
                MetricCard { Layout.fillWidth: true; icon: "arrow-up"; label: "Upload"
                             value: page.speed(ad.r.tx).split(" ")[0]; unit: page.speed(ad.r.tx).split(" ")[1] || ""
                             detail: "right now" }
                MetricCard { Layout.fillWidth: true; visible: ad.w !== null; icon: "activity"; label: "Link rate"
                             value: ad.w ? ad.w.rate.split(" ")[0] : "—"; unit: ad.w ? (ad.w.rate.split(" ")[1] || "") : ""
                             detail: ad.w ? ad.w.security : "" }
            }
            KeyValue { key: "State"; value: ad.a.state + (ad.a.connection ? " — " + ad.a.connection : "") }
            KeyValue { visible: ad.a.ipv4.length > 0; key: "IPv4"; value: ad.a.ipv4.join(", ") }
            KeyValue { visible: ad.a.ipv6.length > 0; key: "IPv6"; value: ad.a.ipv6.join(", ") }
            KeyValue { visible: ad.a.gateway !== ""; key: "Gateway"; value: ad.a.gateway }
            KeyValue { visible: ad.a.dns.length > 0; key: "DNS"; value: ad.a.dns.join(", ") }
            KeyValue { key: "MAC address"; value: ad.a.mac }
        }
    }

    // ---- nearby Wi-Fi networks
    Panel {
        Layout.fillWidth: true
        visible: page.tab === "wifi"
        title: "Nearby networks"
        subtitle: (page.s.networks || []).length ? "From the adapter's last scan; connect in Network settings"
                                                  : "None found in the last scan"
        padding: 0
        Repeater {
            model: LiveModel { values: (page.s.networks || []).slice(0, 12) }
            DeviceRow {
                showDivider: index > 0
                icon: modelData.signal >= 67 ? "wifi" : modelData.signal >= 34 ? "wifi-high" : "wifi-low"
                title: modelData.ssid
                detail: [modelData.band, modelData.security, modelData.rate].filter(t => t).join(" · ")
                status: (modelData.inUse ? "Connected · " : "") + modelData.signal + "%"
                tone: modelData.inUse ? theme.live : theme.muted
            }
        }
    }
}
