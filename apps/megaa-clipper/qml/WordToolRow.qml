import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Edit tab, "Cut words" / "Mute words": the label, then the tool toggle, how many words of the clip it marks
// and Clear (web ui/index.html 284-304). The Edit tab puts the hints and the mute sounds after it.
ColumnLayout {
    id: tool
    property string list: "cuts"   // "cuts" or "mutes"
    readonly property bool isCut: list === "cuts"
    spacing: 7

    FieldLabel { label: tool.isCut ? "Cut words" : "Mute words" }
    RowLayout {
        Layout.fillWidth: true
        spacing: 10
        NeonButton {
            small: true
            iconText: tool.isCut ? Theme.icCut : Theme.icMute
            text: tool.isCut ? "Cut tool" : "Mute tool"
            active: tool.isCut ? Store.cutMode : Store.muteMode
            activeColor: tool.isCut ? Theme.magenta : Theme.violet
            activeFill: tool.isCut ? 0.16 : 0.18
            activeGlow: tool.isCut ? 0.3 : 0.35
            ToolTip.visible: hovered
            ToolTip.delay: 600
            ToolTip.text: tool.isCut ? "Toggle the cut tool (X)" : "Toggle the mute tool (M)"
            onClicked: {
                Store.releaseFocus()
                if (tool.isCut) Store.setCutMode(!Store.cutMode)
                else Store.setMuteMode(!Store.muteMode)
            }
        }
        Text {
            Layout.fillWidth: true
            text: tool.isCut ? Store.cutLabel : Store.muteLabel
            color: Theme.dim
            font.pixelSize: 11
            elide: Text.ElideRight
        }
        NeonButton {
            small: true
            text: "Clear"
            onClicked: {
                Store.releaseFocus()
                if (tool.isCut) Store.clearCuts()
                else Store.clearMutes()
            }
        }
    }
}
