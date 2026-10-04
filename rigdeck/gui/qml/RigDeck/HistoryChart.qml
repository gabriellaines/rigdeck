import QtQuick
import QtQuick.Shapes

// Rolling history like Task Manager's: newest sample on the right, `length` samples across.
// `values` fills an area; optional `values2` draws a second line (e.g. upload, writes).
// Optional `bands`: [{from, to_}] fractions of the width, shaded behind the curve (e.g. alt-tabs).
// maxValue <= 0 scales to the largest value shown (and eases to a new scale).
// Drawn with Shapes, so an update never blanks the chart: the old curve stays until the new one
// replaces it, and each new sample slides in from the right over `slideMs` (off with reduce motion).
Item {
    id: root
    property var values: []
    property var values2: []
    property var bands: []
    property color bandColor: theme.warning
    property real maxValue: 100
    property int length: 60
    property color color: theme.accent
    property color color2: theme.warning
    property bool grid: true
    property bool frame: true
    property int slideMs: 900            // about one sample interval
    implicitHeight: 120
    clip: true

    readonly property real targetPeak: maxValue > 0 ? maxValue
        : Math.max(1, Math.max.apply(null, (values || []).concat(values2 || []).concat([0])) * 1.15)
    property real peak: targetPeak
    Behavior on peak { enabled: !appState.reduceMotion; NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }

    readonly property real step: width / Math.max(1, length - 1)

    // the sample that just scrolled out, drawn one step left of the chart so the curve stays
    // continuous while it slides (it's clipped away once the slide ends)
    property var lead: [undefined, undefined]
    property var _prev: [[], []]

    function points(vals, closed, which) {
        const out = []
        if (!vals || vals.length < 2 || width <= 0) return out
        const n = vals.length, x0 = width - (n - 1) * step, h = height - 2
        const y = v => height - 1 - Math.min(1, Math.max(0, v) / peak) * h
        if (lead[which] !== undefined && n >= length) out.push(Qt.point(x0 - step, y(lead[which])))
        for (let i = 0; i < n; i++)
            out.push(Qt.point(x0 + i * step, y(vals[i])))
        if (closed) { out.push(Qt.point(width, height)); out.push(Qt.point(out[0].x, height)) }
        return out
    }

    // a new sample: start one step to the right and slide into place
    function remember(which, vals) {
        const p = _prev[which]
        lead[which] = p && p.length && vals && vals.length >= length ? p[0] : undefined
        _prev[which] = vals ? vals.slice() : []
        lead = lead                                   // notify
    }
    onValues2Changed: remember(1, values2)
    onValuesChanged: {
        remember(0, values)
        if (appState.reduceMotion || !visible) return
        slide.stop(); shift.x = step; slide.start()
    }

    // grid (static)
    Repeater {
        model: root.grid ? 3 : 0
        Rectangle { required property int index
                    width: root.width; height: 1; y: Math.round(root.height * (index + 1) / 4)
                    color: Qt.alpha(theme.text, 0.07) }
    }
    Repeater {
        model: root.grid ? 5 : 0
        Rectangle { required property int index
                    width: 1; height: root.height; x: Math.round(root.width * (index + 1) / 6)
                    color: Qt.alpha(theme.text, 0.07) }
    }

    Repeater {
        model: root.bands || []
        Rectangle { required property var modelData
                    x: root.width * modelData.from; height: root.height
                    width: Math.max(2, root.width * (modelData.to_ - modelData.from))
                    color: Qt.alpha(root.bandColor, 0.16) }
    }

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        transform: Translate { id: shift; x: 0 }
        NumberAnimation { id: slide; target: shift; property: "x"; to: 0; duration: root.slideMs }

        ShapePath {                     // area under the main line
            strokeColor: "transparent"
            fillColor: Qt.alpha(root.color, 0.18)
            PathPolyline { path: root.points(root.values, true, 0) }
        }
        ShapePath {
            strokeColor: root.color
            strokeWidth: 1.5
            fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin
            PathPolyline { path: root.points(root.values, false, 0) }
        }
        ShapePath {
            strokeColor: root.color2
            strokeWidth: 1.5
            fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin
            PathPolyline { path: root.points(root.values2, false, 1) }
        }
    }

    Rectangle {
        visible: root.frame
        anchors.fill: parent
        color: "transparent"
        border.color: theme.border
    }
}
