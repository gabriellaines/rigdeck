import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// "Open controls >" style text button.
AbstractButton {
    id: root
    property string label: ""
    implicitWidth: row.implicitWidth + 8
    implicitHeight: 28
    Accessible.name: label
    focusPolicy: Qt.StrongFocus
    background: Rectangle {
        radius: theme.radius
        color: root.hovered ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.12) : "transparent"
        border.width: root.visualFocus ? 2 : 0
        border.color: theme.accent
    }
    contentItem: RowLayout {
        id: row
        spacing: 4
        Label { text: root.label; color: theme.accent; font.pixelSize: 14; leftPadding: 4 }
        Icon { name: "chevron-right"; size: 14; color: theme.accent }
    }
}
