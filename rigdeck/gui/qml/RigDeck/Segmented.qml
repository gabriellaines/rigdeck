import QtQuick
import QtQuick.Controls

// Exclusive choice shown as a wrapping row of chips.
Flow {
    id: root
    property var model: []
    property int currentIndex: -1
    property int chipHeight: 32
    property int minChipWidth: 56
    signal activated(int index)
    spacing: 6
    Repeater {
        model: LiveModel { values: root.model }
        Chip {
            label: modelData
            checkable: true
            checked: index === root.currentIndex
            implicitHeight: root.chipHeight
            implicitWidth: Math.max(root.minChipWidth, implicitContentWidth + 24)
            onClicked: { checked = Qt.binding(() => index === root.currentIndex); root.activated(index) }
        }
    }
}
