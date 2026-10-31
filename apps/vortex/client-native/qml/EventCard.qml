import QtQuick
import QtQuick.Layouts

// One event / tournament / offer from the server (fields: title, kind, game, tag, when, prize, status).
// Live events glow magenta, upcoming ones cyan, offers amber with an OFFER tag.
Rectangle {
    id: root
    property var ev: null
    signal join()

    readonly property bool live: ev ? ev.status === "live" : false
    readonly property bool offer: ev ? ev.kind === "offer" : false
    readonly property color accent: offer ? Theme.amber : (live ? Theme.magenta : Theme.cyan)
    implicitHeight: 150
    color: Theme.bgPanel
    border.color: ma.containsMouse ? accent : Theme.border
    border.width: 1
    Rectangle { anchors { top: parent.top; left: parent.left; right: parent.right }
                height: 2; color: root.accent }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 6
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            // OFFER tag
            Rectangle {
                visible: root.offer
                implicitWidth: offerTag.implicitWidth + 14; implicitHeight: 18
                color: Qt.rgba(1, 0.72, 0, 0.12); border.color: Theme.amber; border.width: 1
                Text { id: offerTag; anchors.centerIn: parent; text: "OFFER"; color: Theme.amber
                       font.family: Theme.fontMono; font.weight: Font.Bold; font.pixelSize: 9; font.letterSpacing: 2 }
            }
            Text { text: root.ev ? ((root.offer ? (root.ev.tag || "") : (root.ev.game || "")).toUpperCase()) : ""
                   color: Theme.textDim; font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 2
                   Layout.fillWidth: true; elide: Text.ElideRight }
            Text {
                text: root.live ? "● LIVE" : ("● " + (root.ev ? (root.ev.when || "") : ""))
                color: root.live ? Theme.magenta : Theme.amber
                font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 1
            }
        }
        Text { text: root.ev ? (root.ev.title || "") : ""; color: Theme.textPrimary
               font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 20; Layout.fillWidth: true; elide: Text.ElideRight }
        Text { text: root.offer ? "PRICE" : "PRIZE POOL"; color: Theme.textDim; font.family: Theme.fontMono; font.pixelSize: 9; font.letterSpacing: 2 }
        Text { text: root.ev ? (root.ev.prize || "") : ""; color: Theme.amber
               font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 22 }
        Item { Layout.fillHeight: true }
        VxButton {
            text: root.offer ? "CLAIM AT THE COUNTER →" : (root.live ? "JOIN NOW →" : "REGISTER →")
            accent: root.accent
            onClicked: root.join()
        }
    }
    MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton }
}
