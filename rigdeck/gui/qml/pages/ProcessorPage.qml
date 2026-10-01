import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    readonly property var c: system.info.cpu || ({})
    readonly property var l: system.live
    function fmt(v, d) { return (v === null || v === undefined) ? "—" : Number(v).toLocaleString(Qt.locale(), "f", d || 0) }

    PageHeader {
        title: page.c.name || "Processor"
        subtitle: page.c.cores + " cores · " + page.c.threads + " threads · " + (page.c.driver || "") +
                  (page.c.governor ? " (" + page.c.governor + ")" : "")
        status: "Live"
    }
    GridLayout {
        Layout.fillWidth: true
        columns: page.pageWidth >= 900 ? 4 : page.pageWidth >= 520 ? 2 : 1
        columnSpacing: 12; rowSpacing: 12; uniformCellWidths: true
        MetricCard { Layout.fillWidth: true; icon: "thermometer"; label: "Temperature"; value: page.fmt(page.l.cpuTemp); unit: "°C" }
        MetricCard { Layout.fillWidth: true; icon: "gauge"; label: "Load"; value: page.fmt(page.l.cpuLoad); unit: "%" }
        MetricCard { Layout.fillWidth: true; icon: "activity"; label: "Average clock"; value: page.fmt(page.l.cpuMhz / 1000, 2); unit: "GHz" }
        MetricCard { Layout.fillWidth: true; icon: "zap"; label: "Max boost"; value: page.fmt(page.c.max_mhz / 1000, 2); unit: "GHz" }
    }
    Panel {
        Layout.fillWidth: true
        title: "Threads"
        subtitle: "Load and clock of each logical CPU"
        GridLayout {
            Layout.fillWidth: true
            columns: page.pageWidth >= 760 ? 2 : 1
            columnSpacing: 24; rowSpacing: 10
            Repeater {
                model: page.l.coreLoads || []
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Label { text: "CPU " + index; color: theme.muted; font.pixelSize: 12; Layout.preferredWidth: 48 }
                    UsageBar { Layout.fillWidth: true; value: modelData / 100 }
                    Label { text: modelData + "%"; color: theme.text; font.pixelSize: 12; Layout.preferredWidth: 36
                            horizontalAlignment: Text.AlignRight }
                    Label { text: page.fmt((page.l.coreMhz || [])[index]) + " MHz"; color: theme.muted; font.pixelSize: 12
                            Layout.preferredWidth: 72; horizontalAlignment: Text.AlignRight }
                }
            }
        }
    }
}
