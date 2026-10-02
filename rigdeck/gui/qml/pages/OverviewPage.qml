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
            icon: "thermometer"; label: "CPU package"
            value: page.fmt(page.live.cpuTemp); unit: "°C"
            detail: page.info.cpu ? page.info.cpu.name : ""
        }
        MetricCard {
            Layout.fillWidth: true
            icon: "monitor"; label: "GPU core"
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

    GridLayout {
        Layout.fillWidth: true
        columns: page.pageWidth >= 900 ? 2 : 1
        columnSpacing: 16
        rowSpacing: 16

        Panel {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop   // the device list beside it can grow taller
            Layout.horizontalStretchFactor: 65
            title: "Cooling"
            subtitle: page.cool ? page.cool.identity.model : "No supported cooler"
            actionText: page.cool ? "Open controls" : ""
            onActionClicked: root.navigate("cooler")
            RowLayout {
                visible: page.cool !== null
                spacing: 20
                Layout.fillWidth: true
                Card {
                    color: "transparent"
                    implicitWidth: 180
                    implicitHeight: 230
                    FanSpinner {
                        anchors.centerIn: parent
                        rpm: page.coolerUp ? page.cool.live.fan : null
                        visible: page.shown
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    RowLayout {
                        Label { text: "Fan curve"; color: theme.muted; font.pixelSize: 14; Layout.fillWidth: true }
                        Chip { label: page.cool ? page.cool.fanModeName : "" }
                    }
                    CurveChart {
                        Layout.fillWidth: true
                        compact: true
                        points: page.cool ? page.cool.fanCurve : []
                        tMax: 90
                    }
                }
            }
            Label {
                visible: page.cool === null
                text: "Connect a supported AIO cooler (GIGABYTE AORUS WATERFORCE X II) to control it here."
                color: theme.muted
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }

        Panel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.horizontalStretchFactor: 35
            title: "Devices"
            subtitle: (page.coolerUp ? 1 : 0) + (page.gpuInfo ? 1 : 0)
                      + page.deviceRows.filter(r => r.connected).length + " connected"
            padding: 0
            DeviceRow {
                visible: page.cool !== null
                showDivider: false
                icon: "fan"
                title: page.cool ? page.cool.identity.model : ""
                detail: "USB 0414:7a5e"
                status: page.coolerUp ? "Connected" : "Disconnected"
                tone: page.coolerUp ? theme.live : theme.warning
            }
            DeviceRow {
                visible: page.gpuInfo !== null
                showDivider: page.cool !== null
                icon: "monitor"
                title: page.gpuName()
                detail: page.gpuInfo ? [page.gpuInfo.kernel_driver, page.info.mesa ? "Mesa " + page.info.mesa : ""]
                                       .filter(s => s).join(" · ") : ""
                status: "Monitoring"
            }
            Repeater {
                model: page.deviceRows
                DeviceRow {
                    readonly property var s: modelData
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

    GridLayout {
        Layout.fillWidth: true
        columns: page.pageWidth >= 760 ? 3 : 1
        columnSpacing: 16
        rowSpacing: 16
        uniformCellWidths: true
        InfoCard {
            Layout.fillWidth: true
            icon: "cpu"; title: "Processor"
            primary: page.info.cpu ? page.info.cpu.name : ""
            lines: page.info.cpu ? [page.info.cpu.cores + " cores · " + page.info.cpu.threads + " threads",
                                    page.fmt(page.live.cpuMhz / 1000, 2) + " GHz current"] : []
        }
        InfoCard {
            Layout.fillWidth: true
            icon: "monitor"; title: "Graphics"
            primary: page.gpuName()
            lines: page.gpuInfo ? [page.gpuInfo.vram_gb ? page.gpuInfo.vram_gb + " GB VRAM" : "",
                                   "Vulkan " + (page.gpuInfo.vulkan_api || "?").split(".").slice(0, 2).join(".")
                                   + " · " + (page.gpuInfo.vulkan_driver || "").toUpperCase()] : []
        }
        InfoCard {
            Layout.fillWidth: true
            icon: "box"; title: "Software"
            primary: "RigDeck service " + (appState.serviceState === "active" ? "active" : appState.serviceState)
            lines: [page.info.mesa ? "Mesa " + page.info.mesa : "Mesa unknown", page.info.session || ""]
        }
    }
}
