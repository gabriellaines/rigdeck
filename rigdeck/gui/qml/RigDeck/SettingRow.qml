import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// A setting: title and description on the left, its control (the row's children) on the right.
RowLayout {
    id: root
    property string title: ""
    property string description: ""
    property string note: ""          // muted extra line, e.g. "Not set from RigDeck yet"
    default property alias control: slot.data
    Layout.fillWidth: true
    spacing: 16

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 2
        Label { text: root.title; color: theme.text; font.pixelSize: 14; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Label { visible: text !== ""; text: root.description; color: theme.muted; font.pixelSize: 12
                Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Label { visible: text !== ""; text: root.note; color: theme.warning; font.pixelSize: 12
                Layout.fillWidth: true; wrapMode: Text.WordWrap }
    }
    RowLayout { id: slot; spacing: 8 }
}
