import QtQuick
import QtQuick.Layouts
import "."

// Glass panel with a cyan-marked title, HUD corner ticks and a header row for extra controls.
Rectangle {
    id: panel
    property string title: ""
    property string tag: ""
    default property alias content: body.data
    property alias header: headerExtra.data
    property bool showHeader: true

    color: Theme.panel
    radius: Theme.radius
    border.color: Theme.line
    border.width: 1

    // HUD corner ticks
    Repeater {
        model: [[0, 0], [1, 1]]
        Item {
            x: modelData[0] ? panel.width - 14 : -1
            y: modelData[1] ? panel.height - 14 : -1
            width: 15; height: 15
            opacity: 0.55
            Rectangle { width: 14; height: 1; color: Theme.cyan; y: modelData[1] ? 14 : 0 }
            Rectangle { width: 1; height: 14; color: Theme.cyan; x: modelData[0] ? 14 : 0 }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        RowLayout {
            visible: panel.showHeader
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            Layout.leftMargin: 16
            Layout.rightMargin: 14
            spacing: 10
            Rectangle {
                width: 3; height: 14; radius: 2; color: Theme.cyan
                layer.enabled: true
            }
            Text {
                text: panel.title
                color: Theme.text
                font.family: Theme.display
                font.pixelSize: 13
                font.weight: Font.DemiBold
                font.letterSpacing: 2.6
                font.capitalization: Font.AllUppercase
            }
            Rectangle {
                visible: panel.tag !== ""
                radius: 6
                color: Qt.rgba(130 / 255, 170 / 255, 1, 0.06)
                border.color: Theme.line
                implicitWidth: tagText.implicitWidth + 16
                implicitHeight: 20
                Text {
                    id: tagText
                    anchors.centerIn: parent
                    text: panel.tag
                    color: Theme.muted
                    font.family: Theme.mono
                    font.pixelSize: 11
                }
            }
            Item { Layout.fillWidth: true }
            RowLayout { id: headerExtra; spacing: 8 }
        }
        Rectangle {
            visible: panel.showHeader
            Layout.fillWidth: true
            height: 1
            color: Theme.line
        }
        Item {
            id: body
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
