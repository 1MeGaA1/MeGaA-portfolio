import QtQuick

// Bottom-center transient notice.
Rectangle {
    id: root
    property color accent: Theme.cyan
    function show(msg, ms, color) {
        label.text = msg
        root.accent = color || Theme.cyan
        root.opacity = 1
        hideTimer.interval = ms || 2600
        hideTimer.restart()
    }
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: 34
    width: label.implicitWidth + 40
    height: 40
    color: Theme.bgPanel
    border.color: accent
    border.width: 1
    opacity: 0
    visible: opacity > 0
    z: 100
    Behavior on opacity { NumberAnimation { duration: 200 } }
    Text {
        id: label
        anchors.centerIn: parent
        color: root.accent
        font.family: Theme.fontMono
        font.pixelSize: 12
        font.letterSpacing: 1
    }
    Timer { id: hideTimer; onTriggered: root.opacity = 0 }
}
