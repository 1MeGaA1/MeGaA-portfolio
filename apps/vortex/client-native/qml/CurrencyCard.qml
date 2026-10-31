import QtQuick

Rectangle {
    id: root
    property int amount: 0
    property int price: 0
    property string unit: ""
    property color accent: Theme.cyan
    signal buy()

    implicitWidth: 150
    implicitHeight: 120
    color: Theme.surface
    border.color: ma.containsMouse ? accent : Theme.border
    border.width: 1
    Rectangle { anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 2; color: root.accent }

    Column {
        anchors.centerIn: parent
        spacing: 6
        width: parent.width - 24
        Text { width: parent.width; text: root.amount.toLocaleString(Qt.locale(), "f", 0)
               color: Theme.textPrimary; horizontalAlignment: Text.AlignHCenter
               font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 26 }
        Text { width: parent.width; text: root.unit; color: Theme.textMuted
               horizontalAlignment: Text.AlignHCenter
               font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 2 }
        Text { width: parent.width; text: "$" + root.price; color: Theme.green
               horizontalAlignment: Text.AlignHCenter
               font.family: Theme.fontMono; font.weight: Font.Medium; font.pixelSize: 15 }
    }
    MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.buy() }
    scale: ma.pressed ? 0.98 : 1.0
    Behavior on scale { NumberAnimation { duration: 90 } }
}
