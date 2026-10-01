import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs

// Preset color dots plus "Custom…" (a color dialog). Colors are "rrggbb" without '#'.
Flow {
    id: root
    property string current: ""
    property var colors: ["ff0000", "ff8000", "ffd000", "00ff40", "00c8ff", "0040ff", "a000ff", "ffffff"]
    signal picked(string color)
    spacing: 10

    Repeater {
        model: root.colors
        AbstractButton {
            width: 30; height: 30
            focusPolicy: Qt.StrongFocus
            Accessible.name: "Color #" + modelData
            ToolTip.visible: hovered; ToolTip.text: "#" + modelData
            onClicked: root.picked(modelData)
            background: Rectangle {
                radius: 15
                color: "#" + modelData
                border.color: theme.border
                Rectangle {
                    anchors.fill: parent; anchors.margins: -4; radius: 19; color: "transparent"
                    border.width: (root.current === modelData || parent.parent.visualFocus) ? 2 : 0
                    border.color: theme.accent
                }
            }
        }
    }
    Button {
        text: "Custom…"
        icon.source: "image://icons/droplet/" + theme.text.toString().slice(-6)
        onClicked: dialog.open()
    }
    ColorDialog {
        id: dialog
        selectedColor: "#" + (root.current || "ffffff")
        onAccepted: root.picked(selectedColor.toString().slice(-6))
    }
}
