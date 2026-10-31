import QtQuick
import QtQuick.Layouts
import "."

// Row of mutually exclusive options: model = [{value, label}], `current` = selected value.
Rectangle {
    id: seg
    property var model: []
    property var current
    property int buttonHeight: 32
    property int inset: 4               // space around the buttons
    property int fontSize: 11
    property real letterSpacing: 1.2
    signal picked(var value)

    implicitHeight: buttonHeight + inset * 2
    radius: 11
    color: Theme.field
    border.color: Theme.line2

    RowLayout {
        anchors.fill: parent
        anchors.margins: seg.inset
        spacing: 4
        Repeater {
            model: seg.model
            Rectangle {
                required property var modelData
                readonly property bool on: modelData.value === seg.current
                Layout.fillWidth: true
                Layout.preferredHeight: seg.buttonHeight
                radius: 8
                color: on ? Theme.cyanSoft : "transparent"
                border.color: on ? Qt.rgba(0, 229 / 255, 1, 0.45) : "transparent"
                Text {
                    anchors.centerIn: parent
                    text: modelData.label
                    color: parent.on ? Theme.cyan : (area.containsMouse ? Theme.text : Theme.muted)
                    font.family: Theme.display
                    font.pixelSize: seg.fontSize
                    font.weight: Font.DemiBold
                    font.letterSpacing: seg.letterSpacing
                    font.capitalization: Font.AllUppercase
                }
                MouseArea {
                    id: area
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: seg.picked(modelData.value)
                }
            }
        }
    }
}
