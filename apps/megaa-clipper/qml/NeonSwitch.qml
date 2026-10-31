import QtQuick
import QtQuick.Controls.Basic
import "."

// Small toggle switch with a label to its right.
Switch {
    id: sw
    property bool big: false
    property color accent: Theme.cyan     // track border and knob while on
    property real accentFill: 0.18        // track tint while on (web: .18 cyan, .22 in the teaser box)
    focusPolicy: Qt.NoFocus
    font.family: Theme.ui
    font.pixelSize: big ? 13 : 12
    spacing: 9
    indicator: Rectangle {
        x: sw.leftPadding
        y: (sw.height - height) / 2
        width: 30; height: 17; radius: 9
        color: sw.checked ? Qt.rgba(sw.accent.r, sw.accent.g, sw.accent.b, sw.accentFill) : Theme.raised
        border.color: sw.checked ? sw.accent : Theme.line2
        Rectangle {
            x: sw.checked ? 15 : 2
            y: 2
            width: 11; height: 11; radius: 6
            color: sw.checked ? sw.accent : Theme.muted
            Behavior on x { NumberAnimation { duration: 150 } }
        }
    }
    contentItem: Text {
        leftPadding: sw.indicator.width + sw.spacing
        text: sw.text
        font: sw.font
        color: sw.big ? Theme.text : Theme.muted
        verticalAlignment: Text.AlignVCenter
    }
}
