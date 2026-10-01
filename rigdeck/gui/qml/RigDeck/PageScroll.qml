import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Scrollable content canvas: max 1152px wide, centered, 24px (16px narrow) outer spacing.
ScrollView {
    id: root
    default property alias content: col.data
    readonly property real pageWidth: col.width
    readonly property bool narrow: width < 700
    contentWidth: availableWidth
    clip: true
    ColumnLayout {
        id: col
        width: Math.min(1152, root.availableWidth - 2 * (root.narrow ? 16 : 24))
        x: (root.availableWidth - width) / 2
        y: root.narrow ? 16 : 24
        spacing: 16
    }
    implicitHeight: col.implicitHeight
    Component.onCompleted: contentItem.contentHeight = Qt.binding(() => col.implicitHeight + 2 * (narrow ? 16 : 24))
}
