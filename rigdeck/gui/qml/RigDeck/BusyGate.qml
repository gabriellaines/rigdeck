import QtQuick

// `shown` turns true only once `busy` has lasted `delay` ms, so quick changes don't grey a panel
// out and back (a visible flash). Invisible: takes no room in a layout.
Item {
    id: root
    property bool busy: false
    property int delay: 400
    property bool shown: false
    visible: false
    Timer { id: t; interval: root.delay; onTriggered: root.shown = root.busy }
    onBusyChanged: { if (busy) t.restart(); else { t.stop(); shown = false } }
}
