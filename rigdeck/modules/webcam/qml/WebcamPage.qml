import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    property bool preview: false
    readonly property bool has: webcam.cameras.length > 0

    Connections { target: webcam; function onToast(m) { root.showToast(m) } }
    onShownChanged: if (!shown) preview = false   // release the camera when leaving the page

    function shownValue(c, v) {
        if (c.unit === "kelvin") return v + " K"
        if (c.unit === "zoom") return (v / 100).toFixed(1) + "×"
        if (c.unit === "degrees") return Math.round(v / 3600) + "°"
        return v
    }

    PageHeader {
        title: webcam.name || "Webcam"
        subtitle: page.has ? webcam.cameras[webcam.index].path + " · settings are re-applied whenever it's plugged in" : ""
        status: page.has ? "Connected" : "Not connected"
        tone: page.has ? theme.live : theme.warning
    }

    Banner {
        visible: !page.has
        text: "No webcam found. Plug one in — it shows up here within a few seconds."
    }
    Banner {
        visible: page.has && webcam.error !== ""
        tone: "error"
        text: webcam.error
        buttonText: "Retry"
        onClicked: webcam.refresh()
    }

    RowLayout {
        Layout.fillWidth: true
        visible: page.has
        spacing: 12
        Segmented {
            Layout.fillWidth: true
            visible: webcam.cameras.length > 1
            model: webcam.cameras.map(c => c.name)
            currentIndex: webcam.index
            onActivated: (ix) => webcam.select(ix)
        }
        Item { Layout.fillWidth: true }
        Button { text: page.preview ? "Hide preview" : "Show preview"; onClicked: page.preview = !page.preview }
        Button { text: "Reset to defaults"; onClicked: webcam.resetDefaults() }
    }

    // Live picture; a separate file so the page still works without Qt Multimedia.
    Loader {
        id: previewLoader
        Layout.fillWidth: true
        Layout.preferredHeight: active && status === Loader.Ready ? width * 9 / 16 : 0
        Layout.maximumHeight: 480
        active: page.preview && page.has
        source: "CameraPreview.qml"
        onLoaded: item.cameraName = Qt.binding(() => webcam.name)
    }
    Label {
        visible: page.preview && previewLoader.status === Loader.Error
        text: "The preview needs Qt Multimedia (on Arch: qt6-multimedia)."
        color: theme.muted; font.pixelSize: 12
    }

    Repeater {
        model: LiveModel { values: webcam.groups }
        Panel {
            id: group
            Layout.fillWidth: true
            title: modelData.title
            readonly property var items: modelData.controls
            Repeater {
                model: LiveModel { values: group.items }
                SettingRow {
                    id: row
                    readonly property var c: modelData
                    title: c.label
                    description: c.inactive ? "Controlled automatically — turn the automatic option off to adjust"
                                            : c.hint
                    enabled: !c.inactive
                    opacity: c.inactive ? 0.6 : 1

                    Toggle {
                        visible: row.c.type === "bool"
                        checked: row.c.value !== 0
                        Accessible.name: row.c.label
                        onToggled: webcam.set(row.c.key, checked ? 1 : 0)
                    }
                    Segmented {
                        visible: row.c.type === "menu" || row.c.type === "intmenu"
                        model: (row.c.menu || []).map(m => m.label)
                        currentIndex: (row.c.menu || []).findIndex(m => m.value === row.c.value)
                        onActivated: (ix) => webcam.set(row.c.key, row.c.menu[ix].value)
                    }
                    Slider {
                        id: sl
                        visible: row.c.type === "int"
                        Layout.preferredWidth: 240
                        from: row.c.min; to: row.c.max; stepSize: row.c.step
                        value: row.c.value
                        Accessible.name: row.c.label
                        onMoved: webcam.set(row.c.key, Math.round(value))
                    }
                    Label {
                        visible: row.c.type === "int"
                        text: page.shownValue(row.c, Math.round(sl.value))
                        color: theme.text; font.pixelSize: 13
                        Layout.preferredWidth: 64
                        horizontalAlignment: Text.AlignRight
                    }
                    IconButton {
                        visible: row.c.type === "int" && row.c.value !== row.c.default && !row.c.inactive
                        iconName: "rotate-cw"
                        tip: "Back to default (" + page.shownValue(row.c, row.c.default) + ")"
                        onClicked: webcam.set(row.c.key, row.c.default)
                    }
                    Item { visible: !(row.c.type === "int" && row.c.value !== row.c.default && !row.c.inactive)
                           implicitWidth: 32 }
                }
            }
        }
    }
}
