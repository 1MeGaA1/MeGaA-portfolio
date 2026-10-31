import QtQuick
import QtQuick.Layouts

Flow {
    id: root
    property var model: []          // [{key,label}]
    property string current: ""
    signal picked(string key)
    spacing: 8

    Repeater {
        model: root.model
        delegate: Rectangle {
            required property var modelData
            implicitWidth: t.implicitWidth + 26
            implicitHeight: 30
            color: root.current === modelData.key ? Qt.rgba(0, 0.9, 1, 0.10) : "transparent"
            border.color: root.current === modelData.key ? Theme.cyan : Theme.border
            border.width: 1
            Text {
                id: t; anchors.centerIn: parent; text: modelData.label
                color: root.current === modelData.key ? Theme.cyan : Theme.textMuted
                font.family: Theme.fontMono; font.pixelSize: 11; font.letterSpacing: 2
            }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: root.picked(modelData.key) }
        }
    }
}
