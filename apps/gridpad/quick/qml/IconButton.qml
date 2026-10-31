import QtQuick
import QtQuick.Controls

// Flat toolbar button: an icon, optional text beside it, hover / pressed / checked tints.
AbstractButton {
    id: btn

    property string iconName
    property string tip
    property int iconSize: 16
    property color iconColor: btn.checked ? Theme.c.ACCENT : (btn.hovered ? Theme.c.TEXT : Theme.c.ICON)

    implicitHeight: 28
    implicitWidth: btn.text !== "" ? row.implicitWidth + 16 : 28
    focusPolicy: Qt.NoFocus
    hoverEnabled: true
    font.family: Theme.sans
    font.pixelSize: 12
    font.weight: Font.Normal

    ToolTip.visible: btn.tip !== "" && btn.hovered
    ToolTip.text: btn.tip
    ToolTip.delay: 600

    background: Rectangle {
        radius: 4
        color: btn.down || btn.checked ? Theme.c.ACCENT_BG : (btn.hovered ? Theme.c.HOVER : "transparent")
        Behavior on color { ColorAnimation { duration: 90 } }
    }

    contentItem: Item {
        Row {
            id: row
            anchors.centerIn: parent
            spacing: 6
            Icon {
                anchors.verticalCenter: parent.verticalCenter
                name: btn.iconName
                color: btn.iconColor
                size: btn.iconSize
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                visible: btn.text !== ""
                text: btn.text
                font: btn.font
                color: btn.iconColor
            }
        }
    }

    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
