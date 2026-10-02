import QtQuick
import QtQuick.Controls as T

// RigDeck's TextField: Fusion's control with a rounded, theme-coloured frame.
T.TextField {
    id: root
    implicitHeight: 32
    hoverEnabled: true
    font.pixelSize: 13
    background: Rectangle {
        implicitWidth: 120
        radius: theme.radius
        color: theme.panel
        border.width: root.activeFocus ? 2 : 1
        border.color: root.activeFocus ? theme.accent : root.hovered ? Qt.darker(theme.border, 1.15) : theme.border
        opacity: root.enabled ? 1 : 0.5
    }
}
