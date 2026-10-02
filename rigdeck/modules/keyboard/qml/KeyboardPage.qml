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
        Layout.fillWidth: true
        visible: page.ok
        title: "Actuation and Rapid Trigger"
        subtitle: "What each onboard profile is set to, read from the keyboard. Switch profiles with Fn + F2 / F3 / F4."
        Label {
            visible: keyboard.analogStatus === "loading" && keyboard.analog.length === 0
            text: "Reading the keyboard…"; color: theme.muted; font.pixelSize: 13
        }
        Repeater {
            model: keyboard.analog
            ColumnLayout {
                id: prof
                required property var modelData
                Layout.fillWidth: true
                spacing: 4
                Label {
                    text: "Profile " + prof.modelData.index + "  ·  " + prof.modelData.keys
                          + (prof.modelData.name ? "  ·  " + prof.modelData.name : "")
                    color: theme.text; font.pixelSize: 13; font.bold: true
                    Layout.topMargin: prof.modelData.index > 1 ? 8 : 0
                }
                Repeater {
                    model: [{ label: "Actuation point", groups: prof.modelData.actuation },
                            { label: "Rapid Trigger", groups: prof.modelData.rapidTrigger }]
                    KeyValue {
                        required property var modelData
                        key: modelData.label
                        value: modelData.groups.length === 0 ? "Off"
                               : modelData.groups.map(g => g.value + (g.all ? " (all keys)" : " — " + g.keys.join(" "))).join("\n")
                    }
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
                text: "Changing these from RigDeck is coming. For now: Fn + F5 adjusts them on the keyboard."
            }
            Button {
                text: "Refresh"
                enabled: keyboard.analogStatus !== "loading"
                onClicked: keyboard.refreshAnalog()
            }
        }
        ActionLink {
            label: "Logitech's guide: setting actuation and Rapid Trigger without software"
            onClicked: appState.openUrl("https://www.logitech.com/assets/70228/g_pro_x_tkl_rapid.pdf")
        }
    }

    BluetoothDevices { category: "keyboard"; label: "Bluetooth keyboards" }
}
