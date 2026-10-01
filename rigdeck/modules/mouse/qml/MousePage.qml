import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    readonly property var s: mouse.state
    readonly property bool ok: mouse.status === "ok"
    readonly property bool known: s.stages !== undefined     // last known settings, also while asleep
    readonly property var b: s.battery || null

    // DPI edits stay local until Apply (each write wears the mouse's flash a little)
    property var draft: []
    property int draftCount: 1
    readonly property bool dpiDirty: ok && (draftCount !== s.stageCount
        || draft.some((d, i) => i < draftCount && d !== s.stages[i]))
    function resetDraft() { if (ok) { draft = s.stages.slice(); draftCount = s.stageCount } }
    Connections {
        target: mouse
        function onToast(m) { root.showToast(m) }
        function onStateChanged() { if (!page.dpiDirty) page.resetDraft() }
    }
    Component.onCompleted: { resetDraft(); mouse.setActive(shown) }
    onShownChanged: mouse.setActive(shown)
    // a different mouse: its draft starts from its own stages
    Connections { target: mouse; function onMiceChanged() { page.draft = []; page.resetDraft() } }

    PageHeader {
        title: page.s.name || "Mouse"
        subtitle: page.s.connection ? (page.s.connection === "wireless" ? "Wireless receiver" : "USB cable")
                                      + " · settings are stored on the mouse" : ""
        status: ({ ok: page.b ? page.b.level + "% battery" : "Connected", asleep: "Asleep", none: "Not found",
                   loading: "Looking…", error: "Error" })[mouse.status]
        tone: page.ok ? (page.b && page.b.level < 15 && !page.b.charging ? theme.warning : theme.live)
                      : mouse.status === "error" ? theme.error : theme.warning
    }

    Segmented {
        Layout.fillWidth: true
        visible: mouse.mice.length > 1
        model: mouse.mice.map(m => m.name)
        currentIndex: mouse.index
        onActivated: (ix) => mouse.select(ix)
    }

    Banner {
        visible: mouse.status === "asleep"
        tone: "info"
        text: "The mouse is asleep (its receiver answers, the mouse doesn't). Move it to wake it — this page updates by itself."
              + (page.known ? " Showing its last known settings." : "")
    }
    Banner {
        visible: mouse.status === "none"
        text: "No supported mouse found. Supported: Pulsar Xlite V3 and Attack Shark X11 Ultra (wireless receiver or cable)."
    }
    Banner {
        visible: mouse.status === "error"
        tone: "error"
        text: mouse.error
        buttonText: "Retry"
        onClicked: mouse.refresh()
    }
    Banner {
        visible: page.ok && page.b !== null && page.b.level < 15 && !page.b.charging
        text: "Battery low (" + (page.b ? page.b.level : 0) + "%) — plug the mouse in to charge."
    }

    GridLayout {
        Layout.fillWidth: true
        visible: page.known
        columns: page.pageWidth >= 900 ? 3 : 1
        columnSpacing: 12; rowSpacing: 12; uniformCellWidths: true
        MetricCard {
            Layout.fillWidth: true
            icon: !page.b ? "battery" : page.b.charging ? "battery-charging" : page.b.level >= 70 ? "battery-full"
                  : page.b.level >= 30 ? "battery-medium" : "battery-low"
            label: "Battery"
            value: page.b ? page.b.level : "—"; unit: page.b ? "%" : ""
            detail: !page.b ? "Not reported" : page.b.charging ? "Charging" : (page.b.mv / 1000).toFixed(2) + " V"
        }
        MetricCard {
            Layout.fillWidth: true
            icon: "activity"; label: "Polling rate"
            value: page.s.rate ? page.s.rate.toLocaleString(Qt.locale(), "f", 0) : "—"; unit: "Hz"
            detail: "Up to " + (page.s.maxRate || 0).toLocaleString(Qt.locale(), "f", 0) + " Hz on this connection"
        }
        MetricCard {
            Layout.fillWidth: true
            icon: "gauge"; label: "Sensitivity"
            value: page.ok && page.s.stages ? page.s.stages[page.s.currentStage].toLocaleString(Qt.locale(), "f", 0) : "—"
            unit: "DPI"
            detail: page.ok ? "Stage " + (page.s.currentStage + 1) + " of " + page.s.stageCount : ""
        }
    }

    // ---- DPI stages
    Panel {
        Layout.fillWidth: true
        visible: page.known
        enabled: page.ok && !mouse.busy
        title: "Sensitivity (DPI)"
        subtitle: "The DPI button on the mouse cycles through these stages; the light shows which one is active"
        SettingRow {
            title: "Number of stages"
            Segmented {
                model: Array.from({ length: mouse.maxStages }, (_, i) => String(i + 1))
                currentIndex: page.draftCount - 1
                minChipWidth: 36
                onActivated: (ix) => page.draftCount = ix + 1
            }
        }
        Repeater {
            model: page.draftCount
            SettingRow {
                id: stageRow
                readonly property int n: index
                title: "Stage " + (n + 1) + (n === page.s.currentStage ? "  ·  active" : "")
                Rectangle { implicitWidth: 14; implicitHeight: 14; radius: 7; color: page.s.colors ? page.s.colors[stageRow.n] : "white"
                            border.color: theme.border }
                SpinBox {
                    from: page.s.dpiMin || 50; to: page.s.dpiMax || 26000
                    stepSize: value >= (page.s.dpiStepLimit || 30000) ? 100 : 50
                    editable: true
                    value: page.draft[stageRow.n] || 800
                    Accessible.name: "Stage " + (stageRow.n + 1) + " DPI"
                    onValueModified: { const d = page.draft.slice(); d[stageRow.n] = value; page.draft = d }
                }
                Button {
                    text: "Use"
                    enabled: stageRow.n !== page.s.currentStage && stageRow.n < page.s.stageCount
                    onClicked: mouse.setCurrentStage(stageRow.n)
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Label { text: "DPI is set in steps of 50" + ((page.s.dpiMax || 0) > (page.s.dpiStepLimit || 0)
                          ? " (100 above " + page.s.dpiStepLimit + ")" : "") + "."
                    color: theme.muted; font.pixelSize: 12; Layout.fillWidth: true }
            Button { text: "Revert"; enabled: page.dpiDirty; onClicked: page.resetDraft() }
            Button { text: "Apply"; highlighted: true; enabled: page.dpiDirty
                     onClicked: mouse.applyStages(page.draft, page.draftCount) }
        }
    }

    // ---- performance
    Panel {
        Layout.fillWidth: true
        visible: page.known
        enabled: page.ok && !mouse.busy
        title: "Performance"
        subtitle: "Saved on the mouse right away"
        SettingRow {
            title: "Polling rate"
            description: "How often the mouse reports its position. Higher is smoother but uses more battery and CPU."
            Segmented {
                model: mouse.rates.filter(r => r <= (page.s.maxRate || 1000)).map(r => r >= 1000 ? (r / 1000) + "K" : String(r))
                currentIndex: mouse.rates.filter(r => r <= (page.s.maxRate || 1000)).indexOf(page.s.rate)
                minChipWidth: 44
                onActivated: (ix) => mouse.setRate(mouse.rates.filter(r => r <= (page.s.maxRate || 1000))[ix])
            }
        }
        SettingRow {
            title: "Motion sync"
            description: "Lines up sensor readings with the polling rate: more consistent tracking, about 1 ms more delay"
            Toggle { checked: page.s.motionSync === true; Accessible.name: "Motion sync"
                     onToggled: mouse.setSwitch("motionSync", checked) }
        }
        SettingRow {
            title: "Angle snapping"
            description: "Straightens slightly wobbly lines; most players leave it off"
            Toggle { checked: page.s.angleSnap === true; Accessible.name: "Angle snapping"
                     onToggled: mouse.setSwitch("angleSnap", checked) }
        }
        SettingRow {
            title: "Ripple control"
            description: "Smooths jitter at very high DPI, at the cost of a little responsiveness"
            Toggle { checked: page.s.ripple === true; Accessible.name: "Ripple control"
                     onToggled: mouse.setSwitch("ripple", checked) }
        }
    }

    // ---- light
    Panel {
        Layout.fillWidth: true
        visible: page.known
        enabled: page.ok && !mouse.busy
        title: "Light"
        readonly property var led: page.s.led || ({})
        SettingRow {
            title: "Effect"
            Segmented {
                model: ["Off", "Steady", "Breathing"]
                currentIndex: !parent.parent.led.on ? 0 : parent.parent.led.mode === 2 ? 2 : 1
                onActivated: (ix) => mouse.setLed(ix === 0 ? { on: false } : { mode: ix })
            }
        }
        SettingRow {
            visible: parent.led.on === true && parent.led.mode === 1
            title: "Brightness"
            Slider { id: bri; Layout.preferredWidth: 220; from: 1; to: 10; stepSize: 1; value: parent.parent.led.brightness || 5
                     Accessible.name: "Light brightness"
                     onPressedChanged: if (!pressed) mouse.setLed({ brightness: Math.round(value) }) }
            Label { text: Math.round(bri.value) + " / 10"; color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 48 }
        }
        SettingRow {
            visible: parent.led.on === true && parent.led.mode === 2
            title: "Speed"
            Slider { id: spd; Layout.preferredWidth: 220; from: 1; to: 5; stepSize: 1; value: parent.parent.led.speed || 3
                     Accessible.name: "Breathing speed"
                     onPressedChanged: if (!pressed) mouse.setLed({ speed: Math.round(value) }) }
            Label { text: Math.round(spd.value) + " / 5"; color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 48 }
        }
    }

    Panel {
        Layout.fillWidth: true
        visible: page.known
        title: "Backup"
        subtitle: "RigDeck saves the mouse's settings before its first change; backups are in ~/.local/share/rigdeck/mouse-backups"
        RowLayout {
            Layout.fillWidth: true
            Label { text: "Restore one with: rigdeck mouse restore FILE"; color: theme.muted; font.pixelSize: 12
                    Layout.fillWidth: true }
            Button { text: "Back up now"; onClicked: mouse.backupNow() }
        }
    }
}
