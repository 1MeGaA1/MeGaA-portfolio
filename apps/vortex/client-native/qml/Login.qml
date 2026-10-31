import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    id: root
    property bool busy: false
    property bool registerMode: false

    function setNotice(text, kind) {
        notice.text = text || ""
        notice.color = kind === "bad" ? Theme.magenta : (kind === "good" ? Theme.green : Theme.amber)
        notice.visible = !!text
    }
    function focusFirst() { emailField.forceActiveFocus() }

    Rectangle { anchors.fill: parent; color: Theme.bg }
    RingsBackground {}

    // logo wordmark
    Row {
        id: brand
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: Math.max(24, (card.y - height) / 2)
        spacing: 12
        Rectangle {
            width: 40; height: 40; radius: 20; anchors.verticalCenter: parent.verticalCenter
            color: "transparent"; border.color: Theme.cyan; border.width: 2
            Rectangle { anchors.centerIn: parent; width: 20; height: 20; radius: 10
                        color: "transparent"; border.color: Theme.magenta; border.width: 2 }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "VORTEX"; color: Theme.textPrimary
            font.family: Theme.fontDisplay; font.weight: Font.Bold
            font.pixelSize: 26; font.letterSpacing: 6
        }
    }

    VxCard {
        id: card
        anchors.centerIn: parent
        width: 380
        implicitHeight: col.implicitHeight + 44
        height: implicitHeight
        accent: Theme.cyan

        ColumnLayout {
            id: col
            anchors.fill: parent
            anchors.margins: 0
            spacing: 12

            SectionLabel { label: "ACCESS TERMINAL" }
            Text {
                text: root.registerMode ? "Create account" : "Login"
                color: Theme.textPrimary; font.family: Theme.fontDisplay
                font.weight: Font.Bold; font.pixelSize: 22; font.letterSpacing: 1
            }

            Text {
                id: notice
                Layout.fillWidth: true
                visible: false
                wrapMode: Text.WordWrap
                font.family: Theme.fontMono; font.pixelSize: 11; font.letterSpacing: 1
                font.capitalization: Font.AllUppercase
            }

            VxField { id: emailField; Layout.fillWidth: true; label: "EMAIL / USERNAME" }
            VxField { id: pwField;    Layout.fillWidth: true; label: "PASSWORD"; echo: true
                      onAccepted: root.submit() }
            VxField { id: pw2Field;   Layout.fillWidth: true; label: "CONFIRM PASSWORD"; echo: true
                      visible: root.registerMode; onAccepted: root.submit() }

            VxButton {
                Layout.fillWidth: true
                text: root.busy ? "PLEASE WAIT…" : (root.registerMode ? "CREATE ACCOUNT →" : "LOGIN →")
                accent: Theme.cyan
                enabled: !root.busy
                onClicked: root.submit()
            }

            Item { Layout.fillWidth: true; implicitHeight: 1
                Rectangle { anchors.centerIn: parent; width: parent.width; height: 1; color: Theme.border } }

            VxButton {
                Layout.fillWidth: true
                text: root.registerMode ? "← BACK TO LOGIN" : "CREATE ACCOUNT →"
                accent: Theme.magenta
                filled: false
                enabled: !root.busy
                onClicked: { root.registerMode = !root.registerMode; root.setNotice("") }
            }
        }
    }

    // connection status — makes it obvious when the server can't be reached
    property bool online: false
    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom; anchors.bottomMargin: 40
        spacing: 8
        Text {
            text: "●"
            color: root.online ? Theme.green : Theme.amber
            font.pixelSize: 12
            SequentialAnimation on opacity {
                running: !root.online; loops: Animation.Infinite
                NumberAnimation { from: 1; to: 0.3; duration: 600 }
                NumberAnimation { from: 0.3; to: 1; duration: 600 }
            }
        }
        Text {
            text: root.online ? "CONNECTED TO SERVER" : "SERVER OFFLINE · CHECK client.json"
            color: root.online ? Theme.green : Theme.amber
            font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 2
        }
    }
    Connections {
        target: vortex
        function onLinkChanged(on, err) { root.online = on }
        function onWelcomeReceived(s) { root.online = true }
    }

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom; anchors.bottomMargin: 20
        text: (vortex.stationName || "STATION") + " · VORTEX v" + vortex.version
        color: Theme.textDim; font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 2
    }

    function submit() {
        if (busy) return
        if (registerMode) {
            if (!emailField.text || !pwField.text) { setNotice("ENTER EMAIL AND PASSWORD", "bad"); return }
            if (pwField.text !== pw2Field.text) { setNotice("PASSWORDS DO NOT MATCH", "bad"); return }
            busy = true; vortex.register(emailField.text.trim(), pwField.text, "")
        } else {
            if (!emailField.text || !pwField.text) { setNotice("ENTER EMAIL AND PASSWORD", "bad"); return }
            busy = true; vortex.login(emailField.text.trim(), pwField.text)
        }
    }

    Connections {
        target: vortex
        function onLoginResult(ok, error, message) {
            root.busy = false
            if (!ok) { root.setNotice(message || "LOGIN FAILED", "bad"); pwField.clear() }
        }
        function onRegisterResult(ok, error, message) {
            root.busy = false
            if (ok) {
                root.registerMode = false
                pwField.clear(); pw2Field.clear()
                root.setNotice(message || "ACCOUNT CREATED · ASK THE COUNTER TO ADD TIME", "good")
            } else {
                root.setNotice(message || "COULD NOT CREATE ACCOUNT", "bad")
            }
        }
    }
}
