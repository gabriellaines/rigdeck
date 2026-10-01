import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    function gb(b) { return b >= 1e12 ? (b / 1e12).toFixed(2) + " TB" : (b / 1e9).toFixed(b >= 1e10 ? 0 : 1) + " GB" }

    PageHeader { title: "Storage"; subtitle: system.storage.length + " drives"; status: "Live" }
    Repeater {
        model: system.storage
        Panel {
            Layout.fillWidth: true
            title: modelData.model
            subtitle: [page.gb(modelData.size), modelData.transport, "/dev/" + modelData.name,
                       modelData.removable ? "removable" : ""].filter(s => s).join(" · ")
            headerExtra: [
                Chip { visible: modelData.temp !== null && modelData.temp !== undefined
                       label: Math.round(modelData.temp || 0) + " °C" }
            ]
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
