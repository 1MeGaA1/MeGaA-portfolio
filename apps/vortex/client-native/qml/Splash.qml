import QtQuick

// Bolder animated "initializing" screen: glowing counter-rotating vortex mark,
// live connection status, animated progress. Status reflects the real server link.
Item {
    id: root
    signal done()

    property int stage: 0
    property bool online: false
    property bool linkFailed: false
    readonly property var stages: [
        { t: "CONNECTING TO SERVER",   c: Theme.cyan },
        { t: "AUTHENTICATING STATION", c: Theme.cyan },
        { t: "LOADING GAME LIBRARY",   c: Theme.magenta },
        { t: "READY",                  c: Theme.green }
    ]

    Rectangle { anchors.fill: parent; color: Theme.bg }
    RingsBackground {}

    Column {
        anchors.centerIn: parent
        spacing: 30

        // ---------------- glowing vortex mark ----------------
        Item {
            id: mark
            width: 170; height: 170
            anchors.horizontalCenter: parent.horizontalCenter

            // expanding halo pulses (the "glow")
            Repeater {
                model: 2
                delegate: Rectangle {
                    required property int index
                    anchors.centerIn: parent
                    width: 120; height: 120; radius: 60
                    color: "transparent"
                    border.color: Theme.cyan
                    border.width: 2
                    SequentialAnimation on scale {
                        loops: Animation.Infinite
                        PauseAnimation { duration: index * 700 }
                        NumberAnimation { from: 0.8; to: 1.5; duration: 1400; easing.type: Easing.OutCubic }
                        PauseAnimation { duration: 0 }
                    }
                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        PauseAnimation { duration: index * 700 }
                        NumberAnimation { from: 0.4; to: 0.0; duration: 1400 }
                        PauseAnimation { duration: 0 }
                    }
                }
            }
            // outer ring (cyan), clockwise
            Rectangle {
                anchors.centerIn: parent; width: 128; height: 128; radius: 64
                color: "transparent"; border.color: Theme.cyan; border.width: 3
                RotationAnimation on rotation { from: 0; to: 360; duration: 4200; loops: Animation.Infinite; running: true }
                // a bright arc segment via a small dot riding the ring
                Rectangle { width: 10; height: 10; radius: 5; color: Theme.cyan
                            x: parent.width / 2 - 5; y: -5 }
            }
            // inner ring (magenta), counter-clockwise
            Rectangle {
                anchors.centerIn: parent; width: 84; height: 84; radius: 42
                color: "transparent"; border.color: Theme.magenta; border.width: 3
                RotationAnimation on rotation { from: 360; to: 0; duration: 3200; loops: Animation.Infinite; running: true }
                Rectangle { width: 8; height: 8; radius: 4; color: Theme.magenta
                            x: parent.width / 2 - 4; y: -4 }
            }
            // pulsing core
            Rectangle {
                anchors.centerIn: parent; width: 28; height: 28; radius: 14; color: Theme.cyan
                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    NumberAnimation { from: 1.0; to: 0.35; duration: 700; easing.type: Easing.InOutSine }
                    NumberAnimation { from: 0.35; to: 1.0; duration: 700; easing.type: Easing.InOutSine }
                }
                SequentialAnimation on scale {
                    loops: Animation.Infinite
                    NumberAnimation { from: 1.0; to: 1.18; duration: 700; easing.type: Easing.InOutSine }
                    NumberAnimation { from: 1.18; to: 1.0; duration: 700; easing.type: Easing.InOutSine }
                }
            }
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "VORTEX"; color: Theme.textPrimary
            font.family: Theme.fontDisplay; font.weight: Font.Bold
            font.pixelSize: 46; font.letterSpacing: 12
        }

        // ---------------- live status ----------------
        Text {
            id: statusText
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.linkFailed ? "// SERVER OFFLINE · RETRYING"
                                  : "// " + root.stages[root.stage].t
            color: root.linkFailed ? Theme.amber : root.stages[root.stage].c
            font.family: Theme.fontMono; font.pixelSize: 13; font.letterSpacing: 3
            font.capitalization: Font.AllUppercase
            Behavior on color { ColorAnimation { duration: 200 } }
        }

        // ---------------- progress ----------------
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 320; height: 4; color: Theme.surface
            Rectangle {
                id: bar; height: parent.height; width: 0
                color: root.linkFailed ? Theme.amber : (root.stage >= 3 ? Theme.green : Theme.cyan)
                Behavior on width { NumberAnimation { duration: 450; easing.type: Easing.OutCubic } }
                Behavior on color { ColorAnimation { duration: 200 } }
            }
        }
    }

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom; anchors.bottomMargin: 22
        text: (vortex.stationName || "STATION") + " · VORTEX v" + vortex.version
        color: Theme.textDim; font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 2
    }

    function setBar() { bar.width = 320 * ((root.stage + 1) / root.stages.length) }

    // step through the first three stages for effect; the last (READY) waits for the real link
    Timer {
        id: stepper
        interval: 600; running: true; repeat: true
        onTriggered: {
            if (root.stage < 2) { root.stage++; root.setBar() }
            else if (root.stage === 2 && root.online) { root.stage = 3; root.setBar() }
        }
    }
    Component.onCompleted: setBar()

    Connections {
        target: vortex
        function onLinkChanged(on, err) { root.online = on; root.linkFailed = !on }
        function onWelcomeReceived(s) { root.online = true; root.linkFailed = false }
    }

    // leave the splash once we've shown the brand for a moment AND either reached READY
    // or hit the safety cap (so a slow/offline server never traps the screen).
    Timer { id: minTime; interval: 2200; running: true }
    Timer {
        interval: 150; running: true; repeat: true
        onTriggered: {
            if (!minTime.running && (root.stage >= 3 || capped)) { running = false; root.done() }
        }
    }
    property bool capped: false
    Timer { interval: 5000; running: true; onTriggered: root.capped = true }
}
