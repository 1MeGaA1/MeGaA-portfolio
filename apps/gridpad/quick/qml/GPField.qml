import QtQuick
import QtQuick.Controls

// One-line text input; `mono` switches to the notes font (separators, find text).
TextField {
    id: f

    property bool mono: false

    implicitHeight: 30
    leftPadding: 8
    rightPadding: 8
    selectByMouse: true
    font.family: f.mono ? Theme.mono : Theme.sans
    font.pixelSize: f.mono ? 12 : 13
    font.weight: Theme.wNormal
    color: Theme.c.TEXT
    placeholderTextColor: Theme.c.MUTED
    selectionColor: Theme.c.HI
    selectedTextColor: Theme.c.HI_TEXT

    background: Rectangle {
        implicitWidth: 160
        radius: 4
        color: Theme.c.FIELD
        border.color: f.activeFocus ? Theme.c.ACCENT : Theme.c.BORDER
        Behavior on border.color { ColorAnimation { duration: 120 } }
    }
}
