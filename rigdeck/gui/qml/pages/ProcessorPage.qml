import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    readonly property var c: system.info.cpu || ({})
    readonly property var sp: usage.specs
    readonly property var l: system.live
    readonly property var h: usage.history
    readonly property var n: usage.now.cpu || ({})
    function fmt(v, d) { return (v === null || v === undefined) ? "—" : Number(v).toLocaleString(Qt.locale(), "f", d || 0) }
    function ghz(mhz) { return mhz ? (mhz / 1000).toFixed(2) + " GHz" : "—" }
    function bytes(b) { return b >= 1048576 ? (b / 1048576) + " MiB" : (b / 1024) + " KiB" }

    PageHeader {
        title: page.sp.name || page.c.name || "Processor"
        subtitle: page.sp.cores + " cores · " + page.sp.threads + " threads · " + (page.sp.driver || "")
                  + (page.sp.governor ? " (" + page.sp.governor + ")" : "")
        status: "Live"
    }
    GridLayout {
        Layout.fillWidth: true
        columns: page.pageWidth >= 900 ? 4 : page.pageWidth >= 520 ? 2 : 1
        columnSpacing: 12; rowSpacing: 12; uniformCellWidths: true
        MetricCard { Layout.fillWidth: true; icon: "thermometer"; label: "Temperature"; value: page.fmt(page.l.cpuTemp); unit: "°C" }
        MetricCard { Layout.fillWidth: true; icon: "gauge"; label: "Load"; value: page.fmt(page.n.total); unit: "%" }
        MetricCard { Layout.fillWidth: true; icon: "activity"; label: "Average clock"; value: page.fmt(page.l.cpuMhz / 1000, 2); unit: "GHz"
                     detail: "Base " + page.ghz(page.sp.baseMhz) }
        MetricCard { Layout.fillWidth: true; icon: "zap"; label: "Max boost"; value: page.fmt(page.sp.maxMhz / 1000, 2); unit: "GHz"
                     detail: page.sp.boost === false ? "Boost is off" : "Boost on" }
    }

    // ---- total load over the last minute
    Panel {
        Layout.fillWidth: true
        title: "Utilization"
        subtitle: "All threads, last 60 seconds"
        HistoryChart { Layout.fillWidth: true; implicitHeight: 140; values: page.h.cpu || []; length: usage.historyLength }
    }

    // ---- one small chart per logical processor (like Task Manager's "logical processors" view)
    Panel {
        Layout.fillWidth: true
        title: "Logical processors"
        subtitle: "Load of each thread over the last minute, with its current clock"
        GridLayout {
            Layout.fillWidth: true
            columns: page.pageWidth >= 1100 ? 8 : page.pageWidth >= 760 ? 4 : 2
            columnSpacing: 10; rowSpacing: 10; uniformCellWidths: true
            Repeater {
                model: (page.h.cores || []).length
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: "CPU " + index; color: theme.muted; font.pixelSize: 11; Layout.fillWidth: true }
                        Label { text: ((page.n.cores || [])[index] || 0) + "% · " + page.fmt(((page.n.mhz || [])[index] || 0) / 1000, 1) + " GHz"
                                color: theme.text; font.pixelSize: 11 }
                    }
                    HistoryChart {
                        Layout.fillWidth: true
                        implicitHeight: 54
                        grid: false
                        values: page.h.cores[index] || []
                        length: usage.historyLength
                    }
                }
            }
        }
    }

    // ---- specifications
    Panel {
        Layout.fillWidth: true
        title: "Specifications"
        KeyValue { key: "Model"; value: page.sp.name || "" }
        KeyValue { key: "Cores / threads"; value: page.sp.cores + " / " + page.sp.threads
                                                  + (page.sp.smt ? " (SMT on)" : page.sp.threads > page.sp.cores ? " (SMT off)" : "") }
        KeyValue { key: "Clock"; value: "base " + page.ghz(page.sp.baseMhz) + " · boost up to " + page.ghz(page.sp.maxMhz)
                                        + " · lowest " + page.ghz(page.sp.minMhz) }
        Repeater {
            model: page.sp.caches || []
            KeyValue {
                key: "L" + modelData.level + " cache" + (modelData.type === "Unified" ? "" : " (" + modelData.type.toLowerCase() + ")")
                value: page.bytes(modelData.size * modelData.instances)
                       + (modelData.instances > 1 ? " (" + modelData.instances + " × " + page.bytes(modelData.size) + ")" : "")
            }
        }
        KeyValue { key: "Virtualization"; value: page.sp.virtualization
                   ? page.sp.virtualization + (page.sp.virtualizationEnabled ? " — enabled" : " — disabled in the BIOS") : "not supported" }
        KeyValue { key: "Instruction sets"; value: (page.sp.isa || []).join(", ") }
        KeyValue { key: "Frequency driver"; value: [page.sp.driver, page.sp.pstate ? "mode " + page.sp.pstate : "",
                                                    page.sp.governor ? "governor " + page.sp.governor : "",
                                                    page.sp.epp ? "energy preference " + page.sp.epp : ""].filter(t => t).join(" · ") }
        KeyValue { key: "Microcode"; value: page.sp.microcode || "" }
    }
}
