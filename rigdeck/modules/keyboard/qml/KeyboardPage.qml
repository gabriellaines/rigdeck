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
        title: "Keys: actuation, Rapid Trigger and colours"
        subtitle: "Pick an onboard profile, select keys on the keyboard (click, Ctrl+click, or drag across them) "
                  + "and set them below. RigDeck re-applies its settings whenever that profile is in use."

        property int profile: page.s.activeProfile || 1
        property var selected: []
        readonly property var c: keyboard.custom[profile - 1]
        readonly property var p: keyboard.analog.find(x => x.index === profile)
        // values per key for the map; re-read when the settings or the keyboard data change
        property var values: ({})
        property var li: null              // RigDeck's colours for this profile, or null
        function reload() { values = keyboard.keyValues(profile); li = keyboard.lightingFor(profile) || null }
        onProfileChanged: { selected = []; reload() }
        Connections { target: keyboard; function onAnalogChanged() { ap.reload() } }
        Component.onCompleted: reload()

        function mm(t) { return (t / 10).toFixed(1) + " mm" }
        // the selection's common value, or -1 if the keys differ
        function common(field) {
            const vs = selected.map(n => values[n] ? values[n][field] : undefined)
            return vs.length && vs.every(v => v === vs[0]) ? vs[0] : -1
        }

        Label {
            visible: keyboard.analogStatus === "loading" && keyboard.analog.length === 0
            text: "Reading the keyboard…"; color: theme.muted; font.pixelSize: 13
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Segmented {
                model: keyboard.analog.map(x => "Profile " + x.index + " · " + x.keys
                                                + (page.s.activeProfile === x.index ? "  (in use)" : ""))
                currentIndex: ap.profile - 1
                onActivated: i => ap.profile = i + 1
            }
            Item { Layout.fillWidth: true }
            Label { text: "RigDeck settings"; color: theme.muted; font.pixelSize: 12 }
            Toggle {
                checked: !!ap.c
                Accessible.name: "RigDeck settings for profile " + ap.profile
                onToggled: checked ? keyboard.setKeys(ap.profile, [], {}) : keyboard.resetCustom(ap.profile)
            }
        }
        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: theme.muted
            font.pixelSize: 12
            text: ap.c ? "RigDeck's settings are in use on this profile. Turning them off goes back to the keyboard's own."
                       : "Showing the keyboard's own settings for this profile. Changing a key turns RigDeck settings on."
        }

        RowLayout {
            Layout.fillWidth: true
            Segmented {
                id: viewPick
                objectName: "keyboardView"
                model: ["Actuation", "Rapid Trigger", "Lighting"]
                currentIndex: 0
                onActivated: i => currentIndex = i
            }
            Item { Layout.fillWidth: true }
            Button { text: "All"; onClicked: ap.selected = keyboard.layout.map(k => k.name) }
            Button { text: "WASD"; onClicked: ap.selected = ["W", "A", "S", "D"] }
            Button { text: "None"; enabled: ap.selected.length > 0; onClicked: ap.selected = [] }
        }

        KeyboardMap {
            Layout.fillWidth: true
            Layout.topMargin: 4
            layout: keyboard.layout
            values: ap.values
            view: ["actuation", "rapid", "lighting"][viewPick.currentIndex]
            selected: ap.selected
            onPicked: names => ap.selected = names
        }
        Label {
            text: ["Numbers: actuation point in mm (2.0 is the default; orange = earlier, blue = deeper).",
                   "Numbers: Rapid Trigger sensitivity in mm (how far a key moves up to release, or down to press "
                   + "again); blank = off.",
                   ap.li ? "Colours RigDeck shows on this profile." : "The keyboard's own lighting is in use; "
                   + "colour a key to switch to RigDeck's colours."][viewPick.currentIndex]
            wrapMode: Text.WordWrap; Layout.fillWidth: true
            color: theme.muted; font.pixelSize: 12
        }

        // ---- editor for the selected keys
        ColumnLayout {
            visible: viewPick.currentIndex < 2
            Layout.fillWidth: true
            Layout.topMargin: 6
            spacing: 6
            Label {
                text: ap.selected.length === 0 ? "Select keys to change them."
                      : ap.selected.length > 8 ? ap.selected.length + " keys selected"
                      : "Selected: " + ap.selected.join(" ")
                color: theme.text; font.pixelSize: 13; font.bold: ap.selected.length > 0
            }
            SettingRow {
                enabled: ap.selected.length > 0
                title: "Actuation point"
                description: "How far the key goes down before it counts as pressed"
                Slider { id: act; Layout.preferredWidth: 220; from: 1; to: 40; stepSize: 1
                         value: ap.common("act") > 0 ? ap.common("act") : 20
                         Accessible.name: "Actuation point of the selected keys"
                         onPressedChanged: if (!pressed) keyboard.setKeys(ap.profile, ap.selected, { act: Math.round(value) }) }
                Label { text: ap.common("act") === -1 && !act.pressed ? "mixed" : ap.mm(act.value)
                        color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 56; horizontalAlignment: Text.AlignRight }
            }
            SettingRow {
                enabled: ap.selected.length > 0
                title: "Rapid Trigger"
                description: "The key resets as soon as it starts coming up and presses again as soon as it goes down, "
                             + "instead of at the fixed actuation point"
                Toggle { checked: ap.common("rapid") > 0
                         Accessible.name: "Rapid Trigger for the selected keys"
                         onToggled: keyboard.setKeys(ap.profile, ap.selected, { rapid: checked ? Math.round(rs.value) : 0 }) }
            }
            SettingRow {
                enabled: ap.selected.length > 0 && ap.common("rapid") !== 0
                title: "Rapid Trigger sensitivity"
                description: "How far the key has to move to reset or press again (smaller = more sensitive)"
                Slider { id: rs; Layout.preferredWidth: 220; from: 1; to: 20; stepSize: 1
                         value: ap.common("rapid") > 0 ? ap.common("rapid") : 5
                         Accessible.name: "Rapid Trigger sensitivity of the selected keys"
                         onPressedChanged: if (!pressed) keyboard.setKeys(ap.profile, ap.selected, { rapid: Math.round(value) }) }
                Label { text: ap.common("rapid") === -1 && !rs.pressed ? "mixed" : ap.mm(rs.value)
                        color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 56; horizontalAlignment: Text.AlignRight }
            }
        }

        // ---- colours
        ColumnLayout {
            visible: viewPick.currentIndex === 2
            Layout.fillWidth: true
            Layout.topMargin: 6
            spacing: 8
            SettingRow {
                title: "RigDeck colours"
                description: "Off = the keyboard's own lighting effect for this profile"
                Toggle { checked: !!ap.li; Accessible.name: "RigDeck colours for profile " + ap.profile
                         onToggled: checked ? keyboard.setBaseColor(ap.profile, "ffffff") : keyboard.resetLighting(ap.profile) }
            }
            Label {
                text: ap.selected.length === 0 ? "Select keys to colour them."
                      : ap.selected.length > 8 ? "Colour for the " + ap.selected.length + " selected keys"
                      : "Colour for " + ap.selected.join(" ")
                color: theme.text; font.pixelSize: 13; font.bold: ap.selected.length > 0
            }
            RowLayout {
                enabled: ap.selected.length > 0
                Layout.fillWidth: true
                ColorSwatches {
                    Layout.fillWidth: true
                    current: ap.selected.length === 1 && ap.values[ap.selected[0]] ? (ap.values[ap.selected[0]].color || "") : ""
                    colors: ["ff0000", "ff8000", "ffd000", "00ff40", "00c8ff", "0040ff", "a000ff", "ffffff", "000000"]
                    onPicked: c => keyboard.setColors(ap.profile, ap.selected, c)
                }
                Button { text: "Use background"; enabled: !!ap.li; onClicked: keyboard.setColors(ap.profile, ap.selected, "") }
            }
            SettingRow {
                visible: !!ap.li
                title: "Background"
                description: "Every key without its own colour (black = off)"
                ColorSwatches {
                    current: ap.li ? ap.li.base : ""
                    colors: ["ffffff", "00c8ff", "ff0000", "a000ff", "000000"]
                    onPicked: c => keyboard.setBaseColor(ap.profile, c)
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
                      + "keyboard uses its own."
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
