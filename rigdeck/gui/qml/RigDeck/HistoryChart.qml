import QtQuick

// Rolling history like Task Manager's: newest sample on the right, `length` samples across.
// `values` fills an area; optional `values2` draws a second line (e.g. upload, writes).
// maxValue <= 0 scales to the largest value shown.
Canvas {
    id: root
    property var values: []
    property var values2: []
    property real maxValue: 100
    property int length: 60
    property color color: theme.accent
    property color color2: theme.warning
    property bool grid: true
    property bool frame: true
    readonly property real peak: maxValue > 0 ? maxValue
                                : Math.max(1, Math.max.apply(null, (values || []).concat(values2 || []).concat([0])) * 1.15)
    implicitHeight: 120
    renderStrategy: Canvas.Cooperative

    onValuesChanged: requestPaint()
    onValues2Changed: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    Connections { target: theme; function onChanged() { root.requestPaint() } }

    function line(ctx, vals, fill, col) {
        if (!vals || vals.length < 2) return
        const n = vals.length, step = width / (length - 1), x0 = width - (n - 1) * step
        ctx.beginPath()
        for (let i = 0; i < n; i++) {
            const x = x0 + i * step, y = height - Math.min(1, vals[i] / peak) * (height - 2) - 1
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
        }
        ctx.strokeStyle = col
        ctx.lineWidth = 1.5
        ctx.stroke()
        if (fill) {
            ctx.lineTo(width, height); ctx.lineTo(x0, height); ctx.closePath()
            ctx.fillStyle = Qt.rgba(col.r, col.g, col.b, 0.18)
            ctx.fill()
        }
    }

    onPaint: {
        const ctx = getContext("2d")
        ctx.reset()
        if (grid) {
            ctx.strokeStyle = Qt.rgba(theme.text.r, theme.text.g, theme.text.b, 0.07)
            ctx.lineWidth = 1
            for (let i = 1; i < 4; i++) {
                const y = Math.round(height * i / 4) + 0.5
                ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke()
            }
            for (let i = 1; i < 6; i++) {
                const x = Math.round(width * i / 6) + 0.5
                ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke()
            }
        }
        line(ctx, values, true, color)
        line(ctx, values2, false, color2)
        if (frame) {
            ctx.strokeStyle = theme.border
            ctx.lineWidth = 1
            ctx.strokeRect(0.5, 0.5, width - 1, height - 1)
        }
    }
}
