import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Questions and messages (the classic QMessageBox calls).
//   ask(title, text, ["Save", "Discard", "Cancel"], callback[, defaultLabel])
//     first label = primary (default, Enter) unless defaultLabel names another; last label =
//     cancel (Esc); callback(label) gets the clicked label — Esc counts as the last one.
//     callback may be null.
//   alert(title, text) = ask(title, text, ["OK"], null)
// A request made while one is showing waits in a queue and opens after it closes.
// Buttons read right to left like the other dialogs: the primary sits rightmost.
GPDialog {
    id: dlg

    property var _queue: []
    property var _labels: ["OK"]
    property var _callback: null
    property string _chosen: ""
    property string _default: "OK"

    function ask(title, text, buttons, callback, defaultLabel) {
        const labels = (buttons && buttons.length) ? Array.from(buttons, String) : ["OK"]
        const fallback = labels.indexOf(String(defaultLabel)) >= 0 ? String(defaultLabel) : labels[0]
        dlg._queue.push({ title: String(title || ""), text: String(text || ""), labels: labels,
                          callback: (typeof callback === "function") ? callback : null,
                          defaultLabel: fallback })
        Qt.callLater(dlg._next)
    }

    function alert(title, text) {
        dlg.ask(title, text, ["OK"], null)
    }

    function _next() {
        if (dlg.visible || dlg._queue.length === 0)
            return
        const req = dlg._queue.shift()
        dlg.title = req.title
        message.text = req.text
        dlg._labels = req.labels
        dlg._default = req.defaultLabel
        dlg._callback = req.callback
        dlg._chosen = ""
        dlg.visible = true
        // Shown reversed (the first label sits rightmost); focus the default button.
        const primary = row.itemAt(row.count - 1 - req.labels.indexOf(req.defaultLabel))
        if (primary)
            primary.forceActiveFocus()
        else
            message.forceActiveFocus()
    }

    function _choose(label) {
        dlg._chosen = label
        dlg.accept()
    }

    function _deliver(label) {
        const cb = dlg._callback
        dlg._callback = null
        if (cb)
            cb(label)
    }

    title: ""
    preferredWidth: 420

    onAccepted: dlg._deliver(dlg._chosen)
    onRejected: dlg._deliver(dlg._labels[dlg._labels.length - 1])
    onClosed: Qt.callLater(dlg._next)

    Text {
        id: message
        objectName: "message"
        Layout.fillWidth: true
        Layout.preferredWidth: 100
        Layout.bottomMargin: 2
        textFormat: Text.PlainText  // messages carry sheet names, paths and "\n" — never HTML
        wrapMode: Text.Wrap
        font.family: Theme.sans
        font.pixelSize: 13
        font.weight: Theme.wNormal
        color: Theme.c.TEXT
        lineHeight: 1.15
        activeFocusOnTab: false

        // Holds focus only when there are no buttons to focus; Enter then takes the primary.
        Keys.onReturnPressed: dlg._choose(dlg._default)
        Keys.onEnterPressed: dlg._choose(dlg._default)
    }

    buttons: [
        Repeater {
            id: row
            model: dlg._labels.slice().reverse()
            delegate: GPButton {
                id: button
                required property int index
                required property string modelData
                text: modelData
                primary: button.modelData === dlg._default
                Keys.onReturnPressed: dlg._choose(button.modelData)
                Keys.onEnterPressed: dlg._choose(button.modelData)
                onClicked: dlg._choose(button.modelData)
            }
        }
    ]
}
