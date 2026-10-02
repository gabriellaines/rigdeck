import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    function tb(b) { return b >= 1e12 ? (b / 1e12).toFixed(1) + " TB" : (b / 1e9).toFixed(0) + " GB" }
    function rate(bps) { return bps >= 1e6 ? (bps / 1e6).toFixed(1) + " MB/s" : bps >= 1e3 ? Math.round(bps / 1e3) + " KB/s" : Math.round(bps || 0) + " B/s" }
    function gb(b) { return b >= 1e12 ? (b / 1e12).toFixed(2) + " TB" : (b / 1e9).toFixed(b >= 1e10 ? 0 : 1) + " GB" }

    PageHeader { title: "Storage"; subtitle: system.storage.length + " drives"; status: "Live" }
    Repeater {
        model: system.storage
        Panel {
            id: drive
            Layout.fillWidth: true
            title: modelData.model
            subtitle: [page.gb(modelData.size), modelData.transport, "/dev/" + modelData.name,
                       modelData.removable ? "removable" : ""].filter(s => s).join(" · ")
            headerExtra: [
                Chip { visible: modelData.temp !== null && modelData.temp !== undefined
                       label: Math.round(modelData.temp || 0) + " °C" }
            ]
            // ---- live activity
            readonly property var live: (usage.now.disks || []).find(d => d.name === modelData.name) || ({})
            readonly property var hist: (usage.history.disks || {})[modelData.name] || ({})
            readonly property var hp: usage.health[modelData.name] || null
            readonly property var info: usage.disks[modelData.name] || ({})
            RowLayout {
                Layout.fillWidth: true
                spacing: 16
                HistoryChart { Layout.fillWidth: true; implicitHeight: 70; maxValue: 0
                               values: drive.hist.read || []; values2: drive.hist.write || []
                               length: usage.historyLength }
                ColumnLayout {
                    spacing: 2
                    Label { text: "Read " + page.rate(drive.live.read); color: theme.accent; font.pixelSize: 12 }
                    Label { text: "Write " + page.rate(drive.live.write); color: theme.warning; font.pixelSize: 12 }
                    Label { text: "Active " + Math.round(drive.live.active || 0) + "%"; color: theme.muted; font.pixelSize: 12 }
                }
            }

            // ---- health (SMART, via UDisks)
            GridLayout {
                Layout.fillWidth: true
                visible: drive.hp !== null
                columns: page.pageWidth >= 900 ? 4 : 2
                columnSpacing: 12; rowSpacing: 12; uniformCellWidths: true
                readonly property var hp: drive.hp || ({})
                MetricCard { Layout.fillWidth: true; icon: parent.hp.ok ? "check" : "circle-alert"; label: "Health"
                             value: parent.hp.ok ? "Good" : "Check"; valueColor: parent.hp.ok ? theme.live : theme.error
                             detail: parent.hp.kind === "nvme" ? (parent.hp.warnings.length ? parent.hp.warnings.join(", ") : "No warnings")
                                                               : (parent.hp.badSectors || 0) + " bad sectors" }
                MetricCard { Layout.fillWidth: true; visible: parent.hp.kind === "nvme"; icon: "gauge"; label: "Wear"
                             value: parent.hp.wear !== undefined ? parent.hp.wear : "—"; unit: "% used"
                             detail: "Spare " + parent.hp.spare + "% (alert below " + parent.hp.spareThreshold + "%)" }
                MetricCard { Layout.fillWidth: true; visible: parent.hp.kind === "nvme"; icon: "arrow-up"; label: "Written"
                             value: parent.hp.written ? page.tb(parent.hp.written).split(" ")[0] : "—"
                             unit: parent.hp.written ? page.tb(parent.hp.written).split(" ")[1] : ""
                             detail: parent.hp.read ? page.tb(parent.hp.read) + " read" : "" }
                MetricCard { Layout.fillWidth: true; icon: "activity"; label: "Powered on"
                             value: parent.hp.powerOnHours !== undefined && parent.hp.powerOnHours !== null
                                    ? Math.round(parent.hp.powerOnHours).toLocaleString(Qt.locale(), "f", 0) : "—"
                             unit: "hours"
                             detail: parent.hp.kind === "nvme" ? parent.hp.powerCycles + " power cycles · "
                                                               + parent.hp.unsafeShutdowns + " unsafe shutdowns"
                                                               : "Self-test: " + parent.hp.selftest }
            }
            KeyValue { visible: !!drive.info.firmware; key: "Firmware"; value: drive.info.firmware || "" }
            KeyValue { visible: !!(drive.hp && drive.hp.serial); key: "Serial"; value: drive.hp ? drive.hp.serial : "" }

            Label {
                visible: modelData.filesystems.length === 0
                text: "Not mounted"
                color: theme.muted
                font.pixelSize: 13
            }
            Repeater {
                model: modelData.filesystems
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: modelData.mount; color: theme.text; font.pixelSize: 13; font.weight: Font.DemiBold }
                        Label { text: [modelData.fstype, modelData.label].filter(s => s).join(" · "); color: theme.muted
                                font.pixelSize: 12; Layout.fillWidth: true }
                        Label { text: page.gb(modelData.used) + " of " + page.gb(modelData.size); color: theme.muted; font.pixelSize: 12 }
                    }
                    UsageBar { Layout.fillWidth: true; value: modelData.size ? modelData.used / modelData.size : 0 }
                }
            }
        }
    }
}
