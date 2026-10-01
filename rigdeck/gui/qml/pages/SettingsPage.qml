import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    readonly property var u: appState.update

    PageHeader { title: "Settings"; subtitle: "RigDeck " + appState.version }

    Panel {
        Layout.fillWidth: true
        title: "Appearance"
        RowLayout {
            Layout.fillWidth: true
            Label { text: "Theme"; color: theme.text; font.pixelSize: 14; Layout.fillWidth: true }
            Segmented {
                model: ["System", "Light", "Dark"]
                currentIndex: ["system", "light", "dark"].indexOf(theme.mode)
                onActivated: (i) => appState.setThemeMode(["system", "light", "dark"][i])
            }
        }
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Label { text: "Reduce motion"; color: theme.text; font.pixelSize: 14; Layout.fillWidth: true }
                Label { text: "Stops the spinning fan and other animations"; color: theme.muted; font.pixelSize: 12
                        Layout.fillWidth: true }
            }
            Switch { checked: appState.reduceMotion; onToggled: appState.reduceMotion = checked
                     Accessible.name: "Reduce motion" }
        }
    }

    Panel {
        Layout.fillWidth: true
        title: "Background service"
        subtitle: "Sends CPU temperature to the cooler and animates software lighting effects"
        RowLayout {
            Layout.fillWidth: true
            StatusDot { tone: appState.serviceState === "active" ? theme.live : theme.warning }
            Label {
                text: appState.serviceState === "active" ? "Running"
                      : appState.serviceState === "not-installed" ? "Not installed — run ./install.sh"
                      : "Not running (" + appState.serviceState + ")"
                color: theme.text
                font.pixelSize: 14
                Layout.fillWidth: true
            }
            Button {
                visible: appState.serviceState !== "active" && appState.serviceState !== "not-installed"
                text: "Start service"
                onClicked: appState.startService()
            }
        }
    }

    Panel {
        Layout.fillWidth: true
        title: "Updates"
        subtitle: page.u.method === "package" ? "Installed by your package manager"
                  : page.u.method === "source" ? "Running from a source checkout" : "Installed with install.sh"
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Label {
                    color: theme.text
                    font.pixelSize: 14
                    text: page.u.state === "checking" ? "Checking…"
                        : page.u.state === "available" ? "Version " + page.u.latest + " is available (you have " + page.u.current + ")"
                        : page.u.state === "current" ? "You have the latest version (" + page.u.current + ")"
                        : page.u.state === "updating" ? "Updating…"
                        : page.u.state === "updated" ? "Updated to " + page.u.latest + " — restart to use it"
                        : page.u.state === "error" ? "Update check failed: " + page.u.error
                        : "Version " + page.u.current
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Label {
                    visible: page.u.state === "available" && page.u.method !== "installer"
                    text: page.u.method === "package" ? "Update it with your package manager (e.g. yay -Syu)."
                                                      : "Pull the latest code with git."
                    color: theme.muted
                    font.pixelSize: 12
                }
            }
            BusyIndicator { running: page.u.state === "checking" || page.u.state === "updating"; visible: running
                            implicitWidth: 28; implicitHeight: 28 }
            Button {
                text: "Check now"
                enabled: page.u.state !== "checking" && page.u.state !== "updating"
                visible: page.u.state !== "available" && page.u.state !== "updated"
                onClicked: appState.checkUpdates()
            }
            Button {
                visible: page.u.state === "available" && page.u.method === "installer"
                text: "Update now"
                highlighted: true
                onClicked: appState.applyUpdate()
            }
            Button {
                visible: page.u.state === "updated"
                text: "Restart RigDeck"
                highlighted: true
                onClicked: appState.restartApp()
            }
        }
        ActionLink {
            visible: page.u.url !== "" && (page.u.state === "available" || page.u.state === "updated")
            label: "What's new"
            onClicked: appState.openUrl(page.u.url)
        }
        Rectangle {
            visible: page.u.log !== ""
            Layout.fillWidth: true
            implicitHeight: Math.min(logText.implicitHeight + 16, 180)
            color: theme.raised
            radius: theme.radius
            border.color: theme.border
            ScrollView {
                anchors.fill: parent
                anchors.margins: 8
                Label { id: logText; text: page.u.log; color: theme.muted; font.family: "monospace"; font.pixelSize: 11 }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Label { text: "Check for updates when RigDeck starts"; color: theme.text; font.pixelSize: 14; Layout.fillWidth: true }
            Switch { checked: appState.checkUpdatesOnStart; onToggled: appState.checkUpdatesOnStart = checked
                     Accessible.name: "Check for updates when RigDeck starts" }
        }
    }

    Panel {
        Layout.fillWidth: true
        title: "About"
        KeyValue { key: "Version"; value: appState.version }
        KeyValue { key: "License"; value: "GPL-3.0-or-later · icons: Lucide (ISC)" }
        KeyValue { key: "Session"; value: system.info.session || "" }
        ActionLink { label: "Project on GitHub"; onClicked: appState.openUrl(appState.repoUrl) }
        Label {
            text: "Not affiliated with GIGABYTE. Cooler support is reverse-engineered for interoperability; "
                  + "RigDeck only sends commands observed from GIGABYTE Control Center and never touches firmware."
            color: theme.muted
            font.pixelSize: 12
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
    }
}
