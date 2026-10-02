import QtQuick
import QtQuick.Controls as T

// RigDeck's button (shadows QtQuick.Controls' Button wherever `import RigDeck` comes after it).
// `highlighted: true` = the main action of a group (Apply, Save, Start…).
T.Button {
    id: root
    implicitHeight: 32
    implicitWidth: Math.max(72, contentItem.implicitWidth + 28)
    hoverEnabled: true
    font.pixelSize: 13
    contentItem: Item {
      implicitWidth: row.implicitWidth
      implicitHeight: row.implicitHeight
      Row {
        id: row
        anchors.centerIn: parent
        spacing: 6
        Image {
            visible: root.icon.source.toString() !== ""
            source: root.icon.source
            width: 16; height: 16; sourceSize: Qt.size(16, 16)
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            text: root.text
            font: root.font
            color: root.highlighted ? "white" : theme.text
            anchors.verticalCenter: parent.verticalCenter
        }
      }
    }
    background: Rectangle {
        radius: theme.radius
        color: root.highlighted
               ? (root.down ? Qt.darker(theme.accent, 1.2) : root.hovered ? Qt.lighter(theme.accent, 1.08) : theme.accent)
               : (root.down ? Qt.darker(theme.raised, 1.12) : root.hovered ? Qt.darker(theme.raised, 1.05) : theme.raised)
        border.color: root.visualFocus ? theme.accent : root.highlighted ? "transparent" : theme.border
        border.width: root.visualFocus ? 2 : 1
        opacity: root.enabled ? 1 : 0.45
        Behavior on color { enabled: !appState.reduceMotion; ColorAnimation { duration: 100 } }
    }
}
