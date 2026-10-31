import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ApplicationWindow {
    id: win
    visible: true
    width: 1280
    height: 800
    color: Theme.bg
    title: "Vortex"
    visibility: vortex.kiosk ? Window.FullScreen : Window.Windowed
    flags: vortex.kiosk ? (Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint) : Qt.Window

    property string screen: "splash"

    onClosing: function (close) { close.accepted = vortex.requestClose() }

    Splash {
        anchors.fill: parent
        visible: win.screen === "splash"
        onDone: if (win.screen === "splash") win.screen = "login"
    }
    Login {
        id: loginScreen
        anchors.fill: parent
        visible: win.screen === "login"
        onVisibleChanged: if (visible) focusFirst()
    }
    Hub {
        id: hubScreen
        anchors.fill: parent
        visible: win.screen === "hub"
        onLogoutRequested: vortex.logout()
    }

    Toast { id: toast }

    // ---------------- admin escape (staff PIN) ----------------
    Shortcut { sequence: "Ctrl+Shift+Q"; onActivated: pinOverlay.open() }

    Item {
        id: pinOverlay
        anchors.fill: parent
        visible: false
        z: 200
        function open() { pinField.clear(); pinError.text = ""; visible = true; pinField.forceActiveFocus() }
        function close() { visible = false }

        Rectangle { anchors.fill: parent; color: Qt.rgba(0.02, 0.02, 0.05, 0.92) }
        MouseArea { anchors.fill: parent }   // swallow clicks behind the dialog

        VxCard {
            anchors.centerIn: parent
            width: 360
            implicitHeight: pinCol.implicitHeight + 44
            height: implicitHeight
            accent: Theme.amber
            ColumnLayout {
                id: pinCol
                anchors.fill: parent
                spacing: 12
                SectionLabel { label: "STAFF ESCAPE"; accent: Theme.amber }
                Text { text: "Staff PIN required"; color: Theme.textPrimary
                       font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 20 }
                Text { text: "Closing Vortex returns this PC to the desktop."
                       color: Theme.textMuted; font.family: Theme.fontBody; font.pixelSize: 13
                       Layout.fillWidth: true; wrapMode: Text.WordWrap }
                VxField { id: pinField; Layout.fillWidth: true; label: "PIN"; echo: true
                          onAccepted: pinOverlay.submit() }
                Text { id: pinError; color: Theme.magenta; font.family: Theme.fontMono
                       font.pixelSize: 11; font.letterSpacing: 1; font.capitalization: Font.AllUppercase
                       visible: text.length > 0 }
                RowLayout {
                    Layout.fillWidth: true; spacing: 10
                    VxButton { Layout.fillWidth: true; text: "CANCEL"; filled: false
                               onClicked: pinOverlay.close() }
                    VxButton { Layout.fillWidth: true; text: "EXIT"; accent: Theme.amber
                               onClicked: pinOverlay.submit() }
                }
            }
        }
        function submit() {
            if (!pinField.text) { pinField.forceActiveFocus(); return }
            pinError.text = "CHECKING…"
            vortex.adminExit(pinField.text.trim())
        }
    }

    // ---------------- wiring ----------------
    Connections {
        target: vortex
        function onWelcomeReceived(s) { win.applyState(s) }
        function onSessionChanged(s) {
            if (s) { hubScreen.applySession(s); if (win.screen !== "hub") win.screen = "hub" }
        }
        function onSessionEnded(reason, message) {
            win.screen = "login"
            loginScreen.registerMode = false
            loginScreen.setNotice(message, reason === "expired" ? "bad" : (reason === "logout" ? "good" : ""))
            pinOverlay.close()
        }
        function onWarned(rem, th) {
            toast.show(Math.max(1, Math.round(rem / 60)) + " MINUTES LEFT · TOP UP AT THE COUNTER", 5000, Theme.amber)
        }
        function onMessaged(title, body, level) {
            toast.show((title ? title + " — " : "") + body, 6000, level === "warn" ? Theme.amber : Theme.cyan)
        }
        function onLinkChanged(online, err) {
            if (!online && win.screen !== "splash")
                toast.show("SERVER OFFLINE · RECONNECTING", 3000, Theme.amber)
        }
        function onAdminExitRequested() { pinOverlay.open() }
        function onAdminExitResult(ok, message) {
            if (ok) pinError.text = "PIN ACCEPTED · CLOSING"
            else { pinError.text = (message || "WRONG PIN"); pinField.clear(); pinField.forceActiveFocus() }
        }
        function onPeripheralsChanged(p) { hubScreen.peripherals = p }
        function onStationLockChanged(locked) {
            if (locked && win.screen === "login")
                loginScreen.setNotice("STATION LOCKED BY STAFF · ASK THE COUNTER", "")
        }
    }

    function applyState(s) {
        if (s && s.session) { hubScreen.applySession(s.session); win.screen = "hub" }
    }
    Component.onCompleted: applyState(vortex.snapshot())
}
