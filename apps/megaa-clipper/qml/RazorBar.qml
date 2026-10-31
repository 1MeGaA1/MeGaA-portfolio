import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// CapCut-style razor over the waveform: split the clip at the playhead, delete (or bring back) the part picked
// on the waveform, or turn the parts into separate clips in the queue.
RowLayout {
    id: bar
    property string hint: ""     // what the waveform under the mouse can do (from the strip)
    signal toClips()             // "To clips" – the stage asks first
    readonly property bool hasRange: Store.inT !== null && Store.outT !== null && Store.outT > Store.inT
    readonly property var part: Store.selectedPart >= 0 ? Store.parts[Store.selectedPart] || null : null
    readonly property bool partGone: !!part && Store.partRemoved(Store.selectedPart)
    // the chips lose their words when the text next to them would get under 165 px (the longest messages need that)
    readonly property bool compact: width < splitChip.wideWidth + deleteChip.wideWidth + clipsChip.wideWidth + 3 * spacing + 2 + 165
    spacing: 6

    readonly property string status: {
        const n = Store.parts.length
        if (!hasRange) return "Pick a clip to use the razor"
        if (!part && Store.allPartsRemoved()) return n > 1 ? "Every part is deleted · pick one" : "The clip is deleted · click it"
        if (n < 2 && !part) return "S splits the clip at the playhead"
        if (!part) return `${n} parts · click one to pick it`
        return `Part ${Store.selectedPart + 1} of ${n} · ${(part[1] - part[0]).toFixed(1)}s${partGone ? " · deleted" : ""}`
    }

    component ToolChip: Rectangle {
        id: chip
        property string glyph: ""
        property string text: ""
        property string tip: ""
        property bool danger: false
        signal clicked()
        readonly property real wideWidth: glyphText.implicitWidth + row.spacing + labelText.implicitWidth + 18   // with its words
        implicitWidth: row.implicitWidth + (bar.compact ? 14 : 18)
        implicitHeight: 26
        radius: 8
        opacity: enabled ? 1 : 0.35
        color: area.pressed ? Qt.rgba(0, 229 / 255, 1, 0.12) : area.containsMouse ? Qt.rgba(0, 229 / 255, 1, 0.06) : "transparent"
        border.color: area.containsMouse ? (danger ? Theme.bad : Qt.rgba(0, 229 / 255, 1, 0.45)) : Theme.line2
        readonly property color ink: area.containsMouse ? (danger ? Theme.bad : Theme.cyan) : Theme.muted
        Row {
            id: row
            anchors.centerIn: parent
            spacing: 5
            Text {
                id: glyphText
                anchors.verticalCenter: parent.verticalCenter
                text: chip.glyph
                font.family: Theme.icons
                font.pixelSize: 12
                color: chip.ink
            }
            Text {
                id: labelText
                anchors.verticalCenter: parent.verticalCenter
                visible: !bar.compact
                text: chip.text
                color: chip.ink
                font.family: Theme.display
                font.pixelSize: 10
                font.weight: Font.DemiBold
                font.letterSpacing: 1
                font.capitalization: Font.AllUppercase
            }
        }
        MouseArea {
            id: area
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: { Store.releaseFocus(); chip.clicked() }
        }
        ToolTip.visible: area.containsMouse && tip !== ""
        ToolTip.delay: 500
        ToolTip.text: tip
    }

    ToolChip {
        id: splitChip
        glyph: Theme.icCut
        text: "Split"
        tip: "Split the clip at the playhead (S)"
        enabled: bar.hasRange
        onClicked: Store.addSplit()
    }
    ToolChip {
        id: deleteChip
        glyph: bar.partGone ? Theme.icUndo : Theme.icDelete
        text: bar.partGone ? "Restore" : "Delete"
        tip: bar.partGone ? "Bring the picked part back (Delete)" : "Remove the picked part from the clip (Delete)"
        danger: !bar.partGone
        enabled: !!bar.part
        onClicked: Store.deletePart()
    }
    Text {
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        Layout.leftMargin: 2
        elide: Text.ElideRight
        text: bar.hint || bar.status
        color: bar.hint ? Theme.muted : Theme.dim
        font.pixelSize: 11
        HoverHandler { id: textHover }
        ToolTip.visible: textHover.hovered && truncated   // a very narrow window: the whole text
        ToolTip.delay: 500
        ToolTip.text: text
    }
    ToolChip {
        id: clipsChip
        glyph: Theme.icClips
        text: "To clips"
        tip: "Make each part its own clip in the queue"
        enabled: Store.parts.length > 1 && !Store.allPartsRemoved()
        onClicked: bar.toClips()
    }
}
