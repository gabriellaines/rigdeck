import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    readonly property var i: headset.info
    readonly property var s: headset.settings
    readonly property bool on: headset.status === "ok"
    readonly property var caps: i.caps || []
    readonly property var offMinutes: [0, 10, 20, 30, 60, 90].filter(m => m <= (i.inactiveMax || 90))
    readonly property int bt: bluez.devices.filter(d => d.connected && d.category === "headset").length
    readonly property bool usb: headset.status !== "none" && headset.status !== "not-installed"
    function has(cap) { return caps.indexOf(cap) >= 0 }
    function unset(key) { return s[key] === -1 ? "Not set from RigDeck yet — the headset can't report it" : "" }

    Connections { target: headset; function onToast(m) { root.showToast(m) } }
    onShownChanged: headset.setActive(shown)
    Component.onCompleted: headset.setActive(shown)

    PageHeader {
        title: page.i.name || (page.bt ? "Headphones" : "Headset")
        subtitle: ["via HeadsetControl", page.i.id ? "USB " + page.i.id : ""].filter(t => t).join(" · ")
        status: page.bt && !page.usb ? "Bluetooth" : ({ ok: "Connected", off: "Headset off", none: "Not found", loading: "Looking…",
                   "not-installed": "Setup needed", error: "Error" })[headset.status]
        tone: page.on || (page.bt && !page.usb) ? theme.live : headset.status === "error" ? theme.error : theme.warning
    }

    // ---- setup states
    Banner {
        visible: headset.status === "not-installed" && page.bt === 0
        text: "Headset support uses HeadsetControl, which isn't installed. On Arch/CachyOS: "
              + "sudo pacman -S headsetcontrol — other distros: see HeadsetControl's GitHub page."
        buttonText: "Open HeadsetControl page"
        onClicked: appState.openUrl("https://github.com/Sapd/HeadsetControl#installation")
    }
    Banner {
        visible: headset.status === "off"
        tone: "info"
        text: "The receiver is plugged in, but the headset is off or out of range. Turn it on to see the battery "
              + "and change settings — RigDeck re-applies your settings each time it turns on."
    }
    Banner {
        visible: headset.status === "none" && page.bt === 0
        text: "No supported headset found. Plug in the headset or its wireless receiver."
        buttonText: "Check again"
        onClicked: headset.refresh()
    }
    Banner {
        visible: headset.status === "error"
        tone: "error"
        text: "HeadsetControl reported an error: " + headset.error
        buttonText: "Retry"
        onClicked: headset.refresh()
    }

    // ---- live
    GridLayout {
        Layout.fillWidth: true
        visible: page.on
        columns: page.pageWidth >= 700 ? 2 : 1
        columnSpacing: 12; rowSpacing: 12; uniformCellWidths: true
        MetricCard {
            Layout.fillWidth: true
            icon: page.i.charging ? "battery-charging" : page.i.battery >= 70 ? "battery-full"
                  : page.i.battery >= 30 ? "battery-medium" : "battery-low"
            label: "Battery"
            value: page.i.battery !== null && page.i.battery !== undefined ? page.i.battery : "—"
            unit: "%"
            valueColor: page.i.battery !== null && page.i.battery < 15 && !page.i.charging ? theme.error : theme.text
            detail: page.i.charging ? "Charging" : "On battery"
        }
        MetricCard {
            Layout.fillWidth: true
            visible: page.has("chatmix")
            icon: "headphones"
            label: "Game / chat mix"
            value: page.i.chatmix !== null && page.i.chatmix !== undefined ? Math.round(page.i.chatmix / 1.28) : "—"
            unit: "% game"
            detail: "Set with the dial on the headset"
        }
    }

    // ---- settings
    Panel {
        Layout.fillWidth: true
        visible: page.usb
        title: "Settings"
        subtitle: "Applied right away and re-applied whenever the headset turns on"
        enabled: page.on && !headset.busy

        SettingRow {
            visible: page.has("sidetone")
            title: "Hear yourself (sidetone)"
            description: "Plays your microphone in the headset so you don't talk too loudly"
            note: page.unset("sidetone")
            Toggle {
                visible: page.i.sidetoneOnOff
                checked: page.s.sidetone > 0
                Accessible.name: "Sidetone"
                onToggled: headset.set("sidetone", checked ? 128 : 0)
            }
            Slider {
                id: st
                visible: !page.i.sidetoneOnOff
                Layout.preferredWidth: 220
                from: 0; to: 128; stepSize: 8
                value: Math.max(0, page.s.sidetone)
                Accessible.name: "Sidetone level"
                onPressedChanged: if (!pressed) headset.set("sidetone", Math.round(value))
            }
            Label { visible: !page.i.sidetoneOnOff; text: st.value === 0 ? "Off" : Math.round(st.value / 1.28) + "%"
                    color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 40 }
        }

        SettingRow {
            visible: page.has("inactive_time")
            title: "Turn off when idle"
            description: "Saves battery when you forget to switch the headset off"
            note: page.unset("inactive_time")
            Segmented {
                model: page.offMinutes.map(m => m === 0 ? "Never" : m + " min")
                currentIndex: page.offMinutes.indexOf(page.s.inactive_time)
                minChipWidth: 48
                onActivated: (ix) => headset.set("inactive_time", page.offMinutes[ix])
            }
        }

        SettingRow {
            visible: page.has("lights")
            title: "Lights"
            note: page.unset("lights")
            Toggle { checked: page.s.lights > 0; Accessible.name: "Lights"
                     onToggled: headset.set("lights", checked ? 1 : 0) }
        }
        SettingRow {
            visible: page.has("voice_prompts")
            title: "Voice prompts"
            description: "Spoken announcements such as power and battery level"
            note: page.unset("voice_prompts")
            Toggle { checked: page.s.voice_prompts > 0; Accessible.name: "Voice prompts"
                     onToggled: headset.set("voice_prompts", checked ? 1 : 0) }
        }
        SettingRow {
            visible: page.has("rotate_to_mute")
            title: "Rotate to mute"
            description: "Mutes the microphone when you raise its arm"
            note: page.unset("rotate_to_mute")
            Toggle { checked: page.s.rotate_to_mute > 0; Accessible.name: "Rotate to mute"
                     onToggled: headset.set("rotate_to_mute", checked ? 1 : 0) }
        }
    }

    BluetoothDevices { category: "headset"; label: "Bluetooth headphones" }
}
