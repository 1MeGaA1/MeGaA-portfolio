import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Effects
import "."

// Clip tab, "Speaker switches" (web: ui/pro.js 517-560): from each switch on, the frame sits at its own position –
// for 2-person talks. Add one at the playhead, then drag the preview to frame the other person.
ColumnLayout {
    id: switches
    spacing: 7

    FieldLabel { label: "Speaker switches" }

    RowLayout {
        Layout.fillWidth: true
        spacing: 10
        NeonButton {
            small: true
            text: "+ Switch here"
            onClicked: { Store.releaseFocus(); Store.addKeyframe() }
        }
        Text {
            Layout.fillWidth: true
            text: "Add a switch at the playhead, then drag the preview to frame the other person."
            wrapMode: Text.WordWrap
            color: Theme.dim
            font.pixelSize: 11
        }
    }

    // the model is the COUNT, not the array: a drag on the preview reassigns Store.keyframes on every mouse move,
    // and an int model only rebuilds the rows when a switch is added or removed
    Repeater {
        model: Store.keyframes.length
        Item {
            id: row
            required property int index
            readonly property var k: Store.keyframes[index] || ({ t: 0, x: 0.5, y: 0.5 })
            readonly property bool on: index === Store.activeKeyframe   // the switch in use at the playhead
            Layout.fillWidth: true
            implicitHeight: 40

            // web .kf-row / .kf-row.on (cyan border, box-shadow 0 0 10px rgba(0,229,255,.15))
            Rectangle {
                anchors.fill: parent
                radius: 9
                color: Theme.field
                border.color: row.on ? Theme.cyan : Theme.line2
                layer.enabled: row.on
                layer.effect: MultiEffect {
                    shadowEnabled: true
                    shadowColor: Theme.cyan
                    shadowBlur: 0.5
                    shadowOpacity: 0.15
                    shadowHorizontalOffset: 0
                    shadowVerticalOffset: 0
                }
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 10
                Text {
                    text: Store.fmt(row.k.t)
                    color: Theme.text
                    font.family: Theme.mono
                    font.pixelSize: 12
                }
                Text {
                    Layout.fillWidth: true
                    text: `frame at ${Math.round(row.k.x * 100)}% · ${Math.round(row.k.y * 100)}%`
                    color: Theme.dim
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }
                IconButton {
                    size: 28
                    implicitHeight: 26
                    glyph: Theme.icPlay
                    ToolTip.text: "Go there"
                    onClicked: { Store.releaseFocus(); Store.gotoKeyframe(row.index) }
                }
                IconButton {
                    size: 28
                    implicitHeight: 26
                    danger: true
                    glyph: Theme.icClose
                    ToolTip.text: "Remove"
                    onClicked: { Store.releaseFocus(); Store.removeKeyframe(row.index) }
                }
            }
        }
    }
}
