import QtQuick
import QtQuick.Effects
import "."

// A small look-alike of one caption style (web edition: tileSample).
Rectangle {
    id: tile
    property var st: ({})
    property bool on: false
    signal clicked()

    readonly property var sample: st.max_words === 1 ? ["money"] : ["your", "money", "rule"]
    readonly property int active: st.max_words === 1 ? 0 : 1

    implicitHeight: 70
    radius: 10
    color: on ? Qt.rgba(0, 229 / 255, 1, 0.07) : Theme.field
    border.width: on ? 1.5 : 1
    border.color: on ? Theme.cyan : area.containsMouse ? Qt.rgba(0, 229 / 255, 1, 0.4) : Theme.line2
    clip: true

    Row {
        id: words
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -8
        spacing: 5
        layer.enabled: !!tile.st.glow
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: tile.st.outline_color || "black"
            shadowBlur: 0.5
            shadowOpacity: 1
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 0
        }
        Repeater {
            model: tile.sample
            Rectangle {
                required property string modelData
                required property int index
                readonly property bool lit: (tile.st.mode === "word" && index === tile.active) || (tile.st.mode === "fill" && index <= tile.active)
                readonly property bool boxed: tile.st.mode === "box" && index === tile.active
                width: label.implicitWidth + (boxed ? 8 : 0)
                height: label.implicitHeight + (boxed ? 2 : 0)
                radius: 3
                color: boxed ? tile.st.accent : "transparent"
                anchors.verticalCenter: parent.verticalCenter
                Text {
                    id: label
                    anchors.centerIn: parent
                    text: tile.st.uppercase ? modelData.toUpperCase() : modelData[0].toUpperCase() + modelData.slice(1)
                    font.family: tile.st.font || "Arial Black"
                    font.bold: !!tile.st.bold
                    font.pixelSize: Math.max(10, Math.min(19, 14 * (tile.st.size || 84) / 84))
                                    * (tile.st.mode === "word" && parent.index === tile.active ? tile.st.active_scale || 1 : 1)
                    color: parent.lit ? tile.st.accent : tile.st.text || "white"
                    style: tile.st.outline && !parent.boxed ? Text.Outline : Text.Normal
                    styleColor: tile.st.outline_color || "black"
                }
            }
        }
    }
    Text {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 7
        anchors.horizontalCenter: parent.horizontalCenter
        text: tile.st.label || ""
        color: tile.on ? Theme.cyan : Theme.muted
        font.family: Theme.display
        font.pixelSize: 10
        font.weight: Font.DemiBold
        font.letterSpacing: 1.2
        font.capitalization: Font.AllUppercase
    }
    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: tile.clicked() }
}
