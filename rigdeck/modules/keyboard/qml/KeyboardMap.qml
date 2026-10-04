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
    property string view: "keys"          // "keys" | "lighting"
    property int wideAct: 20               // the profile-wide values (keys that differ are highlighted)
    property int wideRapid: 0
    readonly property real unit: width / 18.25
    implicitHeight: unit * 7.35

    function isSelected(name) { return selected.indexOf(name) >= 0 }
    function toggle(name, add) {
        if (!add) { picked(isSelected(name) && selected.length === 1 ? [] : [name]); return }
        picked(isSelected(name) ? selected.filter(n => n !== name) : selected.concat([name]))
    }
    // keys only show what differs from the profile-wide values
    function keyText(v) {
        if (view !== "keys" || !v || !v.own || v.act === undefined) return ""
        return v.act !== wideAct || !v.rapid ? (v.act / 10).toFixed(1) : ""
    }
    function rapidText(v) {
        if (view !== "keys" || !v || !v.own || v.act === undefined) return ""
        return v.rapid !== wideRapid ? (v.rapid ? "↑" + (v.rapid / 10).toFixed(1) : "↑ off") : ""
    }
    function labelColor(v) {             // readable on the key's own colour in the lighting view
        if (view !== "lighting" || !v || !v.color) return theme.text
        const c = parseInt(v.color, 16), r = c >> 16, g = (c >> 8) & 255, b = c & 255
        return 0.299 * r + 0.587 * g + 0.114 * b > 140 ? "#111" : "#eee"
    }
    function fill(v) {
        if (view === "lighting") return v && v.color ? "#" + v.color : theme.raised
        return v && v.own ? Qt.alpha(theme.accent, 0.28) : theme.raised      // keys with their own settings
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
            opacity: root.view !== "lighting" && !modelData.analog ? 0.35 : 1  // media keys: lights only
            x: modelData.x * root.unit + 2; y: modelData.y * root.unit + (modelData.analog ? 2 : root.unit * 0.3)
            width: modelData.w * root.unit - 4; height: modelData.analog ? root.unit - 4 : root.unit * 0.55
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
            Label {
                anchors { right: parent.right; top: parent.top; rightMargin: 5; topMargin: 3 }
                text: root.rapidText(parent.v)
                font.pixelSize: Math.max(9, root.unit * 0.18)
                color: theme.accent
                font.bold: true
            }
        }
    }
    Rectangle {               // selection band
        visible: root.band.width > 3 || root.band.height > 3
        x: root.band.x; y: root.band.y; width: root.band.width; height: root.band.height
        color: Qt.alpha(theme.accent, 0.15); border.color: theme.accent
    }
}
