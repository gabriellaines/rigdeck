import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Icon tile, name + detail, status dot + label. `future` draws the muted "coming soon" style.
Item {
    id: root
    property string icon: "box"
    property string title: ""
    property string detail: ""
    property string status: ""
    property color tone: theme.live
    property bool future: false
    property bool showDivider: true
    property bool compact: false
    implicitHeight: compact ? 56 : 68
    Layout.fillWidth: true

    Rectangle { visible: root.showDivider; anchors.top: parent.top; width: parent.width; height: 1; color: theme.border }
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        spacing: 14
        Rectangle {
            implicitWidth: 36
            implicitHeight: 36
            radius: theme.radius
            color: root.future ? "transparent" : theme.raised
            border.color: theme.border
            border.width: 1
            Icon { anchors.centerIn: parent; name: root.icon; size: 18; color: root.future ? theme.muted : theme.accent }
        }
        ColumnLayout {
            spacing: 2
            Layout.fillWidth: true
            Label {
                text: root.title
                color: root.future ? theme.muted : theme.text
                font.pixelSize: 14
                font.weight: root.future ? Font.Normal : Font.DemiBold
                elide: Text.ElideRight
                Layout.fillWidth: true
                ToolTip.visible: truncated && hov.hovered
                ToolTip.text: text
                HoverHandler { id: hov }
            }
            RowLayout {   // detail, plus (compact rows) the status, so the name gets the whole width
                Layout.fillWidth: true
                spacing: 6
                Label { text: root.detail; color: theme.muted; font.pixelSize: 12; elide: Text.ElideRight; Layout.fillWidth: true }
                StatusDot { visible: root.compact && !root.future && root.status !== ""; tone: root.tone }
                Label { visible: root.compact; text: root.status; color: theme.muted; font.pixelSize: 12 }
            }
        }
        StatusDot { visible: !root.compact && !root.future && root.status !== ""; tone: root.tone }
        Label { visible: !root.compact; text: root.status; color: theme.muted; font.pixelSize: 12 }
    }
}
