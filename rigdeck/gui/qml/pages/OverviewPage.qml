import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    readonly property var info: system.info
    readonly property var live: system.live
    readonly property var gpuInfo: (info.gpus && info.gpus.length) ? info.gpus[0] : null
    readonly property var gpu: live.gpu || {}
    readonly property var cool: typeof cooler !== "undefined" ? cooler : null
    readonly property bool coolerUp: cool !== null && cool.connected
    // one row per peripheral; backends with several (Wi-Fi, Bluetooth devices…) expose `summaries`
    readonly property var deviceRows: appState.peripherals.reduce(
        (rows, b) => rows.concat(b.summaries !== undefined ? b.summaries : [b.summary]), [])

    function fmt(v, digits) {
        return (v === null || v === undefined) ? "—" : Number(v).toLocaleString(Qt.locale(), "f", digits || 0)
    }
    function mbit(bps) {
        const b = bps * 8
        return b >= 1e6 ? (b / 1e6).toFixed(1) + " Mbit/s" : b >= 1e3 ? Math.round(b / 1e3) + " kbit/s" : Math.round(b) + " bit/s"
    }
    function gpuName() {
        return gpuInfo && gpuInfo.name ? gpuInfo.name.replace(/\s*\(.*\)\s*$/, "") : "GPU"
    }
    function health() {
        if (appState.serviceState !== "active") return "Background service stopped"
        if (cool !== null && !cool.connected) return "Cooler not connected"
        if (live.cpuTemp > 85) return "CPU running hot"
        return "All systems normal"
    }

    PageHeader {
        title: "System overview"
        subtitle: [info.os, info.kernel ? "Kernel " + info.kernel : "", page.health()].filter(s => s).join(" · ")
        status: "Live"
    }

    GridLayout {
        Layout.fillWidth: true
        columns: page.pageWidth >= 900 ? 4 : page.pageWidth >= 520 ? 2 : 1
        columnSpacing: 12
        rowSpacing: 12
        uniformCellWidths: true
        MetricCard {
            Layout.fillWidth: true
            icon: "thermometer"; label: "CPU temperature"
            value: page.fmt(page.live.cpuTemp); unit: "°C"
            detail: page.info.cpu ? page.info.cpu.name : ""
        }
        MetricCard {
            Layout.fillWidth: true
            icon: "monitor"; label: "GPU temperature"
            value: page.fmt(page.gpu.temp_edge); unit: "°C"
            detail: page.gpuName()
        }
        MetricCard {
            Layout.fillWidth: true
            icon: "fan"; label: "Radiator fans"
            value: page.coolerUp ? page.fmt(page.cool.live.fan) : "—"; unit: "RPM"
            detail: page.coolerUp ? page.cool.fanModeName + " profile" : "Cooler not connected"
        }
        MetricCard {
            Layout.fillWidth: true
            icon: "activity"; label: "Pump"
            value: page.coolerUp ? page.fmt(page.cool.live.pump) : "—"; unit: "RPM"
            detail: page.coolerUp ? page.cool.pumpModeName + " profile" : "Cooler not connected"
        }
    }

    // ---- left: cooling, live usage, system summary · right: devices (both columns end level)
    GridLayout {
        Layout.fillWidth: true
        columns: page.pageWidth >= 900 ? 2 : 1
        columnSpacing: 16
        rowSpacing: 16

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.horizontalStretchFactor: 62
            spacing: 16

            // live usage: takes the height left over, so this column ends level with the device list
            Panel {
                id: usagePanel
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: "Live usage"
                subtitle: "Last minute"
                actionText: "Resources"
                onActionClicked: root.navigate("resources")
                readonly property var h: usage.history
                readonly property var n: usage.now
                readonly property var net: (n.nets || []).filter(a => a.up)
                GridLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    columns: page.pageWidth >= 1100 ? 4 : 2
                    columnSpacing: 12; rowSpacing: 12; uniformCellWidths: true
                    Repeater {
                        model: LiveModel { values: [
                            { label: "CPU", value: (usagePanel.n.cpu ? usagePanel.n.cpu.total : 0) + "%",
                              values: usagePanel.h.cpu || [], max: 100 },
                            { label: "Memory", value: Math.round((usagePanel.h.memory || [0]).slice(-1)[0] || 0) + "%",
                              values: usagePanel.h.memory || [], max: 100 },
                            { label: "GPU", value: ((usagePanel.n.gpus || [])[0] || { busy: 0 }).busy + "%",
                              values: (((usagePanel.h.gpus || {})[((usagePanel.n.gpus || [])[0] || {}).card] || {}).busy) || [], max: 100 },
                            { label: "Network", value: usagePanel.net.length
                                  ? "↓ " + page.mbit(usagePanel.net.reduce((a, x) => a + x.rx, 0)) : "offline",
                              values: usagePanel.net.length ? ((usagePanel.h.nets || {})[usagePanel.net[0].device] || {}).rx || [] : [],
                              values2: usagePanel.net.length ? ((usagePanel.h.nets || {})[usagePanel.net[0].device] || {}).tx || [] : [],
                              max: 0 }
                        ] }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: 4
                            RowLayout {
                                Layout.fillWidth: true
                                Label { text: modelData.label; color: theme.muted; font.pixelSize: 12; Layout.fillWidth: true }
                                Label { text: modelData.value; color: theme.text; font.pixelSize: 12 }
                            }
                            HistoryChart {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.minimumHeight: 56
                                grid: false
                                values: modelData.values; values2: modelData.values2 || []
                                maxValue: modelData.max; length: usage.historyLength
                            }
                        }
                    }
                }
            }

        }

        Panel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.alignment: Qt.AlignTop
            Layout.horizontalStretchFactor: 38
            title: "Devices"
            subtitle: (page.coolerUp ? 1 : 0) + (page.gpuInfo ? 1 : 0)
                      + page.deviceRows.filter(r => r.connected).length + " connected"
            padding: 0
            DeviceRow {
                visible: page.cool !== null
                compact: true
                showDivider: false
                icon: "fan"
                title: page.cool ? page.cool.identity.model : ""
                detail: "USB 0414:7a5e"
                status: page.coolerUp ? "Connected" : "Disconnected"
                tone: page.coolerUp ? theme.live : theme.warning
            }
            DeviceRow {
                visible: page.gpuInfo !== null
                compact: true
                showDivider: page.cool !== null
                icon: "monitor"
                title: page.gpuName()
                detail: page.gpuInfo ? [page.gpuInfo.kernel_driver, page.info.mesa ? "Mesa " + page.info.mesa : ""]
                                       .filter(s => s).join(" · ") : ""
                status: "Monitoring"
            }
            Repeater {
                model: LiveModel { values: page.deviceRows }
                DeviceRow {
                    readonly property var s: modelData
                    compact: true
                    icon: s.icon
                    title: s.title
                    detail: s.detail
                    status: s.status
                    tone: s.tone === "live" ? theme.live : s.tone === "error" ? theme.error : theme.warning
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                onClicked: root.navigate(parent.s.id) }
                }
            }
            Item { Layout.fillHeight: true }
        }
    }
}
