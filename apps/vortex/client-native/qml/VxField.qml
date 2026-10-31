import QtQuick
import QtQuick.Controls.Basic

Column {
    id: root
    property alias text: field.text
    property string label: ""
    property bool echo: false
    property string placeholder: ""
    signal accepted()
    function clear() { field.text = "" }
    function forceActiveFocus() { field.forceActiveFocus() }
    spacing: 6

    Text {
        text: root.label
        color: Theme.textMuted
        font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 2
        font.capitalization: Font.AllUppercase
    }
    TextField {
        id: field
        width: parent.width
        placeholderText: root.placeholder
        echoMode: root.echo ? TextInput.Password : TextInput.Normal
        color: Theme.textPrimary
        placeholderTextColor: Theme.textFaint
        font.family: Theme.fontMono; font.pixelSize: 13
        selectionColor: Theme.cyan
        selectByMouse: true
        onAccepted: root.accepted()
        background: Rectangle {
            color: Theme.surfaceAlt
            border.color: field.activeFocus ? Theme.cyan : Theme.border
            border.width: 1
            radius: 0
        }
        leftPadding: 12; rightPadding: 12; topPadding: 10; bottomPadding: 10
    }
}
