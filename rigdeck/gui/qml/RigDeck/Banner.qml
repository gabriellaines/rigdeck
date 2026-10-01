import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Explains why something is unavailable; tone pairs color with an icon.
Rectangle {
    id: root
    property string text: ""
    property string buttonText: ""
    property string tone: "warning"   // warning | error | info
    signal clicked()
    readonly property color toneColor: tone === "error" ? theme.error : tone === "info" ? theme.accent : theme.warning
    color: Qt.rgba(toneColor.r, toneColor.g, toneColor.b, 0.12)
    border.color: Qt.rgba(toneColor.r, toneColor.g, toneColor.b, 0.5)
    border.width: 1
    radius: theme.radius
    implicitHeight: row.implicitHeight + 20
    Layout.fillWidth: true
    RowLayout {
        id: row
        anchors.fill: parent
        anchors.margins: 10
        anchors.leftMargin: 14
        spacing: 10
        Icon { name: root.tone === "info" ? "download" : "circle-alert"; size: 16; color: root.toneColor }
        Label { text: root.text; color: theme.text; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 13 }
        Button { visible: root.buttonText !== ""; text: root.buttonText; onClicked: root.clicked() }
    }
}
