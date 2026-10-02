import QtQuick
import QtQuick.Controls

// The keyboard drawn to scale. Click a key to select it; Ctrl/Shift+click adds to the selection;
// drag across keys to select a block. Each key shows the value of the current view.
Item {
    id: root
    property var layout: []               // [{name, label, x, y, w}] in key units
    property var values: ({})             // name -> {act, rapid, release, color}; act/rapid/release in 0.1 mm
    property var selected: []             // key names (owned by the page)
    signal picked(var names)              // the user changed the selection
    property string view: "actuation"     // "actuation" | "rapid" | "lighting"
    readonly property real unit: width / 18.25
    implicitHeight: unit * 7.35

    function isSelected(name) { return selected.indexOf(name) >= 0 }
    function toggle(name, add) {
        if (!add) { picked(isSelected(name) && selected.length === 1 ? [] : [name]); return }
        picked(isSelected(name) ? selected.filter(n => n !== name) : selected.concat([name]))
    }
    function keyText(v) {
        if (!v || v.act === undefined) return ""          // media keys: no analog switch
        if (view === "actuation") return (v.act / 10).toFixed(1)
        if (view === "rapid") return v.rapid ? (v.rapid / 10).toFixed(1) + (v.release && v.release !== v.rapid
                                                ? "/" + (v.release / 10).toFixed(1) : "") : ""
        return ""
    }
    function labelColor(v) {             // readable on the key's own colour in the lighting view
        if (view !== "lighting" || !v || !v.color) return theme.text
        const c = parseInt(v.color, 16), r = c >> 16, g = (c >> 8) & 255, b = c & 255
        return 0.299 * r + 0.587 * g + 0.114 * b > 140 ? "#111" : "#eee"
    }
    function fill(v) {
        if (view === "lighting") return v && v.color ? "#" + v.color : theme.raised
        if (view === "rapid") return v && v.rapid ? Qt.alpha(theme.accent, 0.25 + 0.6 * (1 - v.rapid / 40)) : theme.raised
        // actuation: lighter = shallower (fires earlier), the 2.0 mm default stays neutral
        if (!v || v.act === 20) return theme.raised
        return Qt.alpha(v.act < 20 ? "#f0a030" : "#3a8fe0", 0.25 + 0.5 * Math.abs(v.act - 20) / 20)
    }

    // drag-to-select
    property point dragFrom
    property rect band: Qt.rect(0, 0, 0, 0)
    MouseArea {
        anchors.fill: parent
        property bool add
        onPressed: e => { add = e.modifiers & (Qt.ControlModifier | Qt.ShiftModifier)
                          root.dragFrom = Qt.point(e.x, e.y); root.band = Qt.rect(e.x, e.y, 0, 0) }
        onPositionChanged: e => root.band = Qt.rect(Math.min(e.x, root.dragFrom.x), Math.min(e.y, root.dragFrom.y),
                                                    Math.abs(e.x - root.dragFrom.x), Math.abs(e.y - root.dragFrom.y))
        onReleased: {
            const b = root.band
            if (b.width < 4 && b.height < 4) {           // a click
                const k = root.layout.find(k => b.x >= k.x * root.unit && b.x <= (k.x + k.w) * root.unit
                                                 && b.y >= k.y * root.unit && b.y <= (k.y + 1) * root.unit)
                if (k) root.toggle(k.name, add)
                else if (!add) root.picked([])
            } else {
                const hit = root.layout.filter(k => (k.x + k.w) * root.unit > b.x && k.x * root.unit < b.x + b.width
                                                    && (k.y + 1) * root.unit > b.y && k.y * root.unit < b.y + b.height)
                                       .map(k => k.name)
                root.picked(add ? Array.from(new Set(root.selected.concat(hit))) : hit)
            }
            root.band = Qt.rect(0, 0, 0, 0)
        }
    }

    Repeater {
        model: root.layout
        Rectangle {
            required property var modelData
            readonly property var v: root.values[modelData.name]
            readonly property bool sel: root.isSelected(modelData.name)
            opacity: root.view !== "lighting" && !modelData.analog ? 0.4 : 1   // media keys: lights only
            x: modelData.x * root.unit + 2; y: modelData.y * root.unit + 2
            width: modelData.w * root.unit - 4; height: root.unit - 4
            radius: modelData.analog ? 5 : height / 2
            color: root.fill(v)
            border.width: sel ? 2.5 : 1
            border.color: sel ? theme.accent : theme.border
            Label {
                anchors { left: parent.left; top: parent.top; leftMargin: 5; topMargin: 3 }
                text: parent.modelData.label
                font.pixelSize: Math.max(9, root.unit * 0.22)
                color: root.labelColor(parent.v)
            }
            Label {
                anchors { right: parent.right; bottom: parent.bottom; rightMargin: 5; bottomMargin: 2 }
                text: root.keyText(parent.v)
                font.pixelSize: Math.max(9, root.unit * 0.2)
                font.bold: true
                color: root.labelColor(parent.v)
            }
        }
    }
    Rectangle {               // selection band
        visible: root.band.width > 3 || root.band.height > 3
        x: root.band.x; y: root.band.y; width: root.band.width; height: root.band.height
        color: Qt.alpha(theme.accent, 0.15); border.color: theme.accent
    }
}
