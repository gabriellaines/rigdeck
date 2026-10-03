import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    readonly property var m: system.live.memory || ({})
    function gib(b) { return b === undefined ? "—" : (b / 1073741824).toLocaleString(Qt.locale(), "f", 1) }

    readonly property var mods: usage.modules
    PageHeader {
        title: "Memory"
        subtitle: page.mods.length
                  ? page.mods.length + " × " + page.mods[0].sizeGB + " GB " + page.mods[0].type
                    + (page.mods[0].xmpMTs ? "-" + page.mods[0].xmpMTs : "") + " · " + page.gib(page.m.total) + " GiB usable"
                  : page.gib(page.m.total) + " GiB installed"
        status: "Live"
    }
    GridLayout {
        Layout.fillWidth: true
        columns: page.pageWidth >= 900 ? 4 : page.pageWidth >= 520 ? 2 : 1
        columnSpacing: 12; rowSpacing: 12; uniformCellWidths: true
        MetricCard { Layout.fillWidth: true; icon: "memory-stick"; label: "In use"; value: page.gib(page.m.used); unit: "GiB"
                     detail: page.m.total ? Math.round(100 * page.m.used / page.m.total) + "% of " + page.gib(page.m.total) + " GiB" : "" }
        MetricCard { Layout.fillWidth: true; icon: "check"; label: "Available"; value: page.gib(page.m.available); unit: "GiB" }
        MetricCard { Layout.fillWidth: true; icon: "layout-grid"; label: "Cache"; value: page.gib(page.m.cached); unit: "GiB"
                     detail: "Freed automatically when apps need it" }
        MetricCard { Layout.fillWidth: true; icon: "refresh-cw"; label: "Swap in use"; value: page.gib(page.m.swap_used); unit: "GiB"
                     detail: "of " + page.gib(page.m.swap_total) + " GiB" }
    }
    Panel {
        Layout.fillWidth: true
        title: "Usage"
        UsageBar { Layout.fillWidth: true; implicitHeight: 10; radius: 5; value: page.m.total ? page.m.used / page.m.total : 0 }
        Label { text: "Apps use " + page.gib(page.m.used) + " GiB. Cache doesn't count as used: Linux keeps recently read files in spare memory and gives it back instantly."
                color: theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    }
    Panel {
        Layout.fillWidth: true
        title: "In use over the last minute"
        HistoryChart { Layout.fillWidth: true; implicitHeight: 120; values: usage.history.memory || []
                       length: usage.historyLength }
    }

    // ---- installed modules (from each module's SPD chip)
    Panel {
        Layout.fillWidth: true
        visible: page.mods.length > 0
        title: "Modules"
        subtitle: "What each memory stick reports about itself. The speed it actually runs at (XMP/EXPO) is set in the BIOS."
        GridLayout {
            Layout.fillWidth: true
            columns: page.pageWidth >= 900 ? 2 : 1
            columnSpacing: 12; rowSpacing: 12; uniformCellWidths: true
            Repeater {
                model: LiveModel { values: page.mods }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: col.implicitHeight + 28
                    radius: theme.radius
                    color: theme.raised
                    border.color: theme.border
                    ColumnLayout {
                        id: col
                        anchors.fill: parent; anchors.margins: 14
                        spacing: 4
                        Label { text: [modelData.maker, modelData.part].filter(t => t).join(" ")
                                color: theme.text; font.pixelSize: 14; font.weight: Font.DemiBold }
                        Label { text: [modelData.sizeGB ? modelData.sizeGB + " GB" : "", modelData.type, modelData.form,
                                       modelData.ranks ? modelData.ranks + (modelData.ranks === 1 ? " rank" : " ranks") : ""]
                                      .filter(t => t).join(" · ")
                                color: theme.muted; font.pixelSize: 12 }
                        KeyValue { visible: !!modelData.xmpMTs; key: "Rated (XMP)"
                                   value: (modelData.xmpMTs || "") + " MT/s at " + (modelData.xmpVolts || "") + " V" }
                        KeyValue { visible: !!modelData.jedecMTs; key: "Default (JEDEC)"; value: (modelData.jedecMTs || "") + " MT/s" }
                        KeyValue { key: "SPD address"; value: modelData.address }
                    }
                }
            }
        }
    }

    Panel {
        Layout.fillWidth: true
        visible: (page.m.zram || []).length > 0
        title: "Compressed swap (zram)"
        subtitle: "Swap that lives in RAM, compressed — no disk involved"
        Repeater {
            model: LiveModel { values: page.m.zram || [] }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6
                KeyValue { key: modelData.name + " holds"; value: page.gib(modelData.data) + " GiB of swapped data" }
                KeyValue { key: "Compressed to"; value: page.gib(modelData.compressed) + " GiB" + (modelData.compressed
                           ? "  (" + (modelData.data / modelData.compressed).toFixed(1) + "× smaller)" : "") }
                KeyValue { key: "RAM it really uses"; value: page.gib(modelData.ram_used) + " GiB" }
                KeyValue { key: "Algorithm"; value: modelData.algorithm }
            }
        }
    }
}
