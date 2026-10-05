import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

// Live usage like Task Manager's Performance tab: resources on the left, the selected one on the right.
PageScroll {
    id: page
    property bool shown: true
    property string selected: "cpu"
    property bool logical: false        // CPU chart: one graph per logical processor instead of the total
    readonly property var h: usage.history
    readonly property var n: usage.now
    readonly property var sp: usage.specs
    readonly property var gpuInfo: system.info.gpus || []

    function gib(b) { return b === undefined || b === null ? "—" : (b / 1073741824).toLocaleString(Qt.locale(), "f", 1) }
    function rate(bps, bits) {   // bytes/s -> "12.3 MB/s" (or bit/s for network)
        if (bps === undefined) return "—"
        const v = bits ? bps * 8 : bps, u = bits ? ["bit/s", "kbit/s", "Mbit/s", "Gbit/s"] : ["B/s", "KB/s", "MB/s", "GB/s"]
        let i = 0, x = v
        while (x >= 1000 && i < 3) { x /= 1000; i++ }
        return (i === 0 ? Math.round(x) : x.toFixed(1)) + " " + u[i]
    }
    function uptime(sec) {       // 93784 -> "1:02:03:04" (days:hours:minutes:seconds, like Task Manager)
        if (!sec) return "—"
        const p = v => String(v).padStart(2, "0")
        return Math.floor(sec / 86400) + ":" + p(Math.floor(sec / 3600) % 24) + ":" + p(Math.floor(sec / 60) % 60) + ":" + p(sec % 60)
    }
    function gpuName(card) {
        const g = gpuInfo.find(g => card.endsWith("/" + g.card))
        return g ? g.name.replace(/\s*\(.*\)\s*$/, "") : "Graphics card"
    }

    // the list on the left: one entry per resource
    readonly property var items: {
        const out = [{ key: "cpu", title: "CPU", sub: (n.cpu ? n.cpu.total : 0) + "%  " + ((n.cpu && n.cpu.mhz.length)
                        ? (n.cpu.mhz.reduce((a, b) => a + b, 0) / n.cpu.mhz.length / 1000).toFixed(2) + " GHz" : ""),
                       values: h.cpu || [], max: 100 },
                     { key: "memory", title: "Memory", sub: n.memory ? gib(n.memory.used) + " / " + gib(n.memory.total) + " GiB" : "",
                       values: h.memory || [], max: 100 }]
        for (const d of (n.disks || []))
            out.push({ key: "disk:" + d.name, title: "Disk · " + (d.model || d.name), sub: d.kind + "  " + Math.round(d.active) + "%",
                       values: (h.disks[d.name] || {}).active || [], max: 100 })
        for (const a of (n.nets || []))
            out.push({ key: "net:" + a.device, title: (a.wifi ? "Wi-Fi" : "Ethernet") + " · " + a.device,
                       sub: a.up ? "↓ " + rate(a.rx, true) + "  ↑ " + rate(a.tx, true) : "Not connected",
                       values: (h.nets[a.device] || {}).rx || [], values2: (h.nets[a.device] || {}).tx || [], max: 0 })
        for (const g of (n.gpus || []))
            out.push({ key: "gpu:" + g.card, title: "GPU · " + gpuName(g.card), sub: g.busy + "%",
                       values: (h.gpus[g.card] || {}).busy || [], max: 100 })
        return out
    }
    readonly property var sel: items.find(i => i.key === selected) || items[0] || ({})

    PageHeader { title: "Resources"; subtitle: "Live usage over the last minute"; status: "Live" }

    RowLayout {
        Layout.fillWidth: true
        spacing: 16

        // ---- list
        ColumnLayout {
            Layout.preferredWidth: page.pageWidth >= 900 ? 300 : 220
            Layout.maximumWidth: Layout.preferredWidth
            Layout.alignment: Qt.AlignTop
            spacing: 8
            Repeater {
                model: LiveModel { values: page.items }
                AbstractButton {
                    Layout.fillWidth: true
                    implicitHeight: 76
                    focusPolicy: Qt.StrongFocus
                    Accessible.name: modelData.title
                    onClicked: page.selected = modelData.key
                    background: Rectangle {
                        radius: theme.radius
                        color: page.sel.key === modelData.key ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.14) : theme.panel
                        border.color: page.sel.key === modelData.key || parent.visualFocus ? theme.accent : theme.border
                    }
                    contentItem: RowLayout {
                        spacing: 10
                        HistoryChart {
                            Layout.preferredWidth: 72; Layout.preferredHeight: 48; Layout.leftMargin: 10
                            grid: false; values: modelData.values; values2: modelData.values2 || []
                            maxValue: modelData.max; length: usage.historyLength
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Label { text: modelData.title; color: theme.text; font.pixelSize: 13; elide: Text.ElideRight; Layout.fillWidth: true }
                            Label { text: modelData.sub; color: theme.muted; font.pixelSize: 12; elide: Text.ElideRight; Layout.fillWidth: true }
                        }
                    }
                }
            }
        }

        // ---- detail
        Panel {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            title: page.sel.title || ""
            subtitle: page.sel.key === "cpu" ? page.sp.name
                      : page.sel.key === "memory" ? "Percentage of memory in use"
                      : (page.sel.key || "").startsWith("disk:") ? "Active time (share of the second the disk was busy)"
                      : (page.sel.key || "").startsWith("net:") ? "Download (filled) and upload (line)"
                      : "Graphics engine busy"
            Segmented {
                visible: page.sel.key === "cpu"
                Layout.fillWidth: true
                model: ["Overall utilization", "Logical processors"]
                currentIndex: page.logical ? 1 : 0
                onActivated: (ix) => page.logical = ix === 1
            }
            HistoryChart {
                visible: !(page.sel.key === "cpu" && page.logical)
                Layout.fillWidth: true
                implicitHeight: 260
                values: page.sel.values || []; values2: page.sel.values2 || []
                maxValue: page.sel.max === undefined ? 100 : page.sel.max
                length: usage.historyLength
            }
            // one small graph per logical processor, laid out in the space of the big chart
            GridLayout {
                id: threads
                visible: page.sel.key === "cpu" && page.logical
                Layout.fillWidth: true
                readonly property int count: (page.h.cores || []).length
                // the column count (preferring one that divides evenly) whose cells come closest
                // to a 16:10 shape inside the 260 px the overall chart uses
                columns: {
                    if (count < 2 || width <= 0) return Math.max(1, count)
                    let best = 1, bestScore = Infinity
                    for (let c = 1; c <= count; c++) {
                        const r = Math.ceil(count / c)
                        const score = Math.abs(Math.log((width / c) / (260 / r) / 1.6)) + (count % c ? 0.35 : 0)
                        if (score < bestScore) { bestScore = score; best = c }
                    }
                    return best
                }
                readonly property int rows: Math.ceil(count / Math.max(1, columns))
                columnSpacing: 6; rowSpacing: 6; uniformCellWidths: true
                Repeater {
                    model: threads.visible ? threads.count : 0
                    HistoryChart {
                        required property int index
                        readonly property var cpu: page.n.cpu || ({})
                        Layout.fillWidth: true
                        implicitHeight: Math.max(40, (260 - threads.rowSpacing * (threads.rows - 1)) / threads.rows)
                        grid: false
                        values: page.h.cores[index] || []
                        length: usage.historyLength
                        Label {
                            x: 5; y: 3
                            width: parent.width - 10
                            text: "CPU " + parent.index + "  " + ((parent.cpu.cores || [])[parent.index] || 0) + "%"
                                  + (parent.width >= 110 ? "  " + (((parent.cpu.mhz || [])[parent.index] || 0) / 1000).toFixed(1) + " GHz" : "")
                            color: theme.muted; font.pixelSize: 10; elide: Text.ElideRight
                        }
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Label { text: "60 seconds"; color: theme.muted; font.pixelSize: 11; Layout.fillWidth: true }
                Label { text: page.sel.max === 0 ? "scaled to the peak" : "100%"; color: theme.muted; font.pixelSize: 11 }
            }

            // stats for the selected resource
            GridLayout {
                Layout.fillWidth: true
                columns: page.pageWidth >= 1100 ? 4 : 2
                columnSpacing: 12; rowSpacing: 12; uniformCellWidths: true
                readonly property string k: page.sel.key || ""
                readonly property var disk: k.startsWith("disk:") ? (page.n.disks || []).find(d => "disk:" + d.name === k) : null
                readonly property var net: k.startsWith("net:") ? (page.n.nets || []).find(a => "net:" + a.device === k) : null
                readonly property var gpu: k.startsWith("gpu:") ? (page.n.gpus || []).find(g => "gpu:" + g.card === k) : null
                readonly property var mem: page.n.memory || ({})

                // CPU
                MetricCard { visible: parent.k === "cpu"; Layout.fillWidth: true; icon: "gauge"; label: "Utilization"
                             value: page.n.cpu ? page.n.cpu.total : "—"; unit: "%" }
                MetricCard { visible: parent.k === "cpu"; Layout.fillWidth: true; icon: "activity"; label: "Speed"
                             value: page.n.cpu && page.n.cpu.mhz.length ? (page.n.cpu.mhz.reduce((a, b) => a + b, 0) / page.n.cpu.mhz.length / 1000).toFixed(2) : "—"
                             unit: "GHz"; detail: "Base " + (page.sp.baseMhz / 1000).toFixed(2) + " GHz" }
                MetricCard { visible: parent.k === "cpu"; Layout.fillWidth: true; icon: "cpu"; label: "Cores"
                             value: page.sp.cores || "—"; detail: (page.sp.threads || 0) + " logical processors" }
                MetricCard { visible: parent.k === "cpu"; Layout.fillWidth: true; icon: "thermometer"; label: "Temperature"
                             value: system.live.cpuTemp !== null && system.live.cpuTemp !== undefined ? Math.round(system.live.cpuTemp) : "—"; unit: "°C" }
                MetricCard { visible: parent.k === "cpu"; Layout.fillWidth: true; icon: "layout-grid"; label: "Processes"
                             value: page.n.cpu ? page.n.cpu.processes : "—"; detail: page.n.cpu ? page.n.cpu.threads + " threads" : "" }
                MetricCard { visible: parent.k === "cpu"; Layout.fillWidth: true; icon: "activity"; label: "Up time"
                             value: page.n.cpu ? page.uptime(page.n.cpu.uptime) : "—"; detail: "days:hours:minutes:seconds" }
                MetricCard { visible: parent.k === "cpu"; Layout.fillWidth: true; icon: "zap"; label: "Max boost"
                             value: page.sp.maxMhz ? (page.sp.maxMhz / 1000).toFixed(2) : "—"; unit: "GHz"
                             detail: page.sp.boost === false ? "Boost is off" : "Boost on" }
                MetricCard { visible: parent.k === "cpu"; Layout.fillWidth: true; icon: "box"; label: "Virtualization"
                             value: page.sp.virtualization ? (page.sp.virtualizationEnabled ? "Enabled" : "Disabled") : "None"
                             detail: page.sp.virtualization ? page.sp.virtualization + (page.sp.virtualizationEnabled ? "" : " · off in the BIOS") : "Not supported" }
                // Memory
                MetricCard { visible: parent.k === "memory"; Layout.fillWidth: true; icon: "memory-stick"; label: "In use"
                             value: page.gib(parent.mem.used); unit: "GiB"; detail: "of " + page.gib(parent.mem.total) + " GiB" }
                MetricCard { visible: parent.k === "memory"; Layout.fillWidth: true; icon: "check"; label: "Available"
                             value: page.gib(parent.mem.available); unit: "GiB" }
                MetricCard { visible: parent.k === "memory"; Layout.fillWidth: true; icon: "layout-grid"; label: "Cache"
                             value: page.gib(parent.mem.cached); unit: "GiB"; detail: "Given back when apps need it" }
                MetricCard { visible: parent.k === "memory"; Layout.fillWidth: true; icon: "refresh-cw"; label: "Swap in use"
                             value: page.gib(parent.mem.swap_used); unit: "GiB"; detail: "of " + page.gib(parent.mem.swap_total) + " GiB" }
                // Disk
                MetricCard { visible: !!parent.disk; Layout.fillWidth: true; icon: "gauge"; label: "Active time"
                             value: parent.disk ? Math.round(parent.disk.active) : "—"; unit: "%" }
                MetricCard { visible: !!parent.disk; Layout.fillWidth: true; icon: "arrow-down"; label: "Read"
                             value: parent.disk ? page.rate(parent.disk.read).split(" ")[0] : "—"; unit: parent.disk ? page.rate(parent.disk.read).split(" ")[1] : "" }
                MetricCard { visible: !!parent.disk; Layout.fillWidth: true; icon: "arrow-up"; label: "Write"
                             value: parent.disk ? page.rate(parent.disk.write).split(" ")[0] : "—"; unit: parent.disk ? page.rate(parent.disk.write).split(" ")[1] : "" }
                MetricCard { visible: !!parent.disk; Layout.fillWidth: true; icon: "hard-drive"; label: "Capacity"
                             value: parent.disk ? Math.round(parent.disk.size / 1e9) : "—"; unit: "GB"
                             detail: parent.disk ? parent.disk.kind + " · firmware " + parent.disk.firmware : "" }
                // Network
                MetricCard { visible: !!parent.net; Layout.fillWidth: true; icon: "arrow-down"; label: "Download"
                             value: parent.net ? page.rate(parent.net.rx, true).split(" ")[0] : "—"; unit: parent.net ? page.rate(parent.net.rx, true).split(" ")[1] : "" }
                MetricCard { visible: !!parent.net; Layout.fillWidth: true; icon: "arrow-up"; label: "Upload"
                             value: parent.net ? page.rate(parent.net.tx, true).split(" ")[0] : "—"; unit: parent.net ? page.rate(parent.net.tx, true).split(" ")[1] : "" }
                // GPU
                MetricCard { visible: !!parent.gpu; Layout.fillWidth: true; icon: "gauge"; label: "Busy"
                             value: parent.gpu ? parent.gpu.busy : "—"; unit: "%" }
                MetricCard { visible: !!parent.gpu; Layout.fillWidth: true; icon: "memory-stick"; label: "Video memory"
                             value: parent.gpu ? page.gib(parent.gpu.vramUsed) : "—"; unit: "GiB"
                             detail: parent.gpu ? "of " + page.gib(parent.gpu.vramTotal) + " GiB" : "" }
            }

            // CPU: caches, like the spec list under Task Manager's stats
            Repeater {
                model: LiveModel { values: page.sel.key === "cpu" ? (page.sp.caches || []) : [] }
                KeyValue {
                    readonly property real kib: modelData.size * modelData.instances / 1024
                    key: "L" + modelData.level + " cache" + (modelData.type === "Unified" ? "" : " (" + modelData.type.toLowerCase() + ")")
                    value: (kib >= 1024 ? (kib / 1024) + " MiB" : kib + " KiB")
                           + (modelData.instances > 1 ? " · " + modelData.instances + " × " + (modelData.size >= 1048576
                              ? modelData.size / 1048576 + " MiB" : modelData.size / 1024 + " KiB") : "")
                }
            }
        }
    }
}
