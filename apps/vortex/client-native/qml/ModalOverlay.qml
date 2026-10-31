import QtQuick
import QtQuick.Layouts

// Reusable centered dialog over a dim background.
Item {
    id: root
    property string label: ""
    property string title: ""
    property color accent: Theme.cyan
    property real cardWidth: 380
    default property alias body: bodyCol.data
    signal openned()
    signal closed()
    function open() { visible = true; openned() }
    function close() { visible = false; closed() }

    anchors.fill: parent
    visible: false
    z: 150

    Rectangle { anchors.fill: parent; color: Qt.rgba(0.02, 0.02, 0.05, 0.9) }
    MouseArea { anchors.fill: parent; onClicked: root.close() }

    VxCard {
        anchors.centerIn: parent
        width: root.cardWidth
        implicitHeight: wrap.implicitHeight + 44
        height: implicitHeight
        accent: root.accent
        MouseArea { anchors.fill: parent }   // block click-through
        ColumnLayout {
            id: wrap
            anchors.fill: parent
            spacing: 12
            RowLayout {
                Layout.fillWidth: true
                SectionLabel { label: root.label; accent: root.accent }
                Item { Layout.fillWidth: true }
                Text {
                    text: "✕"; color: Theme.textMuted; font.pixelSize: 16
                    MouseArea { anchors.fill: parent; anchors.margins: -8; cursorShape: Qt.PointingHandCursor; onClicked: root.close() }
                }
            }
            Text { text: root.title; color: Theme.textPrimary; visible: root.title.length > 0
                   font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 20 }
            ColumnLayout { id: bodyCol; Layout.fillWidth: true; spacing: 12 }
        }
    }
}
