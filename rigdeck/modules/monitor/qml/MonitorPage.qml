import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    readonly property var mons: monitor.monitors
    readonly property bool ok: monitor.status === "ok"
    readonly property var withBrightness: mons.filter(m => m.controls.some(c => c.key === "brightness"))

    Connections { target: monitor; function onToast(m) { root.showToast(m) } }
    onShownChanged: if (shown) monitor.refresh()

    PageHeader {
        title: "Monitors"
        subtitle: page.ok ? page.mons.map(m => m.name).join(" · ") + " · settings are stored in each monitor" : ""
        status: ({ ok: page.mons.length + (page.mons.length === 1 ? " monitor" : " monitors"), none: "None found",
                   loading: "Looking…", "not-installed": "Setup needed", error: "Error" })[monitor.status]
        tone: page.ok ? theme.live : monitor.status === "error" ? theme.error : theme.warning
    }

    Banner {
        visible: monitor.status === "not-installed"
        text: "Monitor controls use ddcutil, which isn't installed. On Arch/CachyOS: sudo pacman -S ddcutil — "
              + "then log out and back in."
        buttonText: "Open ddcutil page"
        onClicked: appState.openUrl("https://www.ddcutil.com/install/")
    }
    Banner {
        visible: monitor.status === "none"
        text: "No monitor answered. Make sure DDC/CI is turned on in each monitor's own menu (often under "
              + "Settings or OSD). Laptop screens and some TVs don't support it."
        buttonText: "Check again"
        onClicked: monitor.refresh()
    }
    Banner {
        visible: monitor.status === "error"
        tone: "error"
        text: monitor.error
        buttonText: "Retry"
        onClicked: monitor.refresh()
    }

    // ---- all monitors at once
    Panel {
        Layout.fillWidth: true
        visible: page.withBrightness.length > 1
        title: "All monitors"
        SettingRow {
            title: "Brightness"
            description: "Sets every monitor to the same brightness"
            Slider {
                id: all
                Layout.preferredWidth: 240
                from: 0; to: 100; stepSize: 1
                value: page.withBrightness.length
                       ? Math.round(page.withBrightness.reduce((s, m) => {
                             const c = m.controls.find(c => c.key === "brightness"); return s + 100 * c.value / c.max }, 0)
                         / page.withBrightness.length) : 0
                Accessible.name: "Brightness of all monitors"
                onPressedChanged: if (!pressed) monitor.setAllBrightness(Math.round(value))
            }
            Label { text: Math.round(all.value) + "%"; color: theme.text; font.pixelSize: 13
                    Layout.preferredWidth: 44; horizontalAlignment: Text.AlignRight }
        }
    }

    // ---- one panel per monitor
    Repeater {
        model: page.mons
        Panel {
            id: mon
            readonly property int mi: index
            Layout.fillWidth: true
            title: modelData.name
            subtitle: modelData.connector + (modelData.serial ? " · serial " + modelData.serial : "")
            enabled: monitor.confirmSeconds === 0

            Repeater {
                model: modelData.controls
                SettingRow {
                    id: row
                    readonly property var c: modelData
                    title: c.label
                    description: c.key === "input" ? "Names come from the monitor and may not match its ports. "
                                                     + "Switches back after " + 10 + " s unless you keep it."
                               : c.key === "volume" ? "The monitor's speakers or its headphone jack" : ""
                    Slider {
                        id: sl
                        visible: row.c.kind === "range"
                        Layout.preferredWidth: 240
                        from: 0; to: row.c.max || 100; stepSize: 1
                        value: row.c.value
                        Accessible.name: mon.title + " " + row.c.label
                        onPressedChanged: if (!pressed) monitor.set(mon.mi, row.c.code, Math.round(value))
                    }
                    Label {
                        visible: row.c.kind === "range"
                        text: Math.round(sl.value) + (row.c.max === 100 ? "%" : " / " + row.c.max)
                        color: theme.text; font.pixelSize: 13
                        Layout.preferredWidth: 44; horizontalAlignment: Text.AlignRight
                    }
                    Toggle {
                        visible: row.c.kind === "switch"
                        checked: row.c.value === 1
                        Accessible.name: mon.title + " " + row.c.label
                        onToggled: monitor.set(mon.mi, row.c.code, checked ? 1 : 0)
                    }
                    ComboBox {
                        visible: row.c.kind === "choice"
                        Layout.preferredWidth: 200
                        model: (row.c.options || []).map(o => o.label)
                        currentIndex: (row.c.options || []).findIndex(o => o.value === row.c.value)
                        Accessible.name: mon.title + " " + row.c.label
                        onActivated: (ix) => row.c.key === "input" ? monitor.setInput(mon.mi, row.c.options[ix].value)
                                                                   : monitor.set(mon.mi, row.c.code, row.c.options[ix].value)
                    }
                }
            }
        }
    }

    // ---- "keep this input?" (reverts by itself, in case the screen went black)
    Dialog {
        visible: monitor.confirmSeconds > 0
        anchors.centerIn: Overlay.overlay
        modal: true
        closePolicy: Popup.NoAutoClose
        title: "Keep the new input on " + monitor.confirmName + "?"
        Label {
            text: "If that screen went black, just wait — it switches back in " + monitor.confirmSeconds + " s."
            color: theme.text
            wrapMode: Text.WordWrap
        }
        footer: DialogButtonBox {
            Button { text: "Switch back"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            Button { text: "Keep"; highlighted: true; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
            onAccepted: monitor.keepInput(true)
            onRejected: monitor.keepInput(false)
        }
    }
}
