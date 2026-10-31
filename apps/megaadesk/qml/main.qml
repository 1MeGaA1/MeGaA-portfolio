import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import MeGaADesk 1.0

ApplicationWindow {
    id: win
    visible: true
    width: 1040
    height: 660
    title: "MeGaADesk"
    color: "#0b0d10"

    property bool connected: false
    property string status: ""

    Connections {
        target: backend
        function onConnected(w, h) {
            win.connected = true
            win.status = ""
            win.title = "MeGaADesk — " + w + "×" + h
            remoteScreen.forceActiveFocus()
        }
        function onFailed(msg) { win.connected = false; win.status = msg }
        function onDisconnected() {
            win.connected = false
            win.status = "Disconnected."
            win.title = "MeGaADesk"
        }
    }

    // --- Remote screen (fills the window when connected) ------------------
    RemoteScreen {
        id: remoteScreen
        objectName: "remoteScreen"
        anchors.fill: parent
        visible: win.connected
        focus: win.connected
    }

    // Floating disconnect button
    Rectangle {
        visible: win.connected
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 8
        width: discBtn.implicitWidth + 20
        height: discBtn.implicitHeight + 12
        color: "#161a20"
        opacity: 0.85
        radius: 6
        Button {
            id: discBtn
            text: "Disconnect"
            anchors.centerIn: parent
            flat: true
            onClicked: backend.disconnect()
        }
    }

    // --- Connect panel ----------------------------------------------------
    Rectangle {
        visible: !win.connected
        anchors.fill: parent
        color: "#0b0d10"

        ColumnLayout {
            anchors.centerIn: parent
            width: 380
            spacing: 14

            Label {
                text: "MeGaADesk"
                color: "#e8eaed"
                font.pixelSize: 30
                font.bold: true
                Layout.alignment: Qt.AlignHCenter
            }
            Label {
                text: "Remote Desktop — no ads, your server"
                color: "#8a8f98"
                Layout.alignment: Qt.AlignHCenter
            }

            TabBar {
                id: modeTab
                Layout.fillWidth: true
                TabButton { text: "Relay (Internet)" }
                TabButton { text: "Direct (LAN)" }
            }

            ColumnLayout {
                visible: modeTab.currentIndex === 0
                Layout.fillWidth: true
                spacing: 8
                TextField {
                    id: relayAddr
                    placeholderText: "Relay host:port  (e.g. 203.0.113.9:7000)"
                    Layout.fillWidth: true
                }
                TextField {
                    id: relayId
                    placeholderText: "Host ID  (what the host registered as)"
                    Layout.fillWidth: true
                }
            }

            ColumnLayout {
                visible: modeTab.currentIndex === 1
                Layout.fillWidth: true
                spacing: 8
                TextField {
                    id: directHost
                    placeholderText: "Host IP  (e.g. 192.168.1.50)"
                    Layout.fillWidth: true
                }
                TextField {
                    id: directPort
                    placeholderText: "Port"
                    text: "7777"
                    Layout.fillWidth: true
                }
            }

            TextField {
                id: pw
                placeholderText: "Password"
                echoMode: TextInput.Password
                Layout.fillWidth: true
                onAccepted: connectBtn.clicked()
            }

            Button {
                id: connectBtn
                text: "Connect"
                Layout.fillWidth: true
                onClicked: {
                    if (modeTab.currentIndex === 0)
                        backend.connectRelay(relayAddr.text.trim(), relayId.text.trim(), pw.text)
                    else
                        backend.connectDirect(directHost.text.trim(), parseInt(directPort.text || "7777"), pw.text)
                }
            }

            Label {
                text: win.status
                visible: win.status.length > 0
                color: "#e06c75"
                wrapMode: Text.Wrap
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }
}
