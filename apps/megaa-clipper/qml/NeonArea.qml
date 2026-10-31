import QtQuick
import QtQuick.Controls.Basic
import "."

// Multi-line version of NeonField.
TextArea {
    id: area
    color: Theme.text
    placeholderTextColor: Theme.dim
    selectionColor: Theme.pickBg
    selectedTextColor: Theme.cyan
    font.family: Theme.ui
    font.pixelSize: 13
    Keys.onEscapePressed: Store.releaseFocus()
    wrapMode: TextEdit.Wrap
    leftPadding: 11
    rightPadding: 11
    topPadding: 8
    bottomPadding: 8
    implicitHeight: 56
    background: Rectangle {
        radius: 9
        color: Theme.field
        border.width: 1
        border.color: area.activeFocus ? Theme.cyan : Theme.line2
    }
}
