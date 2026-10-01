import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    readonly property var g: (system.info.gpus && system.info.gpus.length) ? system.info.gpus[0] : ({})
    readonly property var t: system.live.gpu || {}
    readonly property var i: gpu.info
    readonly property bool ok: gpu.status === "ok"
    readonly property bool canFan: ok && i.fanControls === true
    readonly property var f: gpu.fan
    function fmt(v, d) { return (v === null || v === undefined) ? "—" : Number(v).toLocaleString(Qt.locale(), "f", d || 0) }
    function gib(b) { return b ? (b / 1073741824).toFixed(1) : "—" }
    readonly property var zeroRange: (i.zeroRpmRange && i.zeroRpmRange.length === 2) ? i.zeroRpmRange : [0, 100]

    Connections { target: gpu; function onToast(m) { root.showToast(m) } }

    PageHeader {
        title: page.g.name ? page.g.name.replace(/\s*\(.*\)\s*$/, "") : (page.i.name || "Graphics")
        subtitle: [page.g.kernel_driver, system.info.mesa ? "Mesa " + system.info.mesa : "",
                   page.ok ? "LACT " + page.i.lact : ""].filter(s => s).join(" · ")
        status: page.ok ? (page.canFan ? "Controls ready" : "Monitoring") : "Monitoring"
        tone: page.canFan ? theme.live : theme.warning
    }

    // ---- setup states, each with one fix
    Banner {
        visible: gpu.status === "not-installed"
        text: "GPU controls use LACT's background service, which isn't installed. "
              + "On Arch/CachyOS: sudo pacman -S lact — other distros: see lact's GitHub page."
        buttonText: "Open LACT page"
        onClicked: appState.openUrl("https://github.com/ilya-zlobintsev/LACT#installation")
    }
    Banner {
        visible: gpu.status === "not-running"
        text: "LACT is installed but its service (lactd) isn't running."
        buttonText: "Start LACT"
        onClicked: gpu.startLact()
    }
    Banner {
        visible: gpu.status === "no-permission"
        tone: "error"
        text: "You don't have permission to talk to LACT. Add your user to the 'wheel' group, then log out and back in."
    }
    Banner {
        visible: gpu.status === "error"
        tone: "error"
        text: "LACT reported an error: " + gpu.error
        buttonText: "Retry"
        onClicked: gpu.refresh()
    }
    Banner {
        visible: page.ok && !page.canFan && !gpu.rebootNeeded
        text: "Fan control is locked: AMD's overdrive switch is off in the driver. Enabling it adds one kernel "
              + "option" + (page.i.overdriveMethod === "limine" ? " (via Limine)" : "") + " and needs a restart."
        buttonText: "Enable GPU controls"
        onClicked: gpu.enableControls()
    }
    Banner {
        visible: gpu.rebootNeeded
        tone: "info"
        text: "GPU controls are enabled — restart your PC to unlock fan control."
    }

    // ---- live numbers
    GridLayout {
        Layout.fillWidth: true
        columns: page.pageWidth >= 900 ? 4 : page.pageWidth >= 520 ? 2 : 1
        columnSpacing: 12; rowSpacing: 12; uniformCellWidths: true
        MetricCard { Layout.fillWidth: true; icon: "thermometer"; label: "Core (edge)"; value: page.fmt(page.t.temp_edge); unit: "°C"
                     detail: page.t.temp_junction ? "Hotspot " + page.fmt(page.t.temp_junction) + " °C" : "" }
        MetricCard { Layout.fillWidth: true; icon: "memory-stick"; label: "Memory"; value: page.fmt(page.t.temp_mem); unit: "°C"
                     valueColor: page.t.temp_mem >= 90 ? theme.error : page.t.temp_mem >= 80 ? theme.warning : theme.text
                     detail: page.gib(page.t.vram_used) + " / " + page.gib(page.t.vram_total) + " GiB VRAM used" }
        MetricCard { Layout.fillWidth: true; icon: "fan"; label: "Fans"; value: page.fmt(page.t.fan_rpm); unit: "RPM"
                     detail: page.t.fan_rpm === 0 ? "Stopped (zero-RPM)" : (page.ok && page.i.pwm !== null ? page.i.pwm + "% speed" : "") }
        MetricCard { Layout.fillWidth: true; icon: "zap"; label: "Power"; value: page.fmt(page.t.power_w); unit: "W"
                     detail: page.t.power_cap_w ? "Limit " + page.fmt(page.t.power_cap_w) + " W" : "" }
        MetricCard { Layout.fillWidth: true; icon: "gauge"; label: "Usage"; value: page.fmt(page.t.busy); unit: "%" }
        MetricCard { Layout.fillWidth: true; icon: "activity"; label: "Core clock"; value: page.fmt(page.t.sclk_mhz); unit: "MHz" }
        MetricCard { Layout.fillWidth: true; icon: "activity"; label: "Memory clock"; value: page.fmt(page.t.mclk_mhz); unit: "MHz" }
    }

    // ---- fan
    Panel {
        Layout.fillWidth: true
        title: "Fan"
        subtitle: page.canFan ? "Applied by LACT and kept across reboots" : "Unavailable until GPU controls are enabled"
        enabled: page.canFan
        Segmented {
            Layout.fillWidth: true
            model: ["Automatic", "Custom curve", "Fixed speed"]
            currentIndex: ["auto", "curve", "static"].indexOf(page.f.mode)
            onActivated: (ix) => gpu.setFanMode(["auto", "curve", "static"][ix])
        }

        // zero-RPM (RDNA3/4 firmware option; works with every mode)
        RowLayout {
            Layout.fillWidth: true
            visible: page.i.zeroRpmSupported === true
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Label { text: "Zero RPM"; color: theme.text; font.pixelSize: 14; Layout.fillWidth: true }
                Label { text: page.f.zero_rpm ? "Fans stop completely while the GPU is cool"
                                              : "Fans always spin — better for hot weather and memory temperature"
                        color: theme.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            }
            Toggle { checked: page.f.zero_rpm === true; Accessible.name: "Zero RPM"
                     onToggled: gpu.setZeroRpm(checked) }
        }
        RowLayout {
            Layout.fillWidth: true
            visible: page.i.zeroRpmSupported === true && page.f.zero_rpm === true && (page.i.zeroRpmRange || []).length === 2
            Label { text: "Stop fans below"; color: theme.muted; font.pixelSize: 13; Layout.preferredWidth: 130 }
            Slider {
                id: zt
                Layout.fillWidth: true
                from: page.zeroRange[0]; to: page.zeroRange[1]; stepSize: 1
                value: page.f.zero_rpm_temp || from
                Accessible.name: "Zero RPM stop temperature"
                onMoved: gpu.setZeroRpmTemp(value)
            }
            Label { text: Math.round(zt.value) + " °C"; color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 50 }
        }

        Label {
            visible: page.f.mode === "auto"
            text: "The driver controls the fans" + (page.i.zeroRpmSupported ? "; the switch above decides whether they may stop." : ".")
            color: theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true
        }
        ColumnLayout {
            visible: page.f.mode === "curve"
            Layout.fillWidth: true
            spacing: 6
            Label { text: "Drag the points (or Tab to the chart and use the arrow keys). X: GPU temperature, Y: fan speed."
                    color: theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            CurveChart {
                Layout.fillWidth: true
                points: gpu.fanCurve
                editable: true
                rpmMax: 100; yStep: 25; ySuffix: "%"
                onPointMoved: (ix, tt, pct) => gpu.setCurvePoint(ix, tt, pct)
            }
        }
        RowLayout {
            visible: page.f.mode === "static"
            Layout.fillWidth: true
            Label { text: "Fan speed"; color: theme.muted; font.pixelSize: 13; Layout.preferredWidth: 130 }
            Slider { id: fixed; Layout.fillWidth: true; from: 0; to: 100; stepSize: 5; value: page.f.speed
                     Accessible.name: "Fixed fan speed"; onMoved: gpu.setFixedSpeed(value) }
            Label { text: Math.round(fixed.value) + "%"; color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 50 }
        }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Button { text: "Revert"; enabled: gpu.fanDirty; onClicked: gpu.revertFan() }
            Button { text: "Apply"; highlighted: true; enabled: gpu.fanDirty; onClicked: gpu.applyFan() }
        }
    }

    // ---- power limit
    Panel {
        Layout.fillWidth: true
        title: "Power limit"
        subtitle: page.ok && page.i.capMin ? "Default " + page.fmt(page.i.capDefault) + " W · allowed "
                                             + page.fmt(page.i.capMin) + "–" + page.fmt(page.i.capMax) + " W"
                                           : "Unavailable"
        enabled: page.ok && page.i.capMin !== undefined && page.i.capMin !== null
        RowLayout {
            Layout.fillWidth: true
            Slider {
                id: cap
                Layout.fillWidth: true
                from: page.i.capMin || 0; to: page.i.capMax || 1; stepSize: 1
                value: gpu.powerCap
                Accessible.name: "Power limit in watts"
                onMoved: gpu.setPowerCap(value)
            }
            Label { text: Math.round(cap.value) + " W"; color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 56 }
        }
        Label {
            text: "Lower saves power and heat with a small performance cost; higher can add a few percent of speed."
            color: theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true
        }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Button { text: "Reset to default"; onClicked: gpu.resetPower() }
            Button { text: "Apply"; highlighted: true; enabled: Math.round(gpu.powerCap) !== Math.round(page.i.capNow || 0)
                     onClicked: gpu.applyPower() }
        }
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
        KeyValue { key: "Overdrive"; value: page.ok ? (page.i.overdrive ? "enabled" : "disabled") : "unknown" }
        KeyValue { key: "Kernel"; value: system.info.kernel || "" }
    }

    // ---- "keep these settings?" (LACT reverts unless confirmed)
    Dialog {
        id: keep
        visible: gpu.confirmSeconds > 0
        anchors.centerIn: Overlay.overlay
        modal: true
        closePolicy: Popup.NoAutoClose
        title: "Keep the new power limit?"
        Label {
            text: "If the system misbehaves, do nothing — it reverts in " + gpu.confirmSeconds + " s."
            color: theme.text
            wrapMode: Text.WordWrap
        }
        footer: DialogButtonBox {
            Button { text: "Revert"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            Button { text: "Keep"; highlighted: true; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
            onAccepted: gpu.confirmPower(true)
            onRejected: gpu.confirmPower(false)
        }
    }
}
