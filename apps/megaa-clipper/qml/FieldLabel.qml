import QtQuick
import "."

// Small uppercase label above a field, with an optional dim note after it.
Text {
    property string note: ""
    property string label: ""
    textFormat: Text.StyledText
    text: note ? `${label.toUpperCase()} <font color="${Theme.dim}">· ${note}</font>` : label.toUpperCase()
    color: Theme.muted
    font.family: Theme.display
    font.pixelSize: 11
    font.weight: Font.DemiBold
    font.letterSpacing: 1.6
}
