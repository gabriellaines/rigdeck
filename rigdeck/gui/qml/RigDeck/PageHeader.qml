import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 24px title, muted system line, live/connection status on the right.
RowLayout {
    id: root
    property string title: ""
    property string subtitle: ""
    property string status: ""
    property color tone: theme.live
    Layout.fillWidth: true
    spacing: 12
    ColumnLayout {
        spacing: 4
        Layout.fillWidth: true
        Label { text: root.title; color: theme.text; font.pixelSize: 24; font.weight: Font.DemiBold
                elide: Text.ElideRight; Layout.fillWidth: true }
        Label { text: root.subtitle; color: theme.muted; font.pixelSize: 14; visible: text !== ""
                wrapMode: Text.WordWrap; Layout.fillWidth: true }
    }
    RowLayout {
        Layout.alignment: Qt.AlignBottom
        spacing: 6
        visible: root.status !== ""
        StatusDot { tone: root.tone }
        Label { text: root.status; color: theme.muted; font.pixelSize: 12 }
    }
}
