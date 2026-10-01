import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Card {
    id: root
    property string icon: "box"
    property string title: ""
    property string primary: ""
    property var lines: []
    implicitHeight: col.implicitHeight + 32
    implicitWidth: 220

    ColumnLayout {
        id: col
        anchors.fill: parent
        anchors.margins: 16
        spacing: 4
        RowLayout {
            spacing: 8
            Layout.bottomMargin: 8
            Icon { name: root.icon; size: 16; color: theme.accent }
            Label { text: root.title; color: theme.text; font.pixelSize: 14; font.weight: Font.DemiBold }
        }
        Label { text: root.primary; color: theme.text; font.pixelSize: 14; elide: Text.ElideRight; Layout.fillWidth: true }
        Repeater {
            model: root.lines
            Label { text: modelData; color: theme.muted; font.pixelSize: 12; elide: Text.ElideRight; Layout.fillWidth: true }
        }
    }
}
