import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

ApplicationWindow {
    id: root
    width: 1280
    height: 820
    minimumWidth: 420
    minimumHeight: 500
    visible: true
    title: "RigDeck"
    color: theme.window

    // Native controls (buttons, sliders, dialogs…) take their colors from this palette.
    palette {
        window: theme.window; windowText: theme.text
        base: theme.panel; alternateBase: theme.raised
        text: theme.text; placeholderText: theme.muted
        button: theme.raised; buttonText: theme.text
        highlight: theme.accent; highlightedText: theme.onAccent
        light: theme.raised; midlight: theme.raised; mid: theme.border; dark: theme.border; shadow: theme.window
        toolTipBase: theme.raised; toolTipText: theme.text
        link: theme.accent
        disabled.buttonText: theme.muted; disabled.text: theme.muted; disabled.windowText: theme.muted
        disabled.button: theme.raised; disabled.base: theme.panel
    }

    readonly property bool compact: width < 760
    property string currentId: "overview"
    readonly property var pages: [{ id: "overview", title: "Overview", icon: "layout-grid",
                                    page: Qt.resolvedUrl("pages/OverviewPage.qml") }]
                                 .concat(appState.nav)
                                 .concat([{ id: "settings", title: "Settings", icon: "settings",
                                            page: Qt.resolvedUrl("pages/SettingsPage.qml") }])

    // Sidebar sections, in this order; pages not listed go by kind (peripherals -> Devices)
    readonly property var sectionOrder: ["", "Monitoring", "Hardware", "Devices"]
    readonly property var placement: ({ overview: ["", 0], resources: ["Monitoring", 0], gamemon: ["Monitoring", 1],
        cpu: ["Hardware", 0], gpu: ["Hardware", 1], memory: ["Hardware", 2], storage: ["Hardware", 3],
        motherboard: ["Hardware", 4], cooler: ["Hardware", 5], network: ["Hardware", 6], bluetooth: ["Hardware", 7],
        keyboard: ["Devices", 0], mouse: ["Devices", 1], headset: ["Devices", 2], monitor: ["Devices", 3],
        webcam: ["Devices", 4] })
    function sectionOf(p) { return (placement[p.id] || [p.kind === "peripheral" ? "Devices" : "Hardware", 99])[0] }
    function rankOf(p) { return sectionOrder.indexOf(sectionOf(p)) * 100 + (placement[p.id] || ["", 99])[1] }
    readonly property var sidebarPages: pages.filter(p => p.id !== "settings" && inSidebar(p))
                                             .sort((a, b) => rankOf(a) - rankOf(b))
    // Pages whose device may only be connected through Bluetooth appear while it is.
    function inSidebar(p) {
        if (p.static !== false) return true
        const bt = p.bt || []
        return bt.indexOf("*") >= 0 ? bluez.connectedCount > 0 : bt.some(c => bluez.categories.indexOf(c) >= 0)
    }
    function navigate(id) {
        if (pages.some(p => p.id === id)) currentId = id
    }
    function showToast(text) { toast.show(text) }

    Component.onCompleted: { if (startPage) navigate(startPage); reportView() }
    // backends poll only for what's on screen; nothing while minimised or hidden
    function reportView() {
        appState.setView(visible && visibility !== Window.Minimized && visibility !== Window.Hidden, currentId)
    }
    onVisibilityChanged: reportView()
    onCurrentIdChanged: reportView()
    Connections { target: appState; function onToast(m) { root.showToast(m) } }
    Shortcut { sequence: StandardKey.Quit; onActivated: Qt.quit() }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---- top bar
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 48
            color: theme.panel
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.border }
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 12
                spacing: 10
                Rectangle {
                    implicitWidth: 28
                    implicitHeight: 28
                    radius: theme.radius
                    color: theme.accent
                    Icon { anchors.centerIn: parent; name: "gauge"; size: 16; color: theme.onAccent }
                }
                Label { text: "RigDeck"; color: theme.text; font.pixelSize: 14; font.weight: Font.DemiBold }
                Label { text: "Hardware Control Center"; color: theme.muted; font.pixelSize: 12; visible: !root.compact }
                Item { Layout.fillWidth: true }
                Chip {
                    visible: appState.update.state === "available"
                    label: "Update available — " + appState.update.latest
                    checkable: false
                    hoverEnabled: true
                    focusPolicy: Qt.StrongFocus
                    onClicked: root.navigate("settings")
                }
                IconButton {
                    iconName: theme.dark ? "sun" : "moon"
                    tip: theme.dark ? "Switch to light theme" : "Switch to dark theme"
                    onClicked: appState.setThemeMode(theme.dark ? "light" : "dark")
                }
                IconButton {
                    id: menuButton
                    iconName: "ellipsis-vertical"
                    tip: "More"
                    onClicked: menu.open()
                    Menu {
                        id: menu
                        y: menuButton.height
                        MenuItem { text: "Check for updates"; onTriggered: { appState.checkUpdates(); root.navigate("settings") } }
                        MenuItem { text: "Settings"; onTriggered: root.navigate("settings") }
                        MenuItem { text: "Project on GitHub"; onTriggered: appState.openUrl(appState.repoUrl) }
                        MenuSeparator {}
                        MenuItem { text: "Quit"; onTriggered: Qt.quit() }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // ---- sidebar
            Rectangle {
                Layout.fillHeight: true
                implicitWidth: root.compact ? 64 : 216
                color: theme.panel
                Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: theme.border }
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    anchors.rightMargin: 9
                    spacing: 4
                    Repeater {
                        model: LiveModel { values: root.sidebarPages }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            readonly property string section: root.sectionOf(modelData)
                            readonly property bool firstPeripheral: section !== ""
                                && (index === 0 || root.sectionOf(root.sidebarPages[index - 1]) !== section)
                            Label {
                                visible: parent.firstPeripheral && !root.compact
                                text: parent.section
                                color: theme.muted; font.pixelSize: 11; font.weight: Font.DemiBold
                                Layout.leftMargin: 12; Layout.topMargin: 10
                            }
                            Rectangle {  // compact sidebar: a divider instead of the heading
                                visible: parent.firstPeripheral && root.compact
                                Layout.fillWidth: true; implicitHeight: 1; color: theme.border
                                Layout.topMargin: 6; Layout.bottomMargin: 6
                            }
                            NavItem {
                                iconName: modelData.icon
                                label: modelData.title
                                compact: root.compact
                                current: root.currentId === modelData.id
                                onClicked: root.navigate(modelData.id)
                            }
                        }
                    }
                    Item { Layout.fillHeight: true }
                    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: theme.border }
                    NavItem {
                        iconName: "settings"
                        label: "Settings"
                        compact: root.compact
                        current: root.currentId === "settings"
                        onClicked: root.navigate("settings")
                    }
                }
            }

            // ---- content
            StackLayout {
                id: stack
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: Math.max(0, root.pages.findIndex(p => p.id === root.currentId))
                Repeater {
                    model: LiveModel { values: root.pages }
                    Loader {
                        // pages load on first visit, then stay alive for instant switching
                        active: StackLayout.isCurrentItem || item !== null
                        source: modelData.page
                        property bool shown: StackLayout.isCurrentItem
                        onLoaded: if (item.hasOwnProperty("shown")) item.shown = Qt.binding(() => shown)
                    }
                }
            }
        }
    }

    // ---- toast
    Rectangle {
        id: toast
        property alias text: toastLabel.text
        function show(t) { text = t; opacity = 1; hideTimer.restart() }
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        implicitWidth: Math.min(toastLabel.implicitWidth + 32, root.width - 48)
        implicitHeight: toastLabel.implicitHeight + 20
        radius: theme.radius
        color: theme.raised
        border.color: theme.border
        opacity: 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: appState.reduceMotion ? 0 : 150 } }
        Label {
            id: toastLabel
            anchors.centerIn: parent
            width: Math.min(implicitWidth, root.width - 80)
            color: theme.text
            wrapMode: Text.WordWrap
            font.pixelSize: 13
        }
        Timer { id: hideTimer; interval: 3500; onTriggered: toast.opacity = 0 }
        Accessible.role: Accessible.AlertMessage
        Accessible.name: toastLabel.text
    }
}
