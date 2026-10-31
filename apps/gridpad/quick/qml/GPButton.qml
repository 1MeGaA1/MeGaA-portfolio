import QtQuick
import QtQuick.Controls

// Dialog button, outlined; `primary` marks the default action with the accent border.
Button {
    id: b

    property bool primary: false

    implicitHeight: 30
    leftPadding: 14
    rightPadding: 14
    hoverEnabled: true
    focusPolicy: Qt.TabFocus
    font.family: Theme.sans
    font.pixelSize: 13
    font.weight: Theme.wNormal

    contentItem: Text {
        text: b.text
        textFormat: Text.PlainText
        font: b.font
        color: Theme.c.TEXT
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        implicitWidth: 76
        radius: 4
        color: b.down ? Theme.c.ACCENT_BG : (b.hovered ? Theme.c.HOVER : "transparent")
        border.color: b.primary || b.visualFocus ? Theme.c.ACCENT : Theme.c.BORDER
        Behavior on color { ColorAnimation { duration: 90 } }
    }

    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
