import QtQuick
import QtQuick.Controls

// A key's travel drawn to scale (0 at rest, 4.0 mm at the bottom): where it types (press point)
// and where it lets go: just above the press point (Standard), or as soon as it rises the release
// distance from wherever it is (Rapid; drawn from the bottom). Values in 0.1 mm; -1 = mixed.
Item {
    id: root
    property int act: 20
    property int rapid: 0
    property int travel: 40
    implicitWidth: 230
    implicitHeight: 190

    readonly property real topY: 22
    readonly property real track: height - topY - 18
    function yAt(t) { return topY + track * Math.max(0, Math.min(travel, t)) / travel }
    readonly property bool mixed: act < 0

    // the switch: a stem moving in a housing
    Rectangle {               // housing
        id: housing
        x: 18; y: root.topY; width: 34; height: root.track
        radius: 4; color: theme.raised; border.color: theme.border
    }
    Rectangle {               // keycap at rest
        x: housing.x - 8; y: root.topY - 14; width: housing.width + 16; height: 12; radius: 3
        color: theme.panel; border.color: theme.border
    }
    Label { x: housing.x + housing.width + 12; y: root.topY - 8; text: "at rest"; color: theme.muted; font.pixelSize: 11 }
    Label { x: housing.x + housing.width + 12; y: root.topY + root.track - 8; text: (root.travel / 10).toFixed(1) + " mm (bottom)"
            color: theme.muted; font.pixelSize: 11 }

    // Rapid: the release distance, shown from the bottom up
    Rectangle {
        visible: root.rapid > 0 && !root.mixed
        x: housing.x + 4; width: housing.width - 8
        y: root.yAt(root.travel - root.rapid); height: root.yAt(root.travel) - y
        radius: 2; color: Qt.alpha(theme.accent, 0.35)
        Behavior on y { enabled: !appState.reduceMotion; NumberAnimation { duration: 180 } }
        Behavior on height { enabled: !appState.reduceMotion; NumberAnimation { duration: 180 } }
    }
    Label {
        visible: root.rapid > 0 && !root.mixed
        x: housing.x + housing.width + 12
        y: Math.min(root.yAt(root.travel - root.rapid / 2) - 8, root.topY + root.track - 30)
        text: "↑ " + (root.rapid / 10).toFixed(1) + " mm up: lets go"
        color: theme.accent; font.pixelSize: 12; font.bold: true
    }

    // press point
    Rectangle {
        id: pressLine
        visible: !root.mixed
        x: housing.x - 6; width: housing.width + 12; height: 2
        y: root.yAt(root.act) - 1
        color: theme.live
        Behavior on y { enabled: !appState.reduceMotion; NumberAnimation { duration: 180 } }
    }
    Label {
        visible: !root.mixed
        x: housing.x + housing.width + 12; y: pressLine.y - 9
        text: (root.act / 10).toFixed(1) + " mm: types" + (root.rapid > 0 ? "" : " / lets go")
        color: theme.live; font.pixelSize: 12; font.bold: true
    }
    Label {
        visible: root.mixed
        anchors.centerIn: housing
        x: housing.x + housing.width + 12
        text: "keys differ"; color: theme.muted; font.pixelSize: 11
        rotation: -90
    }
}
