import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

// Record telemetry while playing (like CapFrameX), then review it.
PageScroll {
    id: page
    property bool shown: true
    readonly property var lv: gamemon.live
    readonly property var last: lv.last || ({})
    readonly property var ls: lv.series || ({})
    readonly property var d: gamemon.detail
    readonly property var sm: d.summary || ({})
    readonly property var m: sm.metrics || ({})
    readonly property var fr: d.frames || null
    readonly property var se: d.series || ({})

    Connections { target: gamemon; function onToast(t) { root.showToast(t) } }
    onShownChanged: if (shown) gamemon.refreshList()

    function fmt(v, digits) { return v === null || v === undefined ? "—" : Number(v).toLocaleString(Qt.locale(), "f", digits || 0) }
    function dur(sec) {
        sec = Math.round(sec || 0)
        const h = Math.floor(sec / 3600), mm = Math.floor(sec % 3600 / 60), ss = sec % 60
        return (h ? h + ":" + String(mm).padStart(2, "0") : mm) + ":" + String(ss).padStart(2, "0")
    }
    function stat(key, which) { return page.m[key] ? page.m[key][which] : null }

    PageHeader {
        title: "Game monitor"
        subtitle: "Records CPU, GPU, memory and disks once a second while you play — keeps going if RigDeck is minimised or closed"
        status: gamemon.recording ? "Recording " + page.dur(page.lv.elapsed) : "Ready"
        tone: gamemon.recording ? theme.error : theme.live
    }

    // ---- start / stop and live view
    Panel {
        Layout.fillWidth: true
        title: gamemon.recording ? "Recording" : "New session"
        subtitle: gamemon.recording ? "Detected: " + (page.last.top || "…") : "Start before you launch or join a game; stop when you're done"
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            TextField {
                id: label
                Layout.fillWidth: true
                visible: !gamemon.recording
                placeholderText: "Label (optional), e.g. \"Cyberpunk — ray tracing on\""
                Accessible.name: "Session label"
            }
            Item { Layout.fillWidth: true; visible: gamemon.recording }
            Button {
                text: gamemon.recording ? "Stop and save" : "Start recording"
                icon.source: "image://icons/" + (gamemon.recording ? "circle-stop" : "circle-play") + "/" + theme.onAccent.toString().slice(-6)
                highlighted: true
                enabled: !gamemon.busy
                onClicked: gamemon.recording ? gamemon.stop() : gamemon.start(label.text)
            }
        }
        GridLayout {
            Layout.fillWidth: true
            visible: gamemon.recording
            columns: page.pageWidth >= 1000 ? 4 : 2
            columnSpacing: 12; rowSpacing: 12; uniformCellWidths: true
            MetricCard { Layout.fillWidth: true; icon: "activity"; label: "Elapsed"; value: page.dur(page.lv.elapsed) }
            MetricCard { Layout.fillWidth: true; icon: "cpu"; label: "CPU"; value: page.fmt(page.last.cpu); unit: "%"
                         detail: page.fmt(page.last.cpuTemp) + " °C · busiest thread " + page.fmt(page.last.cpuMax) + "%" }
            MetricCard { Layout.fillWidth: true; icon: "monitor"; label: "GPU"; value: page.fmt(page.last.gpu); unit: "%"
                         detail: page.fmt(page.last.gpuTemp) + " °C · hotspot " + page.fmt(page.last.gpuHotspot) + " °C · " + page.fmt(page.last.gpuPower) + " W" }
            MetricCard { Layout.fillWidth: true; icon: "memory-stick"; label: "Memory"; value: page.fmt(page.last.mem, 1); unit: "GiB"
                         detail: "VRAM " + page.fmt(page.last.vram, 1) + " GiB" }
        }
        RowLayout {
            Layout.fillWidth: true
            visible: gamemon.recording
            spacing: 12
            ColumnLayout {
                Layout.fillWidth: true
                Label { text: "Load — CPU (filled), GPU (line), last 2 minutes"; color: theme.muted; font.pixelSize: 12 }
                HistoryChart { Layout.fillWidth: true; implicitHeight: 110; values: page.ls.cpu || []; values2: page.ls.gpu || []; length: 120 }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Label { text: "Temperature — CPU (filled), GPU hotspot (line)"; color: theme.muted; font.pixelSize: 12 }
                HistoryChart { Layout.fillWidth: true; implicitHeight: 110; values: page.ls.cpuTemp || []; values2: page.ls.gpuHotspot || []
                               maxValue: 110; length: 120 }
            }
        }
    }

    // ---- frames (MangoHud)
    Banner {
        visible: gamemon.mangohud === "setup"
        tone: "info"
        text: "Add FPS, frametimes and 1% lows to your sessions: RigDeck can set up MangoHud to log every frame (the overlay stays hidden). Then add  mangohud %command%  to a game's Steam launch options."
        buttonText: "Set up MangoHud"
        onClicked: gamemon.setupMangohud()
    }
    Banner {
        visible: gamemon.mangohud === "conflict"
        tone: "info"
        text: "For FPS and frametimes, add these lines to " + gamemon.mangohudConf + ":  " + gamemon.mangohudLines.join("  ·  ")
    }
    Banner {
        visible: gamemon.mangohud === "missing"
        tone: "info"
        text: "Install MangoHud (sudo pacman -S mangohud lib32-mangohud) to add FPS and frametimes to your sessions."
    }
    Label {
        visible: gamemon.mangohud === "ready"
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        color: theme.muted; font.pixelSize: 12
        text: "MangoHud logs every frame for RigDeck. Games launched with  mangohud %command%  (Steam launch options) get FPS and frametimes in their sessions."
    }

    // ---- sessions
    RowLayout {
        Layout.fillWidth: true
        spacing: 16

        Panel {
            Layout.preferredWidth: page.pageWidth >= 1000 ? 320 : 240
            Layout.maximumWidth: Layout.preferredWidth
            Layout.alignment: Qt.AlignTop
            title: "Sessions"
            subtitle: gamemon.sessionList.length ? gamemon.sessionList.length + " recorded" : "None yet"
            padding: 0
            Repeater {
                model: gamemon.sessionList
                DeviceRow {
                    compact: true
                    showDivider: index > 0
                    icon: "gamepad-2"
                    title: modelData.name || modelData.game || "Session"
                    detail: modelData.started + (modelData.duration ? " · " + page.dur(modelData.duration) : "")
                    status: modelData.finished ? "" : "recording"
                    tone: theme.error
                    Rectangle { anchors.fill: parent; z: -1; color: theme.accent; opacity: page.d.id === modelData.id ? 0.12 : 0 }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: gamemon.select(modelData.id) }
                }
            }
        }

        // ---- the selected session
        ColumnLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            spacing: 16
            Label {
                visible: !page.d.id
                text: gamemon.sessionList.length ? "Pick a session to see its results." : "Record a session to see its results here."
                color: theme.muted; font.pixelSize: 13
            }
            Panel {
                Layout.fillWidth: true
                visible: !!page.d.id
                title: (page.d.meta && page.d.meta.name) || page.sm.game || "Session"
                subtitle: [(page.d.meta || {}).started, page.dur(page.sm.duration), page.sm.game ? "app: " + page.sm.game : "",
                           page.fr ? page.fmt(page.fr.frames) + " frames from MangoHud" : "no frame data"].filter(t => t).join(" · ")
                headerExtra: [
                    Button { text: "Export CSV"; onClicked: gamemon.exportCsv(page.d.id) },
                    Button { text: "Delete"; onClicked: gamemon.remove(page.d.id) }
                ]
                GridLayout {
                    Layout.fillWidth: true
                    columns: page.pageWidth >= 1100 ? 4 : 2
                    columnSpacing: 12; rowSpacing: 12; uniformCellWidths: true
                    MetricCard { visible: !!page.fr; Layout.fillWidth: true; icon: "gauge"; label: "Average FPS"
                                 value: page.fr ? page.fmt(page.fr.avgFps, 1) : "—"; detail: page.fr ? "frametime " + page.fr.ftAvg + " ms" : "" }
                    MetricCard { visible: !!page.fr; Layout.fillWidth: true; icon: "arrow-down"; label: "1% low"
                                 value: page.fr ? page.fmt(page.fr.low1, 1) : "—"; unit: "FPS"; detail: page.fr ? "99th pct frametime " + page.fr.ftP99 + " ms" : "" }
                    MetricCard { visible: !!page.fr; Layout.fillWidth: true; icon: "arrow-down"; label: "0.1% low"
                                 value: page.fr ? page.fmt(page.fr.low01, 1) : "—"; unit: "FPS"; detail: page.fr ? "worst frame " + page.fr.ftMax + " ms" : "" }
                    MetricCard { visible: !!page.fr; Layout.fillWidth: true; icon: "activity"; label: "Frames"
                                 value: page.fr ? page.fmt(page.fr.frames) : "—"; detail: page.fr ? "app: " + (page.fr.game || "?") : "" }
                    MetricCard { Layout.fillWidth: true; icon: "cpu"; label: "CPU load"; value: page.fmt(page.stat("cpu", "avg")); unit: "% avg"
                                 detail: "max " + page.fmt(page.stat("cpu", "max")) + "% · busiest thread " + page.fmt(page.stat("cpuMax", "p95")) + "% (p95)" }
                    MetricCard { Layout.fillWidth: true; icon: "thermometer"; label: "CPU temperature"; value: page.fmt(page.stat("cpuTemp", "max")); unit: "°C max"
                                 detail: "average " + page.fmt(page.stat("cpuTemp", "avg")) + " °C · clock " + page.fmt(page.stat("cpuMhz", "avg")) + " MHz" }
                    MetricCard { Layout.fillWidth: true; icon: "monitor"; label: "GPU load"; value: page.fmt(page.stat("gpu", "avg")); unit: "% avg"
                                 detail: "clock " + page.fmt(page.stat("gpuMhz", "avg")) + " MHz avg · " + page.fmt(page.stat("gpuMhz", "max")) + " max" }
                    MetricCard { Layout.fillWidth: true; icon: "thermometer"; label: "GPU temperature"; value: page.fmt(page.stat("gpuTemp", "max")); unit: "°C max"
                                 detail: "hotspot " + page.fmt(page.stat("gpuHotspot", "max")) + " · memory " + page.fmt(page.stat("gpuMemTemp", "max")) + " °C" }
                    MetricCard { Layout.fillWidth: true; icon: "zap"; label: "GPU power"; value: page.fmt(page.stat("gpuPower", "avg")); unit: "W avg"
                                 detail: "max " + page.fmt(page.stat("gpuPower", "max")) + " W" }
                    MetricCard { Layout.fillWidth: true; icon: "memory-stick"; label: "VRAM"; value: page.fmt(page.stat("vram", "max"), 1); unit: "GiB max"
                                 detail: "RAM " + page.fmt(page.stat("mem", "max"), 1) + " GiB max" }
                    Repeater {
                        model: Object.keys(page.sm.disks || {}).filter(k => (page.sm.disks[k] || {}).temp)
                        MetricCard { Layout.fillWidth: true; icon: "hard-drive"; label: modelData; unit: "°C max"
                                     value: page.fmt(page.sm.disks[modelData].temp.max)
                                     detail: "read " + page.fmt(page.sm.disks[modelData].read / 1e9, 2) + " GB · written " + page.fmt(page.sm.disks[modelData].written / 1e9, 2) + " GB" }
                    }
                }
            }

            // graphs over the whole session
            Repeater {
                model: !page.d.id ? [] : [
                    { title: "FPS", values: page.fr ? page.fr.fps : [], max: 0, show: !!page.fr },
                    { title: "Frametimes (ms) — spikes are stutters", values: page.fr ? page.fr.frametimes : [], max: 0, show: !!page.fr },
                    { title: "CPU load (filled) and busiest thread (line), %", values: page.se.cpu || [], values2: page.se.cpuMax || [], max: 100, show: true },
                    { title: "GPU load, %", values: page.se.gpu || [], max: 100, show: true },
                    { title: "CPU temperature (filled) and GPU hotspot (line), °C", values: page.se.cpuTemp || [], values2: page.se.gpuHotspot || [], max: 0, show: true },
                    { title: "GPU power, W", values: page.se.gpuPower || [], max: 0, show: true },
                    { title: "Memory (filled) and VRAM (line), GiB", values: page.se.mem || [], values2: page.se.vram || [], max: 0, show: true }
                ]
                Panel {
                    Layout.fillWidth: true
                    visible: modelData.show
                    title: modelData.title
                    padding: 16
                    HistoryChart { Layout.fillWidth: true; implicitHeight: 130; values: modelData.values; values2: modelData.values2 || []
                                   maxValue: modelData.max; length: Math.max(2, modelData.values.length) }
                }
            }

            // every metric: average / 95th percentile / maximum
            Panel {
                Layout.fillWidth: true
                visible: !!page.d.id
                title: "All readings"
                subtitle: "average · 95th percentile · maximum"
                Repeater {
                    model: Object.keys(gamemon.metrics).filter(k => page.m[k])
                    KeyValue {
                        key: gamemon.metrics[modelData].label
                        value: page.fmt(page.m[modelData].avg, 1) + " · " + page.fmt(page.m[modelData].p95, 1) + " · "
                               + page.fmt(page.m[modelData].max, 1) + " " + gamemon.metrics[modelData].unit
                    }
                }
            }
        }
    }
}
