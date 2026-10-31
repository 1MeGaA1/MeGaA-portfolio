import QtQuick
import QtQuick.Effects
import "."

// A small look-alike of one hook style.
Rectangle {
    id: tile
    property var hs: ({})
    property bool on: false
    signal clicked()

    implicitHeight: 58
    radius: 10
    color: on ? Qt.rgba(0, 229 / 255, 1, 0.07) : Theme.field
    border.width: on ? 1.5 : 1
    border.color: on ? Theme.cyan : area.containsMouse ? Qt.rgba(0, 229 / 255, 1, 0.4) : Theme.line2
    clip: true

    Rectangle {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -7
        width: sample.implicitWidth + (tile.hs.mode === "box" ? 10 : 0)
        height: sample.implicitHeight + (tile.hs.mode === "box" ? 2 : 0)
        color: tile.hs.mode === "box" ? tile.hs.box : "transparent"
        layer.enabled: !!tile.hs.glow
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: tile.hs.outline_color || "black"
            shadowBlur: 0.5
            shadowOpacity: 1
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 0
        }
        Text {
            id: sample
            anchors.centerIn: parent
            text: tile.hs.uppercase ? "HOOK" : "Hook"
            font.family: tile.hs.font || "Arial Black"
            font.pixelSize: Math.max(9, Math.min(13, 10.5 * (tile.hs.size || 60) / 60))
            color: tile.hs.text || "black"
            style: tile.hs.mode === "outline" ? Text.Outline : Text.Normal
            styleColor: tile.hs.outline_color || "black"
        }
    }
    Text {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 6
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width - 6
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        text: tile.hs.label || ""
        color: tile.on ? Theme.cyan : Theme.muted
        font.family: Theme.display
        font.pixelSize: 9
        font.weight: Font.DemiBold
        font.letterSpacing: 0.8
        font.capitalization: Font.AllUppercase
    }
    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: tile.clicked() }
}
