import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// A yes / no question (Store.ask): Enter or the OK button runs the action, Esc or Cancel doesn't.
NeonDialog {
    id: dlg
    width: 440
    property string text: ""
    property string okText: "OK"
    property var action: null

    function show(title, text, okText, action) {
        dlg.title = title
        dlg.text = text
        dlg.okText = okText || "OK"
        dlg.action = action
        open()
        keys.forceActiveFocus()
    }

    function accept() {
        const fn = action
        action = null
        close()
        if (fn) fn()
    }

    onClosed: action = null

    Text {
        Layout.fillWidth: true
        text: dlg.text
        wrapMode: Text.WordWrap
        color: Theme.muted
        font.pixelSize: 13
        lineHeight: 1.25
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.topMargin: 6
        spacing: 10
        Item {
            id: keys
            Layout.fillWidth: true
            focus: true
            Keys.onReturnPressed: dlg.accept()
            Keys.onEnterPressed: dlg.accept()
        }
        NeonButton { text: "Cancel"; onClicked: dlg.close() }
        NeonButton { primary: true; text: dlg.okText; onClicked: dlg.accept() }
    }
}
