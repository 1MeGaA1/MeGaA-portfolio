import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Settings: the Anthropic API key for the AI moment picks (saved only on this PC, never shown again).
NeonDialog {
    id: dlg
    title: "Settings"
    property var info: ({ has_key: false, key_hint: "" })

    function show() {
        info = backend.settings()
        keyField.text = ""
        open()
        keyField.forceActiveFocus()
    }

    function save() {
        const key = keyField.text.trim()
        if (!key) { Store.toast("Paste your API key first.", "info"); return }
        const res = backend.saveApiKey(key)
        if (res.error) { Store.toast(res.error, "error"); return }
        keyField.text = ""
        close()
        Store.toast("API key saved.", "ok")
    }

    function remove() {
        const res = backend.saveApiKey("")
        if (res.error) { Store.toast(res.error, "error"); return }
        info = backend.settings()
        Store.toast("API key removed.", "ok")
    }

    FieldLabel { label: "Anthropic API key"; note: "for AI moment picks" }
    NeonField {
        id: keyField
        Layout.fillWidth: true
        mono: true
        echoMode: TextInput.Password
        placeholderText: "sk-ant-…"
        onAccepted: dlg.save()
    }
    Text {
        text: dlg.info.has_key ? `A key is saved (${dlg.info.key_hint}).` : "No key saved – AI picks are off. Free picks still work."
        color: dlg.info.has_key ? Theme.ok : Theme.muted
        font.pixelSize: 12
    }
    Text {
        Layout.fillWidth: true
        text: "AI picks send the transcript text (not the video) to Claude and cost about $0.10–0.20 per hour of "
              + "video. The key is saved only on this PC (clipper/data/settings.json). Get a key at console.anthropic.com."
        wrapMode: Text.WordWrap
        color: Theme.dim
        font.pixelSize: 12
        lineHeight: 1.2
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.topMargin: 4
        spacing: 10
        NeonButton { primary: true; small: true; text: "Save"; onClicked: dlg.save() }
        NeonButton { small: true; text: "Remove key"; visible: dlg.info.has_key; onClicked: dlg.remove() }
        Item { Layout.fillWidth: true }
    }
}
