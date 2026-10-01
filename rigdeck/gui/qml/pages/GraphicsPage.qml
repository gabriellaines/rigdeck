import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    readonly property var g: (system.info.gpus && system.info.gpus.length) ? system.info.gpus[0] : ({})
    readonly property var t: system.live.gpu || {}
    function fmt(v, d) { return (v === null || v === undefined) ? "—" : Number(v).toLocaleString(Qt.locale(), "f", d || 0) }
    function gib(b) { return b ? (b / 1073741824).toFixed(1) : "—" }

    PageHeader {
        title: page.g.name ? page.g.name.replace(/\s*\(.*\)\s*$/, "") : "Graphics"
        subtitle: [page.g.kernel_driver, system.info.mesa ? "Mesa " + system.info.mesa : "", page.g.pci]
                  .filter(s => s).join(" · ")
        status: "Monitoring"
    }

    GridLayout {
        Layout.fillWidth: true
        columns: page.pageWidth >= 900 ? 4 : page.pageWidth >= 520 ? 2 : 1
        columnSpacing: 12; rowSpacing: 12; uniformCellWidths: true
        MetricCard { Layout.fillWidth: true; icon: "thermometer"; label: "Core (edge)"; value: page.fmt(page.t.temp_edge); unit: "°C"
                     detail: page.t.temp_junction ? "Hotspot " + page.fmt(page.t.temp_junction) + " °C" : "" }
        MetricCard { Layout.fillWidth: true; icon: "memory-stick"; label: "Memory"; value: page.fmt(page.t.temp_mem); unit: "°C"
                     detail: page.gib(page.t.vram_used) + " / " + page.gib(page.t.vram_total) + " GiB VRAM used" }
        MetricCard { Layout.fillWidth: true; icon: "fan"; label: "Fans"; value: page.fmt(page.t.fan_rpm); unit: "RPM"
                     detail: page.t.fan_rpm === 0 ? "Stopped (zero-RPM mode)" : "" }
        MetricCard { Layout.fillWidth: true; icon: "zap"; label: "Power"; value: page.fmt(page.t.power_w); unit: "W"
                     detail: page.t.power_cap_w ? "Limit " + page.fmt(page.t.power_cap_w) + " W" : "" }
        MetricCard { Layout.fillWidth: true; icon: "gauge"; label: "Usage"; value: page.fmt(page.t.busy); unit: "%" }
        MetricCard { Layout.fillWidth: true; icon: "activity"; label: "Core clock"; value: page.fmt(page.t.sclk_mhz); unit: "MHz" }
        MetricCard { Layout.fillWidth: true; icon: "activity"; label: "Memory clock"; value: page.fmt(page.t.mclk_mhz); unit: "MHz" }
    }

    Panel {
        Layout.fillWidth: true
        title: "Drivers"
        subtitle: "What renders your games and desktop"
        KeyValue { key: "Kernel driver"; value: page.g.kernel_driver || "" }
        KeyValue { key: "Vulkan driver"; value: [page.g.vulkan_driver, page.g.driver_version].filter(s => s).join(" — ") }
        KeyValue { key: "Mesa"; value: system.info.mesa || "" }
        KeyValue { key: "Vulkan API"; value: page.g.vulkan_api || "" }
        KeyValue { key: "VBIOS"; value: page.g.vbios || "" }
        KeyValue { key: "Kernel"; value: system.info.kernel || "" }
    }

    Banner {
        tone: "info"
        text: "Fan mode (including turning zero-RPM off), power limit and clock controls are coming in the GPU module."
    }
}
