import QtQuick

// A Repeater model that updates rows in place. Backends hand QML a new list on every poll; used
// directly as a model, the Repeater destroys and recreates every delegate each time (a flicker,
// and charts lose their animation). Each row keeps its delegate here; only `modelData` changes.
// Use: Repeater { model: LiveModel { values: backend.list } ... }  (delegates keep using modelData)
ListModel {
    id: root
    property var values: []
    dynamicRoles: true
    onValuesChanged: {
        const v = values || []
        for (let i = 0; i < v.length; i++) {
            if (i < count) setProperty(i, "modelData", v[i])
            else append({ modelData: v[i] })
        }
        if (count > v.length) remove(v.length, count - v.length)
    }
}
