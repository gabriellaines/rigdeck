import QtQuick
import QtQuick.Controls as T

// RigDeck's slider: rounded track filled in the accent colour, round handle.
T.Slider {
    id: root
    implicitHeight: 24
    implicitWidth: 200
    hoverEnabled: true
    background: Item {
        x: root.leftPadding; y: root.topPadding + root.availableHeight / 2 - 2
        width: root.availableWidth; height: 4
        Rectangle { anchors.fill: parent; radius: 2; color: theme.raised; border.color: Qt.alpha(theme.border, 0.6) }
        Rectangle { width: root.visualPosition * parent.width; height: parent.height; radius: 2
                    color: theme.accent; opacity: root.enabled ? 1 : 0.4 }
    }
    handle: Rectangle {
        x: root.leftPadding + root.visualPosition * (root.availableWidth - width)
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: 18; height: 18; radius: 9
        color: theme.panel
        border.color: root.enabled ? theme.accent : theme.border
        border.width: root.pressed || root.visualFocus ? 3 : 2
        scale: root.pressed ? 1.1 : root.hovered ? 1.05 : 1
        Behavior on scale { enabled: !appState.reduceMotion; NumberAnimation { duration: 90 } }
    }
}
