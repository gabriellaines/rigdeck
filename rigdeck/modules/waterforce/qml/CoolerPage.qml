import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Effects
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    BusyGate { id: coolerBusy; busy: cooler.busy !== "" }
    property bool shown: true
    readonly property bool up: cooler.connected
    readonly property bool serviceUp: appState.serviceState === "active"
    readonly property var led: cooler.led
    readonly property var currentEffect: cooler.ledEffects.find(e => e.id === led.effect) || cooler.ledEffects[0]
    function fmt(v) { return (v === null || v === undefined) ? "—" : Number(v).toLocaleString(Qt.locale(), "f", 0) }
    function sendLed(effect, color, brightness, speed) {
        cooler.setLed(effect, color, brightness, speed)
    }

    Connections { target: cooler; function onToast(m) { root.showToast(m) } }

    PageHeader {
        title: cooler.identity.model
        subtitle: [cooler.identity.usb, cooler.identity.firmware ? "Firmware " + cooler.identity.firmware : ""]
                  .filter(s => s).join(" · ")
        status: page.up ? "Connected" : "Disconnected"
        tone: page.up ? theme.live : theme.warning
    }

    Banner {
        visible: !page.up
        tone: "warning"
        text: "The cooler isn't reachable. Is it plugged in, or passed through to a virtual machine? "
              + "Controls are disabled until it's back; RigDeck reconnects automatically."
        buttonText: "Retry"
        onClicked: cooler.reload()
    }
    Banner {
        visible: page.up && !page.serviceUp
        tone: "warning"
        text: "The background service is not running, so the cooler isn't getting your CPU temperature "
              + "and its curves can't react to load."
        buttonText: "Start service"
        onClicked: appState.startService()
    }

    GridLayout {
        Layout.fillWidth: true
        columns: page.pageWidth >= 760 ? 3 : 1
        columnSpacing: 12; rowSpacing: 12; uniformCellWidths: true
        MetricCard { Layout.fillWidth: true; icon: "fan"; label: "Radiator fans"; value: page.fmt(cooler.live.fan)
                     unit: "RPM"; detail: cooler.fanModeName + " profile" }
        MetricCard { Layout.fillWidth: true; icon: "activity"; label: "Pump"; value: page.fmt(cooler.live.pump)
                     unit: "RPM"; detail: cooler.pumpModeName + " profile" }
        MetricCard { Layout.fillWidth: true; icon: "thermometer"; label: "CPU temperature"; value: page.fmt(cooler.live.cpu)
                     unit: "°C"; detail: page.serviceUp ? "Sent to the cooler every 1.5 s" : "Not being sent — service stopped" }
    }

    // ---- tabs
    Segmented {
        id: tabs
        objectName: "coolerTabs"
        Layout.fillWidth: true
        model: ["Cooling", "Lighting", "Screen"]
        currentIndex: 0
        chipHeight: 34
        onActivated: (i) => currentIndex = i
    }

    StackLayout {
        Layout.fillWidth: true
        currentIndex: tabs.currentIndex
        enabled: page.up

        // ==== Cooling
        ColumnLayout {
            spacing: 16
            Panel {
                Layout.fillWidth: true
                title: "Modes"
                subtitle: "Saved on the cooler when you apply"
                GridLayout {
                    Layout.fillWidth: true
                    columns: page.pageWidth >= 640 ? 2 : 1
                    columnSpacing: 16; rowSpacing: 8
                    Label { text: "Fans"; color: theme.muted; font.pixelSize: 13 }
                    Segmented { Layout.fillWidth: true; model: cooler.fanModes; currentIndex: cooler.fanMode
                                onActivated: (i) => cooler.setFanMode(i) }
                    Label { text: "Pump"; color: theme.muted; font.pixelSize: 13 }
                    Segmented { Layout.fillWidth: true; model: cooler.pumpModes; currentIndex: cooler.pumpMode
                                onActivated: (i) => cooler.setPumpMode(i) }
                }
            }
            Panel {
                Layout.fillWidth: true
                title: "Curve"
                subtitle: cooler.curveHint
                headerExtra: [
                    Label { text: "━ Fans"; color: theme.accent; font.pixelSize: 12 },
                    Label { text: "┅ Pump"; color: theme.muted; font.pixelSize: 12 }
                ]
                CurveChart {
                    Layout.fillWidth: true
                    points: cooler.fanCurve
                    points2: cooler.pumpCurve
                    editable: cooler.curveEditable
                    onPointMoved: (i, t, rpm) => cooler.setCurvePoint(i, t, rpm)
                }
                RowLayout {
                    Layout.fillWidth: true
                    Item { Layout.fillWidth: true }
                    Button { text: "Revert"; enabled: cooler.dirty; onClicked: cooler.revertCooling() }
                    Button { text: "Apply"; highlighted: true; enabled: cooler.dirty; onClicked: cooler.applyCooling() }
                }
            }
        }

        // ==== Lighting
        ColumnLayout {
            spacing: 16
            Panel {
                Layout.fillWidth: true
                title: "Effect"
                subtitle: "Static and Rainbow wave run on the cooler; the others are animated by the RigDeck service"
                Segmented {
                    Layout.fillWidth: true
                    model: cooler.ledEffects.map(e => e.label)
                    currentIndex: cooler.ledEffects.findIndex(e => e.id === page.led.effect)
                    onActivated: (i) => page.sendLed(cooler.ledEffects[i].id, page.led.color, page.led.brightness, page.led.speed)
                }
                Banner {
                    visible: page.currentEffect.animated && !page.serviceUp
                    text: page.currentEffect.label + " is animated by the background service, which isn't running."
                    buttonText: "Start service"
                    onClicked: appState.startService()
                }
            }
            Panel {
                Layout.fillWidth: true
                title: "Color"
                enabled: page.currentEffect.usesColor
                subtitle: enabled ? "" : page.currentEffect.label + " doesn't use a color"
                ColorSwatches {
                    Layout.fillWidth: true
                    current: page.led.color
                    onPicked: (c) => page.sendLed(page.led.effect, c, page.led.brightness, page.led.speed)
                }
            }
            Panel {
                Layout.fillWidth: true
                title: "Brightness & speed"
                enabled: page.led.effect !== "off" && page.led.effect !== "rainbow-wave"
                GridLayout {
                    Layout.fillWidth: true
                    columns: 3
                    columnSpacing: 12
                    Label { text: "Brightness"; color: theme.muted; font.pixelSize: 13; Layout.preferredWidth: 90 }
                    Slider {
                        id: bright
                        Layout.fillWidth: true
                        from: 0; to: 100; stepSize: 5
                        value: page.led.brightness
                        Accessible.name: "Brightness"
                        onMoved: page.sendLed(page.led.effect, page.led.color, value, page.led.speed)
                    }
                    Label { text: Math.round(bright.value) + "%"; color: theme.text; font.pixelSize: 13; Layout.preferredWidth: 44 }
                    Label { text: "Speed"; color: theme.muted; font.pixelSize: 13 }
                    Slider {
                        id: speed
                        Layout.fillWidth: true
                        from: 1; to: 10; stepSize: 1
                        enabled: page.currentEffect.animated
                        value: page.led.speed
                        Accessible.name: "Effect speed"
                        onMoved: page.sendLed(page.led.effect, page.led.color, page.led.brightness, value)
                    }
                    Label { text: speed.enabled ? Math.round(speed.value) + " / 10" : "—"; color: theme.text; font.pixelSize: 13 }
                }
            }
        }

        // ==== Screen
        ColumnLayout {
            spacing: 16
            GridLayout {
                Layout.fillWidth: true
                columns: page.pageWidth >= 860 ? 2 : 1
                columnSpacing: 16; rowSpacing: 16

                Panel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 320
                    Layout.maximumWidth: page.pageWidth >= 860 ? 360 : 10000
                    title: "Preview"
                    subtitle: cooler.single ? "Showing one animation" : "Carousel, " + cooler.interval + " s each"
                    readonly property var showing: cooler.files.find(f => f.playing) || null
                    id: preview
                    Item {
                        Layout.alignment: Qt.AlignHCenter
                        implicitWidth: 200; implicitHeight: 200
                        Rectangle { anchors.fill: parent; radius: 100; color: "#000000"; border.color: theme.border }
                        AnimatedImage {
                            id: anim
                            anchors.fill: parent
                            visible: false
                            source: preview.showing ? preview.showing.preview : ""
                            playing: page.shown && !appState.reduceMotion
                            rotation: cooler.rotation
                            layer.enabled: true
                        }
                        Rectangle { id: mask; anchors.fill: parent; radius: 100; visible: false; layer.enabled: true }
                        MultiEffect {
                            anchors.fill: parent
                            source: anim
                            visible: anim.status === AnimatedImage.Ready
                            maskEnabled: true
                            maskSource: mask
                        }
                        ColumnLayout {
                            anchors.centerIn: parent
                            visible: anim.status !== AnimatedImage.Ready
                            spacing: 6
                            Icon { Layout.alignment: Qt.AlignHCenter; name: "image"; size: 32; color: "#90969c" }
                            Label { Layout.alignment: Qt.AlignHCenter; Layout.maximumWidth: 150
                                    text: preview.showing ? preview.showing.name : "Nothing selected"
                                    color: "#e2e5e8"; font.pixelSize: 11; elide: Text.ElideMiddle }
                            Label { Layout.alignment: Qt.AlignHCenter; text: "no preview"; color: "#90969c"; font.pixelSize: 10
                                    visible: preview.showing !== null }
                        }
                    }
                    Label {
                        text: "Previews exist for files uploaded with RigDeck."
                        color: theme.muted; font.pixelSize: 11; Layout.alignment: Qt.AlignHCenter
                        visible: preview.showing !== null && anim.status !== AnimatedImage.Ready
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 12; rowSpacing: 8
                        Label { text: "Rotation"; color: theme.muted; font.pixelSize: 13 }
                        Segmented { Layout.fillWidth: true; model: ["0°", "90°", "180°", "270°"]; chipHeight: 28
                                    currentIndex: [0, 90, 180, 270].indexOf(cooler.rotation)
                                    onActivated: (i) => cooler.setRotation([0, 90, 180, 270][i]) }
                        Label { text: "Units"; color: theme.muted; font.pixelSize: 13 }
                        Segmented { Layout.fillWidth: true; model: ["°C", "°F"]; chipHeight: 28; currentIndex: cooler.fahrenheit ? 1 : 0
                                    onActivated: (i) => cooler.setFahrenheit(i === 1) }
                    }
                }

                Panel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    title: "Animations"
                    subtitle: cooler.freeMb.toFixed(1) + " MB free on the cooler"
                    padding: 0
                    headerExtra: [
                        Button {
                            text: "Upload…"
                            enabled: !coolerBusy.shown
                            icon.source: "image://icons/upload/" + theme.text.toString().slice(-6)
                            onClicked: fileDialog.open()
                        }
                    ]
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.margins: 16
                        spacing: 10
                        RowLayout {
                            Layout.fillWidth: true
                            Segmented { model: ["One animation", "Carousel"]; currentIndex: cooler.single ? 0 : 1
                                        enabled: !coolerBusy.shown; onActivated: (i) => cooler.setSingle(i === 0) }
                            Item { Layout.fillWidth: true }
                            Label { visible: !cooler.single; text: "Seconds each"; color: theme.muted; font.pixelSize: 13 }
                            SpinBox { visible: !cooler.single; from: 5; to: 60; stepSize: 5; value: cooler.interval
                                      editable: true; Accessible.name: "Seconds per animation"
                                      onValueModified: cooler.setInterval(value) }
                        }
                        Label {
                            text: cooler.single ? "Pick the animation to show." : "Tick the animations to rotate through; arrows set the order."
                            color: theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true
                        }
                        RowLayout {
                            visible: cooler.busy !== ""
                            Layout.fillWidth: true
                            BusyIndicator { implicitWidth: 22; implicitHeight: 22; running: parent.visible }
                            Label { text: cooler.busy; color: theme.text; font.pixelSize: 13; Layout.fillWidth: true }
                        }
                        ProgressBar { visible: cooler.uploadProgress >= 0; Layout.fillWidth: true; value: cooler.uploadProgress }
                    }
                    ButtonGroup { id: radioGroup }
                    Repeater {
                        model: cooler.files
                        Item {
                            Layout.fillWidth: true
                            implicitHeight: 56
                            enabled: !coolerBusy.shown
                            Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: theme.border }
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                spacing: 10
                                RadioButton {
                                    visible: cooler.single
                                    checked: modelData.playing
                                    ButtonGroup.group: cooler.single ? radioGroup : null
                                    Accessible.name: "Show " + modelData.name
                                    onClicked: cooler.setPlaying(modelData.name, true)
                                }
                                CheckBox {
                                    visible: !cooler.single
                                    checked: modelData.playing
                                    Accessible.name: "Include " + modelData.name
                                    onClicked: cooler.setPlaying(modelData.name, checked)
                                }
                                Rectangle {
                                    implicitWidth: 32; implicitHeight: 32; radius: 16; color: "#000000"; clip: true
                                    border.color: theme.border
                                    Image { anchors.fill: parent; anchors.margins: 1; source: modelData.preview
                                            fillMode: Image.PreserveAspectCrop; visible: source != "" }
                                    Icon { anchors.centerIn: parent; name: "image"; size: 14; color: "#90969c"
                                           visible: modelData.preview === "" }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 0
                                    Label { text: modelData.name; color: theme.text; font.pixelSize: 13; elide: Text.ElideMiddle
                                            Layout.fillWidth: true }
                                    Label { visible: !cooler.single && modelData.playing; text: "#" + modelData.position + " in the rotation"
                                            color: theme.muted; font.pixelSize: 11 }
                                }
                                IconButton { visible: !cooler.single; iconName: "arrow-up"; tip: "Play earlier"
                                             enabled: index > 0; onClicked: cooler.move(modelData.name, -1) }
                                IconButton { visible: !cooler.single; iconName: "arrow-down"; tip: "Play later"
                                             enabled: index < cooler.files.length - 1; onClicked: cooler.move(modelData.name, 1) }
                                IconButton { iconName: "trash-2"; tip: "Delete " + modelData.name
                                             onClicked: { confirmDelete.name = modelData.name; confirmDelete.open() } }
                            }
                        }
                    }
                }
            }
        }
    }

    FileDialog {
        id: fileDialog
        title: "Upload to the cooler screen"
        nameFilters: ["Animations, videos and images (*.gif *.mp4 *.webm *.mkv *.mov *.avi *.png *.jpg *.jpeg *.webp)"]
        onAccepted: cooler.upload(selectedFile.toString())
    }
    Dialog {
        id: confirmDelete
        property string name: ""
        anchors.centerIn: Overlay.overlay
        modal: true
        title: "Delete " + name + "?"
        standardButtons: Dialog.Cancel | Dialog.Ok
        Label { text: "The file is removed from the cooler's storage."; color: theme.text }
        onAccepted: cooler.deleteFile(name)
    }
}
