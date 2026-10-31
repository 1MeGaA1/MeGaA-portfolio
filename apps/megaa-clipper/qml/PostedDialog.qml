import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// "Mark as posted" (the ✓ on a rendered clip's card): the post goes into the earnings tracker.
NeonDialog {
    id: dlg
    title: "Mark as posted"
    width: 460
    property var target: null   // the clip (not `clip`: every Item has that)
    property string platform: "TikTok"

    function show(c) {
        target = c
        platform = "TikTok"
        urlBox.text = ""
        viewsBox.text = "0"
        open()
        urlBox.forceActiveFocus()
    }

    function save() {
        if (!target) return
        if (Store.postClip(target, platform, urlBox.text, parseInt(viewsBox.text) || 0)) close()
    }

    Text {
        Layout.fillWidth: true
        text: dlg.target ? `${dlg.target.name}${dlg.target.hook || dlg.target.post_caption ? " · " + (dlg.target.hook || dlg.target.post_caption) : ""}` : ""
        elide: Text.ElideRight
        color: Theme.muted
        font.pixelSize: 12
    }
    FieldLabel { label: "Platform" }
    Segmented {
        Layout.fillWidth: true
        buttonHeight: 28
        model: ["TikTok", "Reels", "Shorts", "X"].map(p => ({ value: p, label: p }))
        current: dlg.platform
        onPicked: (value) => dlg.platform = value
    }
    FieldLabel { label: "Link to the post" }
    NeonField {
        id: urlBox
        Layout.fillWidth: true
        placeholderText: "https://www.tiktok.com/@you/video/…"
        onAccepted: dlg.save()
    }
    FieldLabel { label: "Views so far" }
    NeonField {
        id: viewsBox
        Layout.preferredWidth: 160
        mono: true
        validator: IntValidator { bottom: 0 }
        onAccepted: dlg.save()
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.topMargin: 4
        NeonButton { primary: true; small: true; text: "Save to tracker"; onClicked: dlg.save() }
        Item { Layout.fillWidth: true }
    }
}
