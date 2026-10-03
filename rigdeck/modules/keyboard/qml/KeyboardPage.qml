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

    // the profile being edited (starts on the one in use)
    property int profile: s.activeProfile || 1
    property var selected: []
    property var values: ({})          // key name -> {act, rapid, own, color}; 0.1 mm
    property var wide: ({})            // {act, rapid, own, custom} for the whole profile
    property var li: null              // RigDeck's colours for this profile, or null
    property var profileNames: []
    function reload() {
        values = keyboard.keyValues(profile)
        wide = keyboard.profileWide(profile)
        li = keyboard.lightingFor(profile) || null
        const names = keyboard.analog.map(x => x.keys)
        if (JSON.stringify(names) !== JSON.stringify(profileNames)) profileNames = names
    }
    onProfileChanged: { selected = []; reload() }
    Connections { target: keyboard; function onAnalogChanged() { page.reload() }
                  function onToast(m) { root.showToast(m) } }
    Component.onCompleted: reload()

    function mm(t) { return (t / 10).toFixed(1) + " mm" }
    function common(field) {               // the selection's shared value, or -1 when keys differ
        const vs = selected.map(n => values[n] ? values[n][field] : undefined).filter(v => v !== undefined)
        return vs.length && vs.every(v => v === vs[0]) ? vs[0] : -1
    }

    PageHeader {
        title: page.s.name || "Keyboard"
        subtitle: page.ok ? "Firmware " + page.s.firmware : ""
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

    // ---- profile + tab
    RowLayout {
        visible: page.ok && keyboard.analog.length > 0
        Layout.fillWidth: true
        spacing: 12
        Label { text: "Profile"; color: theme.muted; font.pixelSize: 13 }
        Segmented {
            model: page.profileNames             // fixed labels: chips aren't rebuilt on every update
            currentIndex: page.profile - 1
            onActivated: i => page.profile = i + 1
        }
        Label {
            visible: !!page.s.activeProfile
            text: page.s.activeProfile === page.profile ? "In use now" : "Not in use (" + page.profileNames[page.s.activeProfile - 1] + " is)"
            color: page.s.activeProfile === page.profile ? theme.live : theme.muted
            font.pixelSize: 12
        }
        Item { Layout.fillWidth: true }
        Segmented {
            id: tab
            model: ["Keys", "Lighting"]
            currentIndex: 0
            onActivated: i => { currentIndex = i; page.selected = [] }
        }
    }
    Label {
        visible: page.ok && keyboard.analogStatus === "loading" && keyboard.analog.length === 0
        text: "Reading the keyboard…"; color: theme.muted; font.pixelSize: 13
    }

    // =========================================================================== Keys
    Panel {
        visible: page.ok && tab.currentIndex === 0 && keyboard.analog.length > 0
        Layout.fillWidth: true
        title: "Every key"
        subtitle: page.wide.custom ? "Set by RigDeck for this profile"
                                   : "The keyboard's own settings for this profile. Change anything to make it yours."
        SettingRow {
            title: "Press point"
            description: "How far a key goes down before it types. Shorter reacts faster; longer avoids accidental presses."
            Slider { id: wAct; Layout.preferredWidth: 240; from: 1; to: 40; stepSize: 1; value: page.wide.act || 20
                     Accessible.name: "Press point for every key"
                     onPressedChanged: if (!pressed) keyboard.setProfileWide(page.profile, { act: Math.round(value) }) }
            Label { text: page.mm(wAct.value); color: theme.text; font.pixelSize: 13
                    Layout.preferredWidth: 56; horizontalAlignment: Text.AlignRight }
        }
        SettingRow {
            title: "Release"
            description: (page.wide.rapid || 0) > 0
                         ? "Rapid: a key lets go as soon as it starts coming up, and types again as soon as it goes back down"
                         : "Standard: a key lets go when it comes back up past the press point"
            Segmented {
                model: ["Standard", "Rapid"]
                currentIndex: (page.wide.rapid || 0) > 0 ? 1 : 0
                onActivated: i => keyboard.setProfileWide(page.profile, { rapid: i === 1 ? Math.round(wRel.value) || 5 : 0 })
            }
        }
        SettingRow {
            visible: (page.wide.rapid || 0) > 0
            title: "Release distance"
            description: "How far a key has to move up to let go (and back down to type again). Smaller is quicker."
            Slider { id: wRel; Layout.preferredWidth: 240; from: 1; to: 20; stepSize: 1
                     value: (page.wide.rapid || 0) > 0 ? page.wide.rapid : 5
                     Accessible.name: "Release distance for every key"
                     onPressedChanged: if (!pressed) keyboard.setProfileWide(page.profile, { rapid: Math.round(value) }) }
            Label { text: page.mm(wRel.value); color: theme.text; font.pixelSize: 13
                    Layout.preferredWidth: 56; horizontalAlignment: Text.AlignRight }
        }
    }

    Panel {
        visible: page.ok && tab.currentIndex === 0 && keyboard.analog.length > 0
        Layout.fillWidth: true
        title: "Individual keys"
        subtitle: page.wide.own ? (page.wide.own === 1 ? "1 key has its own settings" : page.wide.own + " keys have their own settings")
                                  + " (highlighted, with their values)"
                                : "Select keys (click, Ctrl+click or drag) to give them their own settings"
        RowLayout {
            Layout.fillWidth: true
            Button { text: "WASD"; onClicked: page.selected = ["W", "A", "S", "D"] }
            Button { text: "All"; onClicked: page.selected = keyboard.layout.filter(k => k.analog).map(k => k.name) }
            Button { text: "Clear selection"; enabled: page.selected.length > 0; onClicked: page.selected = [] }
            Item { Layout.fillWidth: true }
            Button { text: "Reset all keys to “Every key”"; visible: (page.wide.own || 0) > 0
                     onClicked: keyboard.clearOwn(page.profile, []) }
        }
        KeyboardMap {
            Layout.fillWidth: true
            Layout.topMargin: 4
            layout: keyboard.layout
            values: page.values
            view: "keys"
            wideAct: page.wide.act || 20
            wideRapid: page.wide.rapid || 0
            selected: page.selected
            onPicked: names => page.selected = names.filter(n => keyboard.layout.some(k => k.name === n && k.analog))
        }
        Label {
            text: "Highlighted keys show their own press point (bottom) and release distance (↑, top). Media keys only have lights."
            color: theme.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap
        }

        ColumnLayout {
            visible: page.selected.length > 0
            Layout.fillWidth: true
            Layout.topMargin: 6
            spacing: 6
            RowLayout {
                Layout.fillWidth: true
                Label {
                    text: page.selected.length > 10 ? page.selected.length + " keys selected"
                                                    : page.selected.join("  ")
                    color: theme.text; font.pixelSize: 14; font.bold: true; Layout.fillWidth: true; elide: Text.ElideRight
                }
                Button { text: "Use “Every key”"; onClicked: keyboard.clearOwn(page.profile, page.selected) }
            }
            SettingRow {
                title: "Press point"
                Slider { id: kAct; Layout.preferredWidth: 240; from: 1; to: 40; stepSize: 1
                         value: page.common("act") > 0 ? page.common("act") : (page.wide.act || 20)
                         Accessible.name: "Press point of the selected keys"
                         onPressedChanged: if (!pressed) keyboard.setKeys(page.profile, page.selected, { act: Math.round(value) }) }
                Label { text: page.common("act") === -1 && !kAct.pressed ? "mixed" : page.mm(kAct.value)
                        color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 56; horizontalAlignment: Text.AlignRight }
            }
            SettingRow {
                title: "Release"
                Segmented {
                    model: ["Standard", "Rapid"]
                    currentIndex: page.common("rapid") === -1 ? -1 : page.common("rapid") > 0 ? 1 : 0
                    onActivated: i => keyboard.setKeys(page.profile, page.selected,
                                                       { rapid: i === 1 ? Math.round(kRel.value) : 0 })
                }
            }
            SettingRow {
                visible: page.common("rapid") !== 0
                title: "Release distance"
                Slider { id: kRel; Layout.preferredWidth: 240; from: 1; to: 20; stepSize: 1
                         value: page.common("rapid") > 0 ? page.common("rapid") : 5
                         Accessible.name: "Release distance of the selected keys"
                         onPressedChanged: if (!pressed) keyboard.setKeys(page.profile, page.selected, { rapid: Math.round(value) }) }
                Label { text: page.common("rapid") === -1 && !kRel.pressed ? "mixed" : page.mm(kRel.value)
                        color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 56; horizontalAlignment: Text.AlignRight }
            }
        }
    }

    // =========================================================================== Lighting
    Panel {
        visible: page.ok && tab.currentIndex === 1
        Layout.fillWidth: true
        title: "Lighting"
        SettingRow {
            visible: page.s.brightness !== undefined
            title: "Brightness"
            Slider {
                id: bri
                Layout.preferredWidth: 240
                from: page.s.brightnessMin || 0; to: page.s.brightnessMax || 100; stepSize: 1
                value: page.s.brightness || 0
                Accessible.name: "Keyboard brightness"
                onPressedChanged: if (!pressed) keyboard.setBrightness(Math.round(value))
            }
            Label { text: Math.round(bri.value) === 0 ? "Off" : Math.round(bri.value) + "%"
                    color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 56; horizontalAlignment: Text.AlignRight }
        }
        SettingRow {
            title: "Colours"
            description: page.li ? "Your colours, per key" : "The effect stored in this profile on the keyboard"
            Segmented {
                model: ["Keyboard's effect", "My colours"]
                currentIndex: page.li ? 1 : 0
                onActivated: i => i === 1 ? keyboard.setBaseColor(page.profile, "ffffff") : keyboard.resetLighting(page.profile)
            }
        }
    }
    Panel {
        visible: page.ok && tab.currentIndex === 1 && !!page.li
        Layout.fillWidth: true
        title: "Key colours"
        subtitle: "Select keys (click, Ctrl+click or drag), then pick a colour"
        RowLayout {
            Layout.fillWidth: true
            Button { text: "All"; onClicked: page.selected = keyboard.layout.map(k => k.name) }
            Button { text: "WASD"; onClicked: page.selected = ["W", "A", "S", "D"] }
            Button { text: "Clear selection"; enabled: page.selected.length > 0; onClicked: page.selected = [] }
        }
        KeyboardMap {
            Layout.fillWidth: true
            Layout.topMargin: 4
            layout: keyboard.layout
            values: page.values
            view: "lighting"
            selected: page.selected
            onPicked: names => page.selected = names
        }
        RowLayout {
            Layout.fillWidth: true
            enabled: page.selected.length > 0
            Label { text: page.selected.length ? "Selected keys" : "Select keys first"; color: theme.text; font.pixelSize: 13
                    Layout.preferredWidth: 110 }
            ColorSwatches {
                Layout.fillWidth: true
                current: page.selected.length === 1 && page.values[page.selected[0]] ? (page.values[page.selected[0]].color || "") : ""
                colors: ["ff0000", "ff8000", "ffd000", "00ff40", "00c8ff", "0040ff", "a000ff", "ffffff", "000000"]
                onPicked: c => keyboard.setColors(page.profile, page.selected, c)
            }
            Button { text: "Same as the rest"; onClicked: keyboard.setColors(page.profile, page.selected, "") }
        }
        RowLayout {
            Layout.fillWidth: true
            Label { text: "Every other key"; color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 110 }
            ColorSwatches {
                Layout.fillWidth: true
                current: page.li ? page.li.base : ""
                colors: ["ffffff", "00c8ff", "ff0000", "a000ff", "000000"]
                onPicked: c => keyboard.setBaseColor(page.profile, c)
            }
        }
    }

    // ---- footer: going back, and what "RigDeck settings" means
    RowLayout {
        visible: page.ok && keyboard.analog.length > 0
        Layout.fillWidth: true
        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: theme.muted
            font.pixelSize: 12
            text: "RigDeck applies these while it's running, and again after you switch profiles (Fn + F2 / F3 / F4) "
                  + "or plug the keyboard in. Without RigDeck the keyboard uses its own."
        }
        Button {
            visible: tab.currentIndex === 0 && !!page.wide.custom
            text: "Back to the keyboard's own"
            onClicked: keyboard.resetCustom(page.profile)
        }
    }

    BluetoothDevices { category: "keyboard"; label: "Bluetooth keyboards" }
}
