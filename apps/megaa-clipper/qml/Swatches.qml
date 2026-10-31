import QtQuick
import QtQuick.Dialogs
import "."

// Row of colour dots. `auto` adds a "style default" dot (value null), `custom` a colour picker.
Flow {
    id: sw
    property var colors: []
    property var current: null
    property bool auto: false
    property bool custom: false
    property color customStart: "#ffffff"
    signal picked(var color)
    spacing: 6

    component Dot: Rectangle {
        id: dot
        property bool on: false
        property string tip: ""
        signal clicked()
        width: 24; height: 24; radius: 12
        border.width: on ? 2 : 1
        border.color: on ? "white" : Qt.rgba(1, 1, 1, 0.18)
        Rectangle {
            anchors.fill: parent
            anchors.margins: -4
            radius: width / 2
            color: "transparent"
            border.color: Theme.cyan
            border.width: 1.5
            visible: dot.on
        }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: dot.clicked() }
    }

    Dot {
        visible: sw.auto
        on: !sw.current
        color: Theme.field
        Text { anchors.centerIn: parent; text: "A"; color: Theme.muted; font.family: Theme.display; font.pixelSize: 11; font.weight: Font.Bold }
        onClicked: sw.picked(null)
    }
    Repeater {
        model: sw.colors
        Dot {
            required property string modelData
            color: modelData
            on: sw.current === modelData
            onClicked: sw.picked(modelData)
        }
    }
    Dot {
        id: customDot
        visible: sw.custom
        readonly property bool isCustom: !!sw.current && sw.colors.indexOf(sw.current) < 0
        on: isCustom
        color: isCustom ? sw.current : Theme.field
        Text {
            anchors.centerIn: parent
            visible: !customDot.isCustom
            text: Theme.icAdd
            font.family: Theme.icons
            font.pixelSize: 11
            color: Theme.muted
        }
        onClicked: picker.open()
    }
    ColorDialog {
        id: picker
        title: "Pick a colour"
        selectedColor: sw.current || sw.customStart
        onAccepted: sw.picked(selectedColor.toString().toUpperCase())
    }
}
