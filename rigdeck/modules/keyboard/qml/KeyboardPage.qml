import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    readonly property var s: keyboard.state
    readonly property bool ok: keyboard.status === "ok"
    readonly property int bt: bluez.devices.filter(d => d.connected && d.category === "keyboard").length

    Connections { target: keyboard; function onToast(m) { root.showToast(m) } }

    PageHeader {
        title: page.s.name || "Keyboard"
        subtitle: page.ok ? "Firmware " + page.s.firmware + " · USB 046d:" + page.s.pid : ""
        status: ({ ok: "Connected", none: "Not found", loading: "Looking…", error: "Error" })[keyboard.status]
        tone: page.ok ? theme.live : keyboard.status === "error" ? theme.error : theme.warning
    }

    Banner {
        visible: keyboard.status === "none" && page.bt === 0
        text: "No supported keyboard found. Supported: Logitech G PRO X TKL RAPID (USB)."
    }
    Banner {
        visible: keyboard.status === "error"
        tone: "error"
        text: keyboard.error
        buttonText: "Retry"
        onClicked: keyboard.refresh()
    }

    Panel {
        Layout.fillWidth: true
        visible: page.ok && page.s.brightness !== undefined
        enabled: !keyboard.busy
        title: "Lighting"
        subtitle: "The colors and effects come from the keyboard's active profile"
        SettingRow {
            title: "Brightness"
            description: "0 turns the lighting off"
            Slider {
                id: bri
                Layout.preferredWidth: 240
                from: page.s.brightnessMin || 0; to: page.s.brightnessMax || 100; stepSize: 1
                value: page.s.brightness || 0
                Accessible.name: "Keyboard brightness"
                onPressedChanged: if (!pressed) keyboard.setBrightness(Math.round(value))
            }
            Label { text: Math.round(bri.value) === 0 ? "Off" : Math.round(bri.value) + "%"
                    color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 44; horizontalAlignment: Text.AlignRight }
        }
        RowLayout {
            Layout.fillWidth: true
            Label { text: "Presets"; color: theme.muted; font.pixelSize: 12; Layout.fillWidth: true }
            Repeater {
                model: keyboard.presets
                Button { text: modelData === 0 ? "Off" : modelData + "%"; onClicked: keyboard.setBrightness(modelData) }
            }
        }
    }

    Panel {
        id: ap
        Layout.fillWidth: true
        visible: page.ok
        enabled: !keyboard.busy
        title: "Actuation and Rapid Trigger"
        subtitle: "Each onboard profile (switch with Fn + F2 / F3 / F4) has its own. Turn on RigDeck settings to "
                  + "change a profile's; RigDeck re-applies them whenever that profile is in use."
        Label {
            visible: keyboard.analogStatus === "loading" && keyboard.analog.length === 0
            text: "Reading the keyboard…"; color: theme.muted; font.pixelSize: 13
        }

        // values are in 0.1 mm
        function mm(t) { return (t / 10).toFixed(1) + " mm" }
        function firstValue(groups) { return groups.length ? Math.round(parseFloat(groups[0].value) * 10) : 0 }
        function asMap(list) { const m = {}; for (const e of list) m[e.name] = e.value; return m }
        function save(n, c, patch) {
            const s = { actuation: c.actuation, rapid: c.rapid, keys: asMap(c.keys), rapidKeys: asMap(c.rapidKeys) }
            keyboard.setCustom(n, Object.assign(s, patch))
        }

        Repeater {
            model: keyboard.analog
            ColumnLayout {
                id: prof
                required property var modelData
                readonly property int n: modelData.index
                readonly property var c: keyboard.custom[n - 1]
                Layout.fillWidth: true
                Layout.topMargin: n > 1 ? 10 : 0
                spacing: 6

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Label { text: "Profile " + prof.n + "  ·  " + prof.modelData.keys
                                  + (prof.modelData.name ? "  ·  " + prof.modelData.name : "")
                            color: theme.text; font.pixelSize: 14; font.bold: true }
                    Chip { visible: page.s.activeProfile === prof.n; label: "In use" }
                    Item { Layout.fillWidth: true }
                    Label { text: "RigDeck settings"; color: theme.muted; font.pixelSize: 12 }
                    Toggle {
                        checked: !!prof.c
                        Accessible.name: "RigDeck settings for profile " + prof.n
                        onToggled: {
                            if (!checked) { keyboard.resetCustom(prof.n); return }
                            const a = ap.firstValue(prof.modelData.actuation) || 20
                            const r = prof.modelData.rapidTrigger.length === 1 && prof.modelData.rapidTrigger[0].all
                                      ? ap.firstValue(prof.modelData.rapidTrigger) : 0
                            keyboard.setCustom(prof.n, { actuation: a, rapid: r, keys: {}, rapidKeys: {} })
                        }
                    }
                }

                // the keyboard's own settings for this profile
                Repeater {
                    model: [{ label: "Actuation point", groups: prof.modelData.actuation },
                            { label: "Rapid Trigger", groups: prof.modelData.rapidTrigger }]
                    KeyValue {
                        required property var modelData
                        visible: !prof.c
                        key: modelData.label
                        value: modelData.groups.length === 0 ? "Off"
                               : modelData.groups.map(g => g.value + (g.all ? " (all keys)" : " — " + g.keys.join(" "))).join("\n")
                    }
                }

                // RigDeck's settings
                SettingRow {
                    visible: !!prof.c
                    title: "Actuation point"
                    description: "How far a key goes down before it counts as pressed (every key, unless set below)"
                    Slider { id: act; Layout.preferredWidth: 220; from: 1; to: 40; stepSize: 1
                             value: prof.c ? prof.c.actuation : 20
                             Accessible.name: "Actuation point, profile " + prof.n
                             onPressedChanged: if (!pressed) ap.save(prof.n, prof.c, { actuation: Math.round(value) }) }
                    Label { text: ap.mm(act.value); color: theme.text; font.pixelSize: 13
                            Layout.preferredWidth: 56; horizontalAlignment: Text.AlignRight }
                }
                SettingRow {
                    visible: !!prof.c
                    title: "Rapid Trigger"
                    description: "A key resets as soon as it starts coming up, and presses again as soon as it goes down"
                    Toggle { checked: !!prof.c && prof.c.rapid > 0
                             Accessible.name: "Rapid Trigger, profile " + prof.n
                             onToggled: ap.save(prof.n, prof.c, checked ? { rapid: 5 } : { rapid: 0, rapidKeys: {} }) }
                }
                SettingRow {
                    visible: !!prof.c && prof.c.rapid > 0
                    title: "Rapid Trigger sensitivity"
                    description: "How far a key has to move to reset or press again (smaller = more sensitive)"
                    Slider { id: rs; Layout.preferredWidth: 220; from: 1; to: 20; stepSize: 1
                             value: prof.c ? Math.max(1, prof.c.rapid) : 5
                             Accessible.name: "Rapid Trigger sensitivity, profile " + prof.n
                             onPressedChanged: if (!pressed) ap.save(prof.n, prof.c, { rapid: Math.round(value) }) }
                    Label { text: ap.mm(rs.value); color: theme.text; font.pixelSize: 13
                            Layout.preferredWidth: 56; horizontalAlignment: Text.AlignRight }
                }

                // per-key actuation
                Repeater {
                    model: prof.c ? prof.c.keys : []
                    SettingRow {
                        id: kr
                        required property var modelData
                        title: modelData.name
                        description: "Its own actuation point"
                        Slider { id: ks; Layout.preferredWidth: 220; from: 1; to: 40; stepSize: 1; value: kr.modelData.value
                                 Accessible.name: "Actuation point of " + kr.modelData.name
                                 onPressedChanged: if (!pressed) {
                                     const m = ap.asMap(prof.c.keys); m[kr.modelData.name] = Math.round(value)
                                     ap.save(prof.n, prof.c, { keys: m })
                                 } }
                        Label { text: ap.mm(ks.value); color: theme.text; font.pixelSize: 13
                                Layout.preferredWidth: 56; horizontalAlignment: Text.AlignRight }
                        Button { text: "Remove"; onClicked: {
                            const m = ap.asMap(prof.c.keys); delete m[kr.modelData.name]
                            ap.save(prof.n, prof.c, { keys: m })
                        } }
                    }
                }
                RowLayout {
                    visible: !!prof.c
                    Layout.fillWidth: true
                    Label { text: "Give a key its own actuation point"; color: theme.muted; font.pixelSize: 12
                            Layout.fillWidth: true }
                    ComboBox {
                        id: pick
                        Layout.preferredWidth: 140
                        model: prof.c ? keyboard.keyNames.filter(k => !prof.c.keys.some(e => e.name === k)) : []
                        Accessible.name: "Key"
                    }
                    Button { text: "Add"; enabled: pick.currentText !== ""; onClicked: {
                        const m = ap.asMap(prof.c.keys); m[pick.currentText] = prof.c.actuation
                        ap.save(prof.n, prof.c, { keys: m })
                    } }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 6
            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: theme.muted
                font.pixelSize: 12
                text: "RigDeck's settings live on top of the profile: without RigDeck running (or on another PC) the "
                      + "keyboard uses its own. Per-key Rapid Trigger: `rigdeck keyboard analog-set --rapid-key`."
            }
            Button {
                text: "Refresh"
                enabled: keyboard.analogStatus !== "loading"
                onClicked: { keyboard.refresh(); keyboard.refreshAnalog() }
            }
        }
    }

    BluetoothDevices { category: "keyboard"; label: "Bluetooth keyboards" }
}
