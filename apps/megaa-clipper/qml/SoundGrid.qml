import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import "."

// The sound on muted words (web .sound-grid): the engine's sounds as 3 x 3 tiles – click one to choose it and
// hear it. The speaker of a tile being previewed pulses for 600 ms (web .sound-tile.playing).
GridLayout {
    id: grid
    columns: 3
    columnSpacing: 5
    rowSpacing: 5

    property string pulseKey: ""
    Connections {
        target: Store
        function onPreviewSound(toneSeconds, key) {
            if (!key) return
            grid.pulseKey = key
            pulseTimer.restart()
        }
    }
    Timer { id: pulseTimer; interval: 600; onTriggered: grid.pulseKey = "" }

    Repeater {
        model: Store.muteSoundOrder
        Rectangle {
            id: tile
            required property string modelData
            readonly property var info: Store.muteSounds[modelData] || ({ label: modelData, kind: "none" })
            readonly property bool on: Store.edit.muteSound === modelData
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            implicitHeight: 32
            radius: 8
            color: on ? Qt.rgba(139 / 255, 92 / 255, 1, 0.2) : Theme.field
            border.color: on ? Theme.violet : tileArea.containsMouse ? Qt.rgba(139 / 255, 92 / 255, 1, 0.5) : Theme.line2
            layer.enabled: on
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: Theme.violet
                shadowBlur: 0.8
                shadowOpacity: 0.3
                shadowHorizontalOffset: 0
                shadowVerticalOffset: 0
            }

            Row {
                anchors.centerIn: parent
                spacing: 6
                Text {
                    id: speaker
                    visible: tile.modelData !== "silence"
                    anchors.verticalCenter: parent.verticalCenter
                    text: Theme.icVolume
                    font.family: Theme.icons
                    font.pixelSize: 13
                    color: label.color
                }
                Text {
                    id: label
                    anchors.verticalCenter: parent.verticalCenter
                    text: tile.info.label
                    color: tile.on ? "#ffffff" : tileArea.containsMouse ? Theme.text : Theme.muted
                    font.family: Theme.display
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.1
                    font.capitalization: Font.AllUppercase
                }
            }

            // web: @keyframes pulse { 50% { opacity: .25; transform: scale(.7) } }, .5 s
            SequentialAnimation {
                running: grid.pulseKey === tile.modelData
                loops: Animation.Infinite
                onStopped: { speaker.opacity = 1; speaker.scale = 1 }
                ParallelAnimation {
                    NumberAnimation { target: speaker; property: "opacity"; to: 0.25; duration: 250; easing.type: Easing.InOutSine }
                    NumberAnimation { target: speaker; property: "scale"; to: 0.7; duration: 250; easing.type: Easing.InOutSine }
                }
                ParallelAnimation {
                    NumberAnimation { target: speaker; property: "opacity"; to: 1; duration: 250; easing.type: Easing.InOutSine }
                    NumberAnimation { target: speaker; property: "scale"; to: 1; duration: 250; easing.type: Easing.InOutSine }
                }
            }

            MouseArea {
                id: tileArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: { Store.releaseFocus(); Store.chooseMuteSound(tile.modelData) }
            }
        }
    }
}
