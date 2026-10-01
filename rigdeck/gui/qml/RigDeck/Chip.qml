import QtQuick
import QtQuick.Controls

// Compact label chip (e.g. the active profile). Checkable when used as a selector.
AbstractButton {
    id: root
    property string label: text
    implicitHeight: 26
    implicitWidth: lbl.implicitWidth + 20
    focusPolicy: checkable ? Qt.StrongFocus : Qt.NoFocus
    hoverEnabled: checkable
    Accessible.name: label
    background: Rectangle {
        radius: theme.radius
        color: root.checked ? theme.accent
             : (root.checkable && root.hovered) ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.12)
             : theme.raised
        border.color: root.checked ? theme.accent : theme.border
        border.width: 1
        Rectangle {
            anchors.fill: parent
            anchors.margins: -3
            radius: theme.radius + 2
            color: "transparent"
            border.width: root.visualFocus ? 2 : 0
            border.color: theme.accent
        }
    }
    contentItem: Label {
        id: lbl
        text: root.label
        color: root.checked ? theme.onAccent : theme.text
        font.pixelSize: 12
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    opacity: enabled ? 1 : 0.5
}
