import QtQuick

// Outlined Lucide icon, recolored through the `icons` image provider.
Item {
    id: root
    property string name: "box"
    property color color: theme.text
    property int size: 16
    implicitWidth: size
    implicitHeight: size
    Image {
        anchors.fill: parent
        sourceSize: Qt.size(root.size * 2, root.size * 2)   // 2x for sharpness on HiDPI
        source: "image://icons/" + root.name + "/" + root.color.toString().slice(-6)
        fillMode: Image.PreserveAspectFit
        smooth: true
    }
}
