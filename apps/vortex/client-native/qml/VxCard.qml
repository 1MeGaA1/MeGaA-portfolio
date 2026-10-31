import QtQuick

// A panel with a top accent line — the Vortex card look.
Rectangle {
    property color accent: Theme.cyan
    default property alias content: inner.data
    color: Theme.bgPanel
    border.color: Theme.border
    border.width: 1
    radius: 0

    Rectangle {   // top accent line
        anchors { top: parent.top; left: parent.left; right: parent.right }
        height: 2
        color: parent.accent
    }
    Item {
        id: inner
        anchors.fill: parent
        anchors.margins: 20
        anchors.topMargin: 22
    }
}
