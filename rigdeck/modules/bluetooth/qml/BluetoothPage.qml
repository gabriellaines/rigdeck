import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    readonly property var pagesFor: ({ headset: "headset", mouse: "mouse", keyboard: "keyboard" })
    readonly property var pageTitles: ({ headset: "Headset", mouse: "Mouse", keyboard: "Keyboard" })

    Connections { target: bluez; function onToast(m) { root.showToast(m) } }

    PageHeader {
        title: "Bluetooth"
        subtitle: "Pairing and connecting happen in your desktop's Bluetooth settings"
        status: bluez.connectedCount + (bluez.connectedCount === 1 ? " device connected" : " devices connected")
        tone: bluez.connectedCount > 0 ? theme.live : theme.muted
    }

    Repeater {
        model: LiveModel { values: bluez.adapters }
        Panel {
            id: ad
            readonly property var a: modelData
            readonly property var mine: bluez.devices.filter(d => d.adapter === a.path)
            Layout.fillWidth: true
            title: "Your devices"
            subtitle: "Adapter " + a.address + " · visible to others as \"" + a.name + "\""
            headerExtra: Button { visible: bluez.canOpenSettings; text: "Pair a device"
                                  onClicked: bluez.openSettings("bluetooth") }
            SettingRow {
                title: "Bluetooth"
                description: ad.a.powered ? "On" : "Off — devices can't connect"
                Toggle { checked: ad.a.powered; Accessible.name: "Bluetooth"; onToggled: bluez.setPowered(ad.a.path, checked) }
            }
            Repeater {
                model: LiveModel { values: ad.mine }
                DeviceRow {
                    Layout.leftMargin: -20; Layout.rightMargin: -20
                    icon: modelData.icon
                    title: modelData.name
                    detail: modelData.kind + (page.pagesFor[modelData.category] && modelData.connected
                                              ? " · also on the " + page.pageTitles[modelData.category] + " page" : "")
                    status: modelData.connected ? (modelData.battery !== null && modelData.battery !== undefined
                                                   ? modelData.battery + "% battery" : "Connected")
                                                : "Paired, not connected"
                    tone: modelData.connected ? theme.live : theme.muted
                    MouseArea {
                        anchors.fill: parent
                        enabled: !!page.pagesFor[modelData.category] && modelData.connected
                        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: root.navigate(page.pagesFor[modelData.category])
                    }
                }
            }
        }
    }
}
