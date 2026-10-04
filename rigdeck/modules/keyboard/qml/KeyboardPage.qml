import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

// Keyboard: like Wootility, the keyboard is the centre of the page and one editor below it acts on
// what's selected: nothing selected = all keys, otherwise the selected keys.
PageScroll {
    id: page
    property bool shown: true
    readonly property var s: keyboard.state
    readonly property bool ok: keyboard.status === "ok"
    readonly property int bt: bluez.devices.filter(d => d.connected && d.category === "keyboard").length
    readonly property bool ready: ok && keyboard.analog.length > 0

    property int profile: s.activeProfile || 1
    property var selected: []
    property var values: ({})          // key name -> {act, rapid, own, color}; 0.1 mm
    property var wide: ({})            // {act, rapid, own, custom} for the whole profile
    property var li: null              // RigDeck's colours for this profile, or null
    property var profileNames: []
    readonly property bool lighting: tab.currentIndex === 1
    readonly property bool all: selected.length === 0

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
    // the value being edited: the profile's for all keys, else the selection's (-1 = keys differ)
    function cur(field) {
        if (all) return field === "act" ? (wide.act || 20) : (wide.rapid || 0)
        const vs = selected.map(n => values[n] ? values[n][field] : undefined).filter(v => v !== undefined)
        return vs.length && vs.every(v => v === vs[0]) ? vs[0] : -1
    }
    function set(patch) {
        if (all) keyboard.setProfileWide(profile, patch)
        else keyboard.setKeys(profile, selected, patch)
    }
    readonly property bool selectionOwn: selected.some(n => values[n] && values[n].own)

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
    Label {
        visible: page.ok && keyboard.analogStatus === "loading" && keyboard.analog.length === 0
        text: "Reading the keyboard…"; color: theme.muted; font.pixelSize: 13
    }

    // ---- profile + what to edit
    RowLayout {
        visible: page.ready
        Layout.fillWidth: true
        spacing: 10
        Segmented {
            model: page.profileNames
            currentIndex: page.profile - 1
            onActivated: i => page.profile = i + 1
        }
        Label {
            visible: !!page.s.activeProfile
            text: page.s.activeProfile === page.profile ? "in use" : "not in use"
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

    // ---- the keyboard
    Panel {
        visible: page.ready
        Layout.fillWidth: true
        RowLayout {
            Layout.fillWidth: true
            Label {
                Layout.fillWidth: true
                text: page.all ? "Click keys to change only those, or drag across several. Changes below apply to all keys."
                               : page.selected.length + (page.selected.length === 1 ? " key" : " keys") + " selected"
                color: page.all ? theme.muted : theme.text; font.pixelSize: 13; font.bold: !page.all
                wrapMode: Text.WordWrap
            }
            Button { text: "WASD"; onClicked: page.selected = ["W", "A", "S", "D"] }
            Button { text: page.all ? "Select all" : "Clear selection"
                     onClicked: page.selected = page.all ? keyboard.layout.filter(k => page.lighting || k.analog).map(k => k.name) : [] }
        }
        KeyboardMap {
            Layout.fillWidth: true
            layout: keyboard.layout
            values: page.values
            view: page.lighting ? "lighting" : "keys"
            wideAct: page.wide.act || 20
            wideRapid: page.wide.rapid || 0
            selected: page.selected
            onPicked: names => page.selected = page.lighting ? names
                      : names.filter(n => keyboard.layout.some(k => k.name === n && k.analog))
        }
        Label {
            visible: !page.lighting && (page.wide.own || 0) > 0
            text: "Tinted keys have their own settings and show what differs (↑ = release distance)."
            color: theme.muted; font.pixelSize: 12
        }
    }

    // ---- editor: keys
    Panel {
        visible: page.ready && !page.lighting
        Layout.fillWidth: true
        title: page.all ? "All keys" : page.selected.length > 12 ? page.selected.length + " keys"
                                                                 : page.selected.join("  ")
        subtitle: page.all ? ((page.wide.own || 0) > 0 ? "Except the " + page.wide.own + " tinted keys, which keep their own" : "")
                           : page.selectionOwn ? "Own settings" : "Same as all keys"
        actionText: page.all ? ((page.wide.own || 0) > 0 ? "Make every key the same" : "")
                             : (page.selectionOwn ? "Same as all keys" : "")
        onActionClicked: keyboard.clearOwn(page.profile, page.all ? [] : page.selected)

        RowLayout {
            Layout.fillWidth: true
            spacing: 28
            KeyTravel {
                act: page.cur("act")
                rapid: page.cur("rapid")
                Layout.alignment: Qt.AlignTop
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                spacing: 14
                SettingRow {
                    title: "Press point"
                    description: "How far down a key types. Shorter is faster; longer avoids accidental presses."
                    Slider { id: act; Layout.preferredWidth: 220; from: 1; to: 40; stepSize: 1
                             value: page.cur("act") > 0 ? page.cur("act") : (page.wide.act || 20)
                             Accessible.name: "Press point"
                             onPressedChanged: if (!pressed) page.set({ act: Math.round(value) }) }
                    Label { text: page.cur("act") === -1 && !act.pressed ? "mixed" : page.mm(act.value)
                            color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 56; horizontalAlignment: Text.AlignRight }
                }
                SettingRow {
                    title: "Release"
                    description: page.cur("rapid") > 0 ? "Rapid: lets go as soon as the key starts rising, types again as soon as it goes down"
                               : page.cur("rapid") === 0 ? "Standard: lets go when the key rises back past the press point"
                               : "The selected keys differ"
                    Segmented {
                        model: ["Standard", "Rapid"]
                        currentIndex: page.cur("rapid") === -1 ? -1 : page.cur("rapid") > 0 ? 1 : 0
                        onActivated: i => page.set({ rapid: i === 1 ? Math.round(rel.value) : 0 })
                    }
                }
                SettingRow {
                    visible: page.cur("rapid") !== 0
                    title: "Release distance"
                    description: "How far the key rises before it lets go (and goes down before it types again)"
                    Slider { id: rel; Layout.preferredWidth: 220; from: 1; to: 20; stepSize: 1
                             value: page.cur("rapid") > 0 ? page.cur("rapid") : 5
                             Accessible.name: "Release distance"
                             onPressedChanged: if (!pressed) page.set({ rapid: Math.round(value) }) }
                    Label { text: page.cur("rapid") === -1 && !rel.pressed ? "mixed" : page.mm(rel.value)
                            color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 56; horizontalAlignment: Text.AlignRight }
                }
            }
        }
    }

    // ---- editor: lighting
    Panel {
        visible: page.ready && page.lighting
        Layout.fillWidth: true
        title: page.all ? "All keys" : page.selected.length > 12 ? page.selected.length + " keys" : page.selected.join("  ")
        SettingRow {
            visible: page.all
            title: "Colours"
            description: page.li ? "Your colours, key by key" : "The effect stored in this profile on the keyboard"
            Segmented {
                model: ["Keyboard's effect", "My colours"]
                currentIndex: page.li ? 1 : 0
                onActivated: i => i === 1 ? keyboard.setBaseColor(page.profile, "ffffff") : keyboard.resetLighting(page.profile)
            }
        }
        SettingRow {
            visible: !!page.li || !page.all
            title: page.all ? "Colour of every key" : "Colour"
            description: page.all ? "Keys you colour separately keep their colour" : ""
            ColorSwatches {
                current: page.all ? (page.li ? page.li.base : "")
                         : page.selected.length === 1 && page.values[page.selected[0]] ? (page.values[page.selected[0]].color || "") : ""
                colors: ["ff0000", "ff8000", "ffd000", "00ff40", "00c8ff", "0040ff", "a000ff", "ffffff", "000000"]
                onPicked: c => page.all ? keyboard.setBaseColor(page.profile, c) : keyboard.setColors(page.profile, page.selected, c)
            }
        }
        RowLayout {
            visible: !page.all && !!page.li
            Item { Layout.fillWidth: true }
            Button { text: "Same as the other keys"; onClicked: keyboard.setColors(page.profile, page.selected, "") }
        }
        SettingRow {
            visible: page.all && page.s.brightness !== undefined
            title: "Brightness"
            Slider {
                id: bri
                Layout.preferredWidth: 220
                from: page.s.brightnessMin || 0; to: page.s.brightnessMax || 100; stepSize: 1
                value: page.s.brightness || 0
                Accessible.name: "Keyboard brightness"
                onPressedChanged: if (!pressed) keyboard.setBrightness(Math.round(value))
            }
            Label { text: Math.round(bri.value) === 0 ? "Off" : Math.round(bri.value) + "%"
                    color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 56; horizontalAlignment: Text.AlignRight }
        }
    }

    // ---- footer
    RowLayout {
        visible: page.ready
        Layout.fillWidth: true
        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: theme.muted
            font.pixelSize: 12
            text: "RigDeck applies your changes while it runs and after profile switches, sleep or replugging. "
                  + "Without RigDeck the keyboard uses its own settings."
        }
        Button {
            visible: !page.lighting && !!page.wide.custom
            text: "Use the keyboard's own"
            onClicked: { page.selected = []; keyboard.resetCustom(page.profile) }
        }
    }

    BluetoothDevices { category: "keyboard"; label: "Bluetooth keyboards" }
}
