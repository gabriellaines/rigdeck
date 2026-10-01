import QtQuick
import QtQuick.Controls

// On/off switch in the theme accent (Fusion's stock one ignores our palette in dark mode).
Switch {
    id: root
    padding: 0
    implicitWidth: indicator.implicitWidth
    implicitHeight: indicator.implicitHeight
    indicator: Rectangle {
        implicitWidth: 40
        implicitHeight: 22
        x: root.leftPadding
        y: root.topPadding + (root.availableHeight - height) / 2
        radius: height / 2
        color: root.checked ? theme.accent : theme.raised
        border.color: root.checked ? theme.accent : theme.border
        opacity: root.enabled ? 1 : 0.45
        Behavior on color { enabled: !appState.reduceMotion; ColorAnimation { duration: 120 } }

        Rectangle {
            width: 16; height: 16; radius: 8
            y: 3
            x: root.checked ? parent.width - width - 3 : 3
            color: root.checked ? theme.onAccent : theme.muted
            Behavior on x { enabled: !appState.reduceMotion; NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        }
        Rectangle {  // keyboard focus ring
            anchors.fill: parent; anchors.margins: -3
            radius: height / 2
            color: "transparent"
            border.color: theme.accent; border.width: 2
            visible: root.visualFocus
        }
    }
    contentItem: Item {}
}
