import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    readonly property var s: motherboard.state
    readonly property var b: s.board || ({})
    readonly property bool sensors: (s.chip || "") !== ""
    readonly property var fans: s.fans || []
    readonly property int spinning: fans.filter(f => f.connected).length
    readonly property var light: motherboard.light
    readonly property var effects: [["off", "Off"], ["static", "Static"], ["breathing", "Breathing"],
                                    ["flashing", "Flashing"], ["cycle", "Color cycle"], ["rainbow", "Rainbow"]]

    Connections { target: motherboard; function onToast(m) { root.showToast(m) } }

    PageHeader {
        title: [page.b.vendor === "ASUSTeK COMPUTER INC." ? "ASUS" : page.b.vendor, page.b.name].filter(t => t).join(" ")
        subtitle: "BIOS " + page.b.bios + (page.b.biosDate ? " (" + page.b.biosDate + ")" : "")
                  + (page.sensors ? " · sensor chip " + page.s.chip.toUpperCase() : "")
        status: page.sensors ? "Monitoring" : "Sensors unavailable"
        tone: page.sensors ? theme.live : theme.warning
    }

    Banner {
        visible: !page.sensors
        text: "The board's temperature and fan sensors need its sensor driver, which isn't loaded."
              + (motherboard.driverAvailable
                 ? " Load it once with: sudo modprobe nct6775 — and at every boot with: "
                   + "echo nct6775 | sudo tee /etc/modules-load.d/rigdeck-fans.conf"
                 : " Your kernel doesn't include the Nuvoton driver (nct6775); ITE boards use it87.")
    }

    GridLayout {
        Layout.fillWidth: true
        visible: page.sensors && (page.s.temps || []).length > 0
        columns: page.pageWidth >= 900 ? 3 : page.pageWidth >= 520 ? 2 : 1
        columnSpacing: 12; rowSpacing: 12; uniformCellWidths: true
        Repeater {
            model: page.s.temps || []
            MetricCard {
                Layout.fillWidth: true
                icon: "thermometer"
                label: modelData.label
                value: modelData.c.toFixed(0); unit: "°C"
                detail: modelData.raw
            }
        }
    }

    Panel {
        Layout.fillWidth: true
        visible: page.sensors && page.fans.length > 0
        title: "Fan headers"
        subtitle: page.spinning === 0
                  ? "No fans connected to the board. Fans on the cooler's hub are on the Cooler page."
                  : page.spinning + " of " + page.fans.length + " headers have a fan · speeds follow the BIOS"
        padding: 0
        Repeater {
            model: page.fans.filter(f => f.connected)
            DeviceRow {
                showDivider: index > 0
                icon: "fan"
                title: "Header " + modelData.n
                detail: modelData.mode + (modelData.duty !== null ? " · " + modelData.duty + "% power" : "")
                status: modelData.rpm.toLocaleString(Qt.locale(), "f", 0) + " RPM"
                tone: theme.live
            }
        }
    }

    // ---- lighting (ASUS Aura)
    Repeater {
        model: page.light.zones || []
        Panel {
            id: zone
            readonly property var zn: modelData
            Layout.fillWidth: true
            enabled: !motherboard.busy
            title: "Lighting · " + zn.label
            subtitle: (zn.mode ? "Kept after restarts" : "The controller can't report its current effect; pick one to take over")
                      + " · Aura firmware " + page.light.firmware
            SettingRow {
                title: "Effect"
                Segmented {
                    model: page.effects.map(e => e[1])
                    currentIndex: page.effects.findIndex(e => e[0] === zone.zn.mode)
                    onActivated: (ix) => motherboard.setLighting(zone.zn.id, page.effects[ix][0], zone.zn.color)
                }
            }
            SettingRow {
                visible: ["static", "breathing", "flashing"].indexOf(zone.zn.mode) >= 0
                title: "Color"
                ColorSwatches {
                    current: zone.zn.color
                    onPicked: (c) => motherboard.setLighting(zone.zn.id, zone.zn.mode, c)
                }
            }
        }
    }
    Banner {
        visible: motherboard.lightError !== ""
        tone: "error"
        text: "Lighting controller: " + motherboard.lightError
        buttonText: "Retry"
        onClicked: motherboard.refreshLighting()
    }
}
