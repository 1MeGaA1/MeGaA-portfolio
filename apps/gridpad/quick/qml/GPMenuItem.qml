import QtQuick
import QtQuick.Controls

// One menu row; a checkable item shows an accent tick when checked.
MenuItem {
    id: it

    implicitHeight: 30
    implicitWidth: label.implicitWidth + leftPadding + rightPadding
    leftPadding: 10
    rightPadding: 28
    hoverEnabled: true

    indicator: Text {
        x: it.leftPadding
        anchors.verticalCenter: parent.verticalCenter
        visible: it.checkable && it.checked
        text: "✓"
        font.family: Theme.sans
        font.pixelSize: 13
        color: Theme.c.ACCENT
    }

    contentItem: Text {
        id: label
        leftPadding: it.checkable ? 20 : 0
        text: it.text
        textFormat: Text.PlainText
        font: it.font
        color: it.enabled ? Theme.c.TEXT : Theme.c.DIM
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        radius: 4
        color: it.highlighted && it.enabled ? Theme.c.HOVER : "transparent"
    }
}
