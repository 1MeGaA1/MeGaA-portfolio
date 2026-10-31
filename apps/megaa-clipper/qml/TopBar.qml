import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Shapes
import "."

// Brand, the open video, engine status and a thin progress line along the bottom.
Rectangle {
    id: bar
    signal openRequested()

    readonly property var job: Store.job
    readonly property string statusKind: job.running ? "busy" : job.error ? "error" : job.seq > 0 ? "done" : ""
    readonly property string statusText: job.running ? `${job.message} · ${job.progress}%`
                                                     : job.error ? "Task failed" : job.seq > 0 ? job.message : "Ready"
    readonly property color statusColor: statusKind === "busy" ? Theme.cyan : statusKind === "error" ? Theme.bad
                                                                : statusKind === "done" ? Theme.ok : Theme.muted

    color: Theme.panel
    radius: Theme.radius
    border.color: Theme.line

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        spacing: 14

        Logo { Layout.preferredWidth: 34; Layout.preferredHeight: 34 }
        Column {
            spacing: 1
            Text {
                textFormat: Text.StyledText
                text: `<font color="${Theme.magenta}">MeGaA</font> CLIPPER`
                color: Theme.text
                font.family: Theme.display
                font.pixelSize: 17
                font.weight: Font.Bold
                font.letterSpacing: 2.2
            }
            Text {
                text: "SHORT-FORM ENGINE · QML"
                color: Theme.dim
                font.family: Theme.mono
                font.pixelSize: 10
                font.letterSpacing: 2.4
            }
        }

        Rectangle { Layout.preferredWidth: 1; Layout.preferredHeight: 30; color: Theme.line2; Layout.leftMargin: 6 }

        NeonButton {
            text: "Open"
            iconText: Theme.icOpen
            small: true
            enabled: !Store.busy
            onClicked: bar.openRequested()
        }
        Column {
            Layout.fillWidth: true
            spacing: 2
            Text {
                width: parent.width
                text: Store.video ? Store.video.name : "No video"
                color: Store.video ? Theme.text : Theme.dim
                elide: Text.ElideMiddle
                font.pixelSize: 14
                font.weight: Font.DemiBold
            }
            Text {
                visible: !!Store.info
                text: Store.info ? `${Store.info.width}×${Store.info.height} · ${Store.fmt(Store.info.duration)} · ${Math.round(Store.info.fps)} fps` : ""
                color: Theme.muted
                font.family: Theme.mono
                font.pixelSize: 11
            }
        }

        // undo / redo of the clip being edited (Ctrl+Z / Ctrl+Y)
        Row {
            visible: !!Store.video
            spacing: 4
            IconButton { glyph: Theme.icUndo; enabled: Store.undoCount > 0; ToolTip.text: "Undo (Ctrl+Z)"; onClicked: Store.undo() }
            IconButton { glyph: Theme.icRedo; enabled: Store.redoCount > 0; ToolTip.text: "Redo (Ctrl+Y)"; onClicked: Store.redo() }
        }
        // the Whop campaign whose rules this video's clips are checked against
        Rectangle {
            id: campChip
            visible: !!Store.video
            readonly property var camp: Store.currentCampaign
            radius: 10
            implicitHeight: 30
            implicitWidth: campRow.implicitWidth + 24
            color: camp ? Qt.rgba(43 / 255, 1, 160 / 255, 0.07) : campArea.containsMouse ? Qt.rgba(0, 229 / 255, 1, 0.05) : "transparent"
            border.color: camp ? Qt.rgba(43 / 255, 1, 160 / 255, 0.45) : Theme.line2
            Row {
                id: campRow
                anchors.verticalCenter: parent.verticalCenter
                x: 12
                spacing: 8
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 7; height: 7; radius: 4
                    color: campChip.camp ? Theme.ok : Theme.dim
                }
                Text {
                    width: Math.min(implicitWidth, 180)
                    text: campChip.camp ? campChip.camp.name : "No campaign"
                    color: campChip.camp ? Theme.text : Theme.muted
                    elide: Text.ElideRight
                    font.pixelSize: 12
                }
            }
            MouseArea {
                id: campArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: Store.dialogRequested("campaigns")
            }
            ToolTip.visible: campArea.containsMouse
            ToolTip.delay: 500
            ToolTip.text: "Whop campaign for this video – its rules are checked for every clip"
        }
        IconButton { glyph: "$"; ToolTip.text: "Earnings tracker"; onClicked: Store.dialogRequested("tracker") }
        IconButton { glyph: Theme.icSettings; ToolTip.text: "Settings (API key)"; onClicked: Store.dialogRequested("settings") }

        // preview proxy / waveform being prepared in the background
        Rectangle {
            visible: Store.prep.state === "working" || Store.prep.state === "error"
            radius: 8
            implicitHeight: 24
            implicitWidth: prepText.implicitWidth + 18
            color: Qt.rgba(0, 229 / 255, 1, 0.06)
            border.color: Theme.line2
            Text {
                id: prepText
                anchors.centerIn: parent
                text: Store.prep.state === "error" ? "Preview unavailable"
                                                   : `${Store.prep.message}${Store.prep.progress ? ` · ${Store.prep.progress}%` : ""}`
                color: Store.prep.state === "error" ? Theme.warn : Theme.muted
                font.family: Theme.mono
                font.pixelSize: 11
            }
        }

        Rectangle {
            radius: 10
            implicitHeight: 30
            implicitWidth: Math.min(380, statusRow.implicitWidth + 24)
            color: Theme.field
            border.color: Qt.rgba(bar.statusColor.r, bar.statusColor.g, bar.statusColor.b, 0.35)
            Row {
                id: statusRow
                anchors.verticalCenter: parent.verticalCenter
                x: 12
                spacing: 9
                Rectangle {
                    id: dot
                    width: 8; height: 8; radius: 4
                    anchors.verticalCenter: parent.verticalCenter
                    color: bar.statusColor
                    SequentialAnimation on opacity {
                        running: bar.statusKind === "busy"
                        loops: Animation.Infinite
                        onRunningChanged: if (!running) dot.opacity = 1
                        NumberAnimation { to: 0.25; duration: 550 }
                        NumberAnimation { to: 1; duration: 550 }
                    }
                }
                Text {
                    width: Math.min(implicitWidth, 330)
                    text: bar.statusText
                    color: bar.statusKind ? bar.statusColor : Theme.muted
                    elide: Text.ElideRight
                    font.family: Theme.mono
                    font.pixelSize: 11
                }
            }
        }
    }

    // job progress along the bottom edge
    Rectangle {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.leftMargin: Theme.radius
        height: 2
        radius: 1
        width: (parent.width - Theme.radius * 2) * (bar.job.running ? Math.max(3, bar.job.progress) / 100 : 1)
        opacity: bar.job.running ? 1 : 0
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Theme.cyan }
            GradientStop { position: 1; color: Theme.magenta }
        }
        Behavior on width { NumberAnimation { duration: 300 } }
        Behavior on opacity { NumberAnimation { duration: 400 } }
    }
}
