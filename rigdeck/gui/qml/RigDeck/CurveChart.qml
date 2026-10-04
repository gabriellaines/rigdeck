import QtQuick
import QtQuick.Controls

// Temperature → RPM chart. `points`/`points2` are [{t, rpm}]; points are draggable when
// `editable`. Keyboard: Tab focuses the chart, Left/Right choose a point, Shift+arrows move it.
Canvas {
    id: root
    renderStrategy: Canvas.Immediate          // no blank frame between clear and redraw
    renderTarget: Canvas.FramebufferObject
    property var points: []
    property var points2: []          // second, dashed curve (pump)
    property bool editable: false
    property bool compact: false
    property real tMax: 100
    property real rpmMax: 3200        // y-axis maximum (RPM, or 100 for percent)
    property real yStep: 800          // grid / label spacing on the y axis
    property string ySuffix: ""       // e.g. "%"
    property int selected: -1
    signal pointMoved(int index, int t, int rpm)

    readonly property real padL: compact ? 4 : 48
    readonly property real padR: 10
    readonly property real padT: 10
    readonly property real padB: compact ? 22 : 28
    implicitHeight: compact ? 190 : 260
    activeFocusOnTab: editable
    Accessible.name: editable ? "Fan curve editor. Use left and right to pick a point, shift and arrows to move it."
                              : "Fan curve"

    function px(t) { return padL + (width - padL - padR) * t / tMax }
    function py(r) { return padT + (height - padT - padB) * (1 - r / rpmMax) }
    function dataAt(x, y) {
        return { t: (x - padL) / (width - padL - padR) * tMax,
                 rpm: (1 - (y - padT) / (height - padT - padB)) * rpmMax }
    }

    // pages re-read their data every few seconds: only redraw when the curve really changed
    property string _drawn: ""
    function maybePaint() {
        const key = JSON.stringify([points, points2])
        if (key !== _drawn) { _drawn = key; requestPaint() }
    }
    onPointsChanged: maybePaint()
    onPoints2Changed: maybePaint()
    onSelectedChanged: requestPaint()
    onActiveFocusChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    Connections { target: theme; function onChanged() { root.requestPaint() } }

    onPaint: {
        const ctx = getContext("2d")
        ctx.reset()
        ctx.font = "11px sans-serif"
        // grid
        ctx.strokeStyle = Qt.rgba(theme.text.r, theme.text.g, theme.text.b, 0.08)
        ctx.lineWidth = 1
        for (let r = 0; r <= rpmMax; r += yStep) {
            const y = Math.round(py(r)) + 0.5
            ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(width - padR, y); ctx.stroke()
            if (!compact) {
                ctx.fillStyle = theme.muted
                ctx.textAlign = "right"
                ctx.fillText(r.toString() + ySuffix, padL - 8, y + 4)
            }
        }
        ctx.strokeStyle = theme.border
        ctx.beginPath(); ctx.moveTo(padL + 0.5, padT); ctx.lineTo(padL + 0.5, height - padB); ctx.stroke()
        // x labels: every 20° (full) or at the curve points (compact)
        ctx.fillStyle = theme.muted
        ctx.textAlign = "center"
        const ticks = compact ? (points || []).map(p => p.t) : [0, 20, 40, 60, 80, 100]
        for (const t of ticks)
            ctx.fillText(t + "°C", Math.min(Math.max(px(t), padL + 16), width - padR - 16), height - 8)

        function curve(pts, color, dashed, dots) {
            if (!pts || pts.length === 0) return
            ctx.strokeStyle = color
            ctx.lineWidth = 2
            ctx.setLineDash(dashed ? [6, 4] : [])
            ctx.beginPath()
            ctx.moveTo(padL, py(pts[0].rpm))
            for (const p of pts) ctx.lineTo(px(p.t), py(p.rpm))
            ctx.lineTo(width - padR, py(pts[pts.length - 1].rpm))
            ctx.stroke()
            ctx.setLineDash([])
            if (!dots) return
            for (let i = 0; i < pts.length; i++) {
                const x = px(pts[i].t), y = py(pts[i].rpm)
                ctx.beginPath()
                ctx.arc(x, y, i === root.selected && root.activeFocus ? 7 : 5, 0, 2 * Math.PI)
                ctx.fillStyle = theme.panel
                ctx.fill()
                ctx.lineWidth = 2
                ctx.strokeStyle = color
                ctx.stroke()
            }
        }
        curve(points2, Qt.rgba(theme.muted.r, theme.muted.g, theme.muted.b, 0.9), true, false)
        curve(points, theme.accent, false, true)
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.editable
        cursorShape: root.editable ? Qt.PointingHandCursor : Qt.ArrowCursor
        property int drag: -1
        onPressed: (m) => {
            root.forceActiveFocus()
            drag = -1
            let best = 14
            for (let i = 0; i < root.points.length; i++) {
                const d = Math.hypot(root.px(root.points[i].t) - m.x, root.py(root.points[i].rpm) - m.y)
                if (d < best) { best = d; drag = i }
            }
            if (drag >= 0) root.selected = drag
        }
        onPositionChanged: (m) => {
            if (drag < 0) return
            const d = root.dataAt(m.x, m.y)
            root.pointMoved(drag, Math.round(d.t), Math.round(d.rpm))
        }
        onReleased: drag = -1
    }

    Keys.onPressed: (e) => {
        if (!editable || points.length === 0) return
        if (selected < 0) selected = 0
        const p = points[selected]
        const moving = e.modifiers & Qt.ShiftModifier
        if (e.key === Qt.Key_Left && !moving) selected = Math.max(0, selected - 1)
        else if (e.key === Qt.Key_Right && !moving) selected = Math.min(points.length - 1, selected + 1)
        else if (e.key === Qt.Key_Left) pointMoved(selected, p.t - 1, p.rpm)
        else if (e.key === Qt.Key_Right) pointMoved(selected, p.t + 1, p.rpm)
        else if (e.key === Qt.Key_Up) pointMoved(selected, p.t, p.rpm + rpmMax / 64)
        else if (e.key === Qt.Key_Down) pointMoved(selected, p.t, p.rpm - rpmMax / 64)
        else return
        e.accepted = true
    }
}
