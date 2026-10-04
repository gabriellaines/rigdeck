import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Connected Bluetooth devices of one category (e.g. "headset"), for that category's page.
Panel {
    id: root
    property string category: ""
    property string label: "Bluetooth devices"
    readonly property var devices: typeof bluez === "undefined" ? []
                                   : bluez.devices.filter(d => d.connected && d.category === root.category)
    visible: devices.length > 0
    Layout.fillWidth: true
    title: label
    subtitle: "Connected through Bluetooth · settings in your desktop's Bluetooth panel"
    padding: 0
    Repeater {
        model: LiveModel { values: root.devices }
        DeviceRow {
            showDivider: index > 0
            icon: modelData.icon
            title: modelData.name
            detail: "Bluetooth · " + modelData.address
            status: modelData.battery !== null && modelData.battery !== undefined ? modelData.battery + "% battery"
                                                                                  : "Connected"
        }
    }
}
