import QtQuick
import QtQuick.Controls.Basic
import "."

// Thin scroll bar that brightens on hover.
ScrollBar {
    id: sb
    implicitWidth: orientation === Qt.Vertical ? 8 : 100
    implicitHeight: orientation === Qt.Horizontal ? 8 : 100
    padding: 1
    policy: ScrollBar.AsNeeded
    contentItem: Rectangle {
        implicitWidth: 6
        implicitHeight: 6
        radius: 3
        color: sb.pressed ? Theme.cyan : sb.hovered ? Qt.rgba(0, 229 / 255, 1, 0.5) : Qt.rgba(130 / 255, 170 / 255, 1, 0.22)
        opacity: sb.size < 1 ? 1 : 0
    }
    background: Item {}
}
