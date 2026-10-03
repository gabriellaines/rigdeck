import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Card with a header (title, subtitle, optional action) and a body below a divider.
Card {
    id: root
    property string title: ""
    property string subtitle: ""
    property string actionText: ""
    property alias headerExtra: extra.data
    property int padding: 20
    signal actionClicked()
    default property alias content: body.data
    implicitHeight: layout.implicitHeight
    implicitWidth: 300
    opacity: enabled ? 1 : 0.55

    ColumnLayout {
        id: layout
        anchors.fill: parent
        spacing: 0
        RowLayout {
            visible: root.title !== "" || root.actionText !== "" || extra.children.length > 0   // untitled: body only
            Layout.fillWidth: true
            Layout.margins: 20
            Layout.bottomMargin: 14
            Layout.topMargin: 16
            spacing: 12
            ColumnLayout {
                spacing: 2
                Layout.fillWidth: true
                Label {
                    text: root.title
                    color: theme.text
                    font.pixelSize: 16
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
                Label {
                    text: root.subtitle
                    color: theme.muted
                    font.pixelSize: 12
                    visible: text !== ""
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }
            RowLayout { id: extra; spacing: 8 }
            ActionLink {
                label: root.actionText
                visible: root.actionText !== ""
                onClicked: root.actionClicked()
            }
        }
        Rectangle { visible: root.title !== "" || root.actionText !== "" || extra.children.length > 0
                    Layout.fillWidth: true; implicitHeight: 1; color: theme.border }
        ColumnLayout {
            id: body
            Layout.fillWidth: true
            Layout.margins: root.padding
            spacing: 12
        }
        Item { Layout.fillHeight: true }   // extra height goes below the content, not between items
    }
}
