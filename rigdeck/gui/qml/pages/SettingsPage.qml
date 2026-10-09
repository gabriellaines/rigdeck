import QtCore
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import RigDeck

PageScroll {
    id: page
    property bool shown: true
    readonly property var u: appState.update

    PageHeader { title: "Settings"; subtitle: "RigDeck " + appState.version }
    Connections { target: settingsFile; function onToast(m) { root.showToast(m) } }
    Connections { target: customThemes; function onToast(m) { root.showToast(m) } }

    Panel {
        Layout.fillWidth: true
        title: "Appearance"
        RowLayout {
            Layout.fillWidth: true
            Label { text: "Theme"; color: theme.text; font.pixelSize: 14; Layout.fillWidth: true }
            Segmented {
                readonly property var values: ["system"].concat(theme.themes.map(t => t.value))
                model: ["System"].concat(theme.themes.map(t => t.label))
                currentIndex: values.indexOf(theme.mode)
                onActivated: (i) => appState.setThemeMode(values[i])
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            visible: theme.customThemes.length > 0
            spacing: 4
            Label { text: "Your themes"; color: theme.text; font.pixelSize: 14 }
            Repeater {
                model: LiveModel { values: theme.customThemes }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Label { text: modelData.name; color: theme.muted; font.pixelSize: 13; Layout.fillWidth: true }
                    IconButton {
                        iconName: "trash-2"
                        tip: "Remove this theme"
                        onClicked: customThemes.remove(modelData.slug)
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Button {
                text: "Import theme file…"
                icon.source: "image://icons/upload/" + theme.text.toString().slice(-6)
                enabled: customThemes.busy === ""
                onClicked: importThemeDialog.open()
            }
            Button {
                text: "Export theme template…"
                icon.source: "image://icons/download/" + theme.text.toString().slice(-6)
                enabled: customThemes.busy === ""
                onClicked: exportThemeDialog.open()
            }
            BusyIndicator { running: customThemes.busy !== ""; visible: running; implicitWidth: 28; implicitHeight: 28 }
            Label { text: customThemes.busy; color: theme.muted; font.pixelSize: 13; Layout.fillWidth: true; elide: Text.ElideRight }
        }
        Label {
            visible: customThemes.error !== ""
            text: customThemes.error
            color: theme.error; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true
        }
        ActionLink {
            label: "How to write a theme file"
            onClicked: appState.openUrl(appState.repoUrl + "/blob/main/docs/custom-themes.md")
        }
        FileDialog {
            id: importThemeDialog
            title: "Import a RigDeck theme file"
            nameFilters: ["Theme files (*.json)", "All files (*)"]
            onAccepted: customThemes.importFile(selectedFile.toString())
        }
        FileDialog {
            id: exportThemeDialog
            title: "Save a theme template to edit"
            fileMode: FileDialog.SaveFile
            defaultSuffix: "json"
            currentFile: StandardPaths.writableLocation(StandardPaths.HomeLocation) + "/my-theme.json"
            nameFilters: ["Theme files (*.json)"]
            onAccepted: customThemes.exportTemplate(selectedFile.toString())
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
            Toggle { checked: appState.reduceMotion; onToggled: appState.reduceMotion = checked
                     Accessible.name: "Reduce motion" }
        }
    }

    Panel {
        Layout.fillWidth: true
        title: "Background service"
        subtitle: "Keeps things working while RigDeck is closed: CPU temperature for the cooler, lighting effects, and re-applying your headset, webcam and keyboard settings"
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
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Label { text: "Check for updates automatically"; color: theme.text; font.pixelSize: 14; Layout.fillWidth: true }
                Label { text: "When RigDeck starts and every few hours; the top bar shows when a new version is out"
                        color: theme.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            }
            Toggle { checked: appState.checkUpdatesOnStart; onToggled: appState.checkUpdatesOnStart = checked
                     Accessible.name: "Check for updates automatically" }
        }
    }

    Panel {
        Layout.fillWidth: true
        title: "Settings file"
        subtitle: "All your device settings in one file: export a backup, or import one to set everything at once"
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Button {
                text: "Import settings file…"
                highlighted: true
                icon.source: "image://icons/upload/ffffff"
                enabled: settingsFile.busy === ""
                onClicked: openDialog.open()
            }
            Button {
                text: "Export current settings…"
                icon.source: "image://icons/download/" + theme.text.toString().slice(-6)
                enabled: settingsFile.busy === ""
                onClicked: saveDialog.open()
            }
            BusyIndicator { running: settingsFile.busy !== ""; visible: running; implicitWidth: 28; implicitHeight: 28 }
            Label { text: settingsFile.busy; color: theme.muted; font.pixelSize: 13; Layout.fillWidth: true; elide: Text.ElideRight }
        }
        ColumnLayout {
            visible: settingsFile.results.length > 0
            Layout.fillWidth: true
            spacing: 6
            Label { text: settingsFile.file; color: theme.muted; font.pixelSize: 12 }
            Repeater {
                model: LiveModel { values: settingsFile.results }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Icon { name: modelData.ok ? "check" : "circle-alert"; size: 16
                           color: modelData.ok ? theme.live : theme.warning; Layout.alignment: Qt.AlignTop }
                    Label {
                        text: "<b>" + modelData.title + "</b> — " + modelData.message
                        textFormat: Text.StyledText
                        color: theme.text; font.pixelSize: 13; wrapMode: Text.WordWrap; Layout.fillWidth: true
                    }
                }
            }
        }
        ActionLink {
            label: "How to write a settings file"
            onClicked: appState.openUrl(appState.repoUrl + "/blob/main/docs/settings-file.md")
        }
        FileDialog {
            id: openDialog
            title: "Import a RigDeck settings file"
            nameFilters: ["Settings files (*.json)", "All files (*)"]
            onAccepted: settingsFile.importFile(selectedFile.toString())
        }
        FileDialog {
            id: saveDialog
            title: "Export your settings"
            fileMode: FileDialog.SaveFile
            defaultSuffix: "json"
            currentFile: StandardPaths.writableLocation(StandardPaths.HomeLocation) + "/rigdeck-settings.json"
            nameFilters: ["Settings files (*.json)"]
            onAccepted: settingsFile.exportFile(selectedFile.toString())
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
            text: "Not affiliated with any hardware maker; product names belong to their owners. Device support "
                  + "comes from public standards, open-source projects and interoperability research. RigDeck "
                  + "never updates or changes device firmware."
            color: theme.muted
            font.pixelSize: 12
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
    }
}
