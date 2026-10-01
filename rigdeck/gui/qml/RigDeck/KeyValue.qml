import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RowLayout {
    property string key: ""
    property string value: ""
    Layout.fillWidth: true
    spacing: 16
    Label { text: parent.key; color: theme.muted; font.pixelSize: 13; Layout.preferredWidth: 150 }
    Label { text: parent.value || "unknown"; color: theme.text; font.pixelSize: 13; elide: Text.ElideRight
            Layout.fillWidth: true; textFormat: Text.PlainText }
}
