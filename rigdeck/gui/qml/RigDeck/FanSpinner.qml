import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 96px fan that spins with the measured RPM (scaled down); still when reduced motion is on.
ColumnLayout {
    id: root
    property var rpm: null
    property string caption: "Radiator fan speed"
    spacing: 10
    Rectangle {
        Layout.alignment: Qt.AlignHCenter
        implicitWidth: 96
        implicitHeight: 96
        radius: 48
        color: theme.raised
        border.color: theme.border
        border.width: 1
        Icon {
            id: fan
            anchors.centerIn: parent
            name: "fan"
            size: 46
            color: theme.accent
            RotationAnimator on rotation {
                from: 0
                to: 360
                loops: Animation.Infinite
                duration: root.rpm > 0 ? Math.max(400, 600000 / root.rpm) : 1000
                running: root.rpm > 0 && !appState.reduceMotion && root.visible
            }
        }
    }
    Label {
        Layout.alignment: Qt.AlignHCenter
        text: root.rpm === null || root.rpm === undefined ? "—" : Number(root.rpm).toLocaleString(Qt.locale(), "f", 0) + " RPM"
        color: theme.text
        font.pixelSize: 18
        font.weight: Font.DemiBold
    }
    Label { Layout.alignment: Qt.AlignHCenter; text: root.caption; color: theme.muted; font.pixelSize: 12 }
}
