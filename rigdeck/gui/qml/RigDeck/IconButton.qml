import QtQuick
import QtQuick.Controls

// Icon-only button with accessible name and tooltip.
AbstractButton {
    id: root
    property string iconName: "box"
    property string tip: ""
    property int iconSize: 16
    implicitWidth: 32
    implicitHeight: 32
    focusPolicy: Qt.StrongFocus
    Accessible.name: tip
    ToolTip.visible: hovered && tip !== ""
    ToolTip.text: tip
    ToolTip.delay: 400
    opacity: enabled ? 1 : 0.4
    background: Rectangle {
        radius: theme.radius
        color: root.down ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.2)
             : root.hovered ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.12) : "transparent"
        border.width: root.visualFocus ? 2 : 0
        border.color: theme.accent
    }
    contentItem: Item {
        Icon { anchors.centerIn: parent; name: root.iconName; size: root.iconSize; color: theme.text }
    }
}
