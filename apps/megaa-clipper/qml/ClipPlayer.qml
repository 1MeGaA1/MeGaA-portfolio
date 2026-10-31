import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtMultimedia
import "."

// Watch a rendered clip over the editor. Click outside or press Esc to close.
Rectangle {
    id: dlg
    visible: false
    color: Qt.rgba(2 / 255, 4 / 255, 8 / 255, 0.82)
    signal opened()
    property var shownClip: null

    function show(c) {
        shownClip = c
        const url = backend.clipUrl(c.name)
        if (!url) { Store.toast("Render the clip first", "info"); return }
        player.source = ""
        player.source = url
        visible = true
        opened()
        player.play()
    }

    function close() {
        player.stop()
        player.source = ""
        visible = false
    }

    MouseArea { anchors.fill: parent; onClicked: dlg.close(); onWheel: (wheel) => wheel.accepted = true }

    MediaPlayer {
        id: player
        videoOutput: out
        audioOutput: AudioOutput {}
        loops: MediaPlayer.Infinite
    }

    Rectangle {
        id: box
        anchors.centerIn: parent
        height: Math.min(parent.height - 80, 900)
        width: (height - 120) * 9 / 16 + 32
        radius: 18
        color: Theme.panelSolid
        border.color: Theme.line2
        MouseArea { anchors.fill: parent }   // clicks inside don't close

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 10
            RowLayout {
                Layout.fillWidth: true
                Text {
                    Layout.fillWidth: true
                    text: dlg.shownClip ? dlg.shownClip.name : ""
                    color: Theme.text
                    elide: Text.ElideRight
                    font.family: Theme.display
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.5
                }
                IconButton {
                    glyph: Theme.icFolder
                    ToolTip.text: "Show in folder"
                    onClicked: if (dlg.shownClip) backend.reveal(dlg.shownClip.name)
                }
                IconButton { glyph: Theme.icClose; ToolTip.text: "Close (Esc)"; onClicked: dlg.close() }
            }
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "black"
                radius: 6
                VideoOutput {
                    id: out
                    anchors.fill: parent
                    fillMode: VideoOutput.PreserveAspectFit
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: player.playbackState === MediaPlayer.PlayingState ? player.pause() : player.play()
                }
                // progress
                Rectangle {
                    anchors.bottom: parent.bottom
                    height: 3
                    width: player.duration ? parent.width * player.position / player.duration : 0
                    color: Theme.cyan
                }
            }
            Text {
                Layout.fillWidth: true
                visible: text !== ""
                text: dlg.shownClip && dlg.shownClip.post_caption ? dlg.shownClip.post_caption : ""
                color: Theme.muted
                wrapMode: Text.WordWrap
                maximumLineCount: 3
                elide: Text.ElideRight
                font.pixelSize: 13
            }
        }
    }
}
