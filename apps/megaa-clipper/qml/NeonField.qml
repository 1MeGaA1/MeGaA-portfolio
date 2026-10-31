import QtQuick
import QtQuick.Controls.Basic
import "."

// Dark text field with a cyan focus ring. `bad` turns the border red.
TextField {
    id: field
    property bool bad: false
    property bool mono: false
    color: Theme.text
    placeholderTextColor: Theme.dim
    selectionColor: Theme.pickBg
    selectedTextColor: Theme.cyan
    font.family: mono ? Theme.mono : Theme.ui
    font.pixelSize: 13
    Keys.onEscapePressed: Store.releaseFocus()
    leftPadding: 11
    rightPadding: 11
    implicitHeight: 36
    background: Rectangle {
        radius: 9
        color: Theme.field
        border.width: 1
        border.color: field.bad ? Theme.bad : (field.activeFocus ? Theme.cyan : Theme.line2)
    }
}
