import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Right panel: the clip being edited (range, framing, hook), its captions and its edits.
Panel {
    id: insp
    title: "Clip"
    tag: Store.editing ? `EDITING · ${Store.editing}` : "NEW"
    property string tab: "clip"
    onTabChanged: Store.releaseFocus()   // a text box on the old tab must not keep the keys while hidden

    header: NeonButton {
        small: true
        text: "New"
        onClicked: { Store.releaseFocus(); Store.newClip(true) }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Segmented {
            Layout.fillWidth: true
            Layout.margins: 14
            Layout.bottomMargin: 6
            model: [{ value: "clip", label: "Clip" }, { value: "captions", label: "Captions" }, { value: "edit", label: "Edit" }]
            current: insp.tab
            onPicked: (value) => insp.tab = value
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: Math.max(0, ["clip", "captions", "edit"].indexOf(insp.tab))
            ClipTab {}
            CaptionsTab {}
            EditTab {}
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 14
            spacing: 10
            NeonButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                text: Store.editing ? "Save changes" : "Add to queue"
                ToolTip.visible: hovered
                ToolTip.delay: 600
                ToolTip.text: "Enter"
                onClicked: { Store.releaseFocus(); Store.addClip(false) }
            }
            NeonButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 1.2
                primary: true
                iconText: Theme.icRender
                text: "Render clip"
                enabled: !Store.busy
                ToolTip.visible: hovered
                ToolTip.delay: 600
                ToolTip.text: "Shift+Enter"
                onClicked: { Store.releaseFocus(); Store.addClip(true) }
            }
        }
    }
}
