import QtQuick

// Thin usage bar; turns amber/red past the thresholds.
Rectangle {
    id: root
    property real value: 0      // 0..1
    implicitHeight: 6
    radius: 3
    color: theme.raised
    border.color: theme.border
    border.width: 1
    Rectangle {
        width: Math.max(0, Math.min(1, root.value)) * parent.width
        height: parent.height
        radius: parent.radius
        color: root.value > 0.92 ? theme.error : root.value > 0.8 ? theme.warning : theme.accent
        Behavior on width { NumberAnimation { duration: appState.reduceMotion ? 0 : 250 } }
    }
}
