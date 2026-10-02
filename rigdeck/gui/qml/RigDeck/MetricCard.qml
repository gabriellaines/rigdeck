import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Icon + label, big value with unit, muted detail line.
Card {
    id: root
    property string icon: "activity"
    property string label: ""
    property string value: "—"
    property string unit: ""
    property string detail: ""
    property color valueColor: theme.text
    implicitHeight: col.implicitHeight + 32
    implicitWidth: 180
    Layout.fillHeight: true      // cards in one row share its height

    ColumnLayout {
        id: col
        anchors.fill: parent
        anchors.margins: 16
        spacing: 6
        RowLayout {
            spacing: 8
            Icon { name: root.icon; size: 15; color: theme.muted }
            Label { text: root.label; color: theme.muted; font.pixelSize: 13 }
        }
        RowLayout {
            spacing: 4
            Label {
                text: root.value
                color: root.valueColor
                font.pixelSize: 24
                font.weight: Font.DemiBold
            }
            Label {
                text: root.unit
                color: theme.muted
                font.pixelSize: 13
                Layout.alignment: Qt.AlignBaseline
                visible: text !== "" && root.value !== "—"
            }
        }
        Label {
            // always takes its line, so cards with and without a detail are the same height
            text: root.detail !== "" ? root.detail : " "
            color: theme.muted
            font.pixelSize: 12
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
        Item { Layout.fillHeight: true }
    }
}
