import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

// One colour on every device with lighting (like SignalRGB), and back to each one's own lighting.
PageScroll {
    id: page
    property bool shown: true
    onShownChanged: if (shown) lighting.refresh()
    readonly property var st: lighting.status
    readonly property var devices: st.devices || []
    readonly property var present: devices.filter(d => d.present)
    property string color: ""                 // picked, not applied yet ("" = the synced one or a default)
    readonly property string shownColor: color || st.color || "00c8ff"
    property var skipped: []                  // device ids left out of the sync

    Connections { target: lighting; function onToast(m) { root.showToast(m) } }

    PageHeader {
        title: "Lighting"
        subtitle: "One colour on all your devices at once, and back to their own lighting whenever you like"
        status: page.st.active ? "Synced" : ""
    }

    Panel {
        Layout.fillWidth: true
        title: "Colour for every device"
        subtitle: page.st.active ? "Synced to #" + page.st.color + ". Pick another colour to change it everywhere."
                                 : "Each device has its own lighting now. Syncing remembers it, so you can go back."
        RowLayout {
            Layout.fillWidth: true
            spacing: 16
            Rectangle {
                implicitWidth: 64; implicitHeight: 64
                radius: theme.radius
                color: "#" + page.shownColor
                border.color: theme.border
                Accessible.name: "Chosen colour #" + page.shownColor
            }
            ColorSwatches {
                Layout.fillWidth: true
                current: page.shownColor
                onPicked: (c) => page.color = c
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 8
            spacing: 10
            Button {
                highlighted: true
                text: lighting.busy ? "Applying…" : page.st.active ? "Apply to synced devices" : "Sync all devices"
                enabled: !lighting.busy && page.present.some(d => page.skipped.indexOf(d.id) < 0)
                onClicked: {
                    lighting.sync(page.shownColor, page.present.map(d => d.id).filter(id => page.skipped.indexOf(id) < 0))
                    page.color = ""
                }
            }
            Button {
                text: "Restore previous lighting"
                visible: page.st.active
                enabled: !lighting.busy
                onClicked: lighting.restore()
            }
            Item { Layout.fillWidth: true }
        }
    }

    Panel {
        Layout.fillWidth: true
        title: "Devices"
        subtitle: "Devices with adjustable colours. Switch one off to leave its lighting alone."
        Label {
            visible: page.devices.length > 0 && page.present.length === 0
            text: "None of the supported devices with lighting is connected."
            color: theme.muted; font.pixelSize: 13
        }
        Repeater {
            model: LiveModel { values: page.present }
            SettingRow {
                title: modelData.name
                description: modelData.synced ? "Synced — its own lighting is remembered" : "Its own lighting"
                Rectangle {
                    visible: modelData.synced
                    implicitWidth: 18; implicitHeight: 18; radius: 9
                    color: "#" + (page.st.color || "000000")
                    border.color: theme.border
                }
                Toggle {
                    checked: page.skipped.indexOf(modelData.id) < 0
                    Accessible.name: "Include " + modelData.name
                    onToggled: page.skipped = checked ? page.skipped.filter(id => id !== modelData.id)
                                                      : page.skipped.concat([modelData.id])
                }
            }
        }
    }

    Banner {
        tone: "info"
        text: "Restore puts every device back to the lighting it had before the first sync, even after a restart. "
              + "The mouse colour is stored on the mouse; the keyboard and cooler colours are kept by the background service."
    }
}
