import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    id: root
    property var session: null
    property var peripherals: null
    property int remaining: 0
    property int budget: 1
    property int points: 42024
    property int page: 0                 // 0 home 1 games 2 apps 3 shop 4 currency 5 events
    property int parkDist: 80             // how far pages slide during the transition
    property string nameOverride: ""
    property string openMenu: ""         // "friends" | "settings" | "user" | ""
    signal logoutRequested()

    readonly property string displayName: nameOverride.length ? nameOverride
        : (session && session.member ? session.member.username : "GUEST")
    readonly property var onlineFriends: Content.friends.filter(function (f) { return f.online })
    readonly property var offlineFriends: Content.friends.filter(function (f) { return !f.online })
    readonly property int friendsOnline: onlineFriends.length
    readonly property int friendsOffline: offlineFriends.length

    function applySession(s) {
        session = s
        if (s) { remaining = Math.max(0, s.remaining_seconds || 0); budget = Math.max(1, s.budget_seconds || 1) }
    }
    function toast(msg, color) { toastItem.show(msg, 2600, color || Theme.cyan) }

    Rectangle { anchors.fill: parent; color: Theme.bg }
    HubBackground { anchors.fill: parent }

    // ================= top bar =================
    Rectangle {
        id: topbar
        anchors { top: parent.top; left: parent.left; right: parent.right }
        height: 60; color: Theme.bgPanelAlt
        Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 1; color: Theme.borderDim }
        RowLayout {
            anchors.fill: parent; anchors.leftMargin: 22; anchors.rightMargin: 22; spacing: 18
            Text { text: "VORTEX"; color: Theme.textPrimary; font.family: Theme.fontDisplay
                   font.weight: Font.Bold; font.pixelSize: 22; font.letterSpacing: 5 }
            Row {
                spacing: 2
                Repeater {
                    model: [ "HOME", "GAMES", "APPS", "SHOP", "GAMES CURRENCY", "EVENTS" ]
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        width: nt.implicitWidth + 24; height: 36
                        color: root.page === index ? Qt.rgba(0, 0.9, 1, 0.08) : "transparent"
                        Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                                    height: 2; color: root.page === index ? Theme.cyan : "transparent" }
                        Text { id: nt; anchors.centerIn: parent; text: modelData
                               color: root.page === index ? Theme.cyan : Theme.textMuted
                               font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 12; font.letterSpacing: 1.5 }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                    onClicked: { root.page = index; root.openMenu = "" } }
                    }
                }
            }
            Item { Layout.fillWidth: true }

            // friends
            TopButton { icon: "friends"; text: "FRIENDS " + root.friendsOnline; active: root.openMenu === "friends"
                        onClicked: root.openMenu = root.openMenu === "friends" ? "" : "friends" }
            // settings
            TopButton { icon: "settings"; text: "SETTINGS"; active: root.openMenu === "settings"
                        onClicked: root.openMenu = root.openMenu === "settings" ? "" : "settings" }
            // session timer chip
            Rectangle {
                Layout.preferredHeight: 38; Layout.preferredWidth: tt.implicitWidth + 26
                color: Theme.surface; border.width: 1
                border.color: root.remaining < 600 ? Theme.magenta : (root.remaining < 1800 ? Theme.amber : Theme.cyan)
                Text { id: tt; anchors.centerIn: parent; text: Theme.clock(root.remaining)
                       color: root.remaining < 600 ? Theme.magenta : (root.remaining < 1800 ? Theme.amber : Theme.cyan)
                       font.family: Theme.fontMono; font.weight: Font.Medium; font.pixelSize: 16; font.letterSpacing: 1 }
            }
            // user avatar
            Rectangle {
                Layout.preferredWidth: 38; Layout.preferredHeight: 38
                color: root.openMenu === "user" ? Theme.cyan : Theme.surface
                border.color: Theme.cyan; border.width: 1
                Text { anchors.centerIn: parent; text: root.displayName.charAt(0).toUpperCase()
                       color: root.openMenu === "user" ? Theme.bgPanel : Theme.cyan
                       font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 16 }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: root.openMenu = root.openMenu === "user" ? "" : "user" }
            }
        }
    }

    // ================= pages =================
    Item {
        id: pageArea
        anchors { top: topbar.bottom; left: parent.left; right: parent.right; bottom: statusbar.top }
        anchors.margins: 24
        clip: true

        PageSlot { idx: 0
            HomePage {
                anchors.fill: parent
                session: root.session; remaining: root.remaining; budget: root.budget; peripherals: root.peripherals
                onNotify: (m) => root.toast(m)
                onRecharge: root.toast("Ask the counter to add time or points", Theme.amber)
                onContactAdmin: root.toast("Admin notified — someone will come over", Theme.green)
                onJoinFeatured: (t) => root.toast("Registered · " + t, Theme.green)
            }
        }
        PageSlot { idx: 1; GamesPage { anchors.fill: parent; kind: "game"; onNotify: (m) => root.toast(m) } }
        PageSlot { idx: 2; GamesPage { anchors.fill: parent; kind: "app";  onNotify: (m) => root.toast(m) } }
        PageSlot { idx: 3; ShopPage { anchors.fill: parent; onNotify: (m) => root.toast(m, Theme.green) } }
        PageSlot { idx: 4; CurrencyPage { anchors.fill: parent; onNotify: (m) => root.toast(m, Theme.green) } }
        PageSlot { idx: 5; EventsPage { anchors.fill: parent; onNotify: (m) => root.toast(m, Theme.green) } }
    }

    // ================= status bar =================
    Rectangle {
        id: statusbar
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 30; color: Theme.bgPanelAlt
        Rectangle { anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 1; color: Theme.borderDim }
        RowLayout {
            anchors.fill: parent; anchors.leftMargin: 22; anchors.rightMargin: 22; spacing: 20
            Text { text: "● ONLINE"; color: Theme.green; font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 1.5 }
            Text { text: (vortex.stationName || "STATION") + " · VORTEX"; color: Theme.textDim
                   font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 1.5 }
            Text { text: root.friendsOnline + " FRIENDS ONLINE"; color: Theme.textDim
                   font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 1.5 }
            Item { Layout.fillWidth: true }
            Text { text: "VORTEX v" + vortex.version; color: Theme.textFaint; font.family: Theme.fontMono; font.pixelSize: 10 }
        }
    }

    // ================= menu catcher =================
    MouseArea { anchors.fill: parent; visible: root.openMenu !== ""; z: 40; onClicked: root.openMenu = "" }

    // ---- friends menu (matches the original web design) ----
    Rectangle {
        visible: root.openMenu === "friends"; z: 50
        anchors { top: topbar.bottom; right: parent.right; topMargin: 6; rightMargin: 120 }
        width: 340; height: 470
        color: Theme.bgPanel; border.color: Theme.border; border.width: 1
        Rectangle { anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 2; color: Theme.cyan }
        ColumnLayout {
            id: fcol; anchors.fill: parent; anchors.margins: 14; spacing: 10
            // header
            ColumnLayout {
                Layout.fillWidth: true; spacing: 3
                RowLayout {
                    Layout.fillWidth: true
                    SectionLabel { label: "FRIENDS" }
                    Item { Layout.fillWidth: true }
                    Text { text: "+ ADD"; color: Theme.cyan; font.family: Theme.fontDisplay; font.weight: Font.Bold
                           font.pixelSize: 11; font.letterSpacing: 1.5
                           MouseArea { anchors.fill: parent; anchors.margins: -6; cursorShape: Qt.PointingHandCursor
                                       onClicked: { root.openMenu = ""; addFriend.open() } } }
                }
                Text { text: root.friendsOnline + " online · " + root.friendsOffline + " offline"
                       color: Theme.textDim; font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 1 }
            }
            ScrollView {
                id: fsv
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                ColumnLayout {
                    width: fsv.availableWidth; spacing: 8
                    Text { text: "ONLINE"; color: Theme.textDim; font.family: Theme.fontMono
                           font.pixelSize: 9; font.letterSpacing: 2 }
                    Repeater { model: root.onlineFriends
                        delegate: FriendRow { required property var modelData; f: modelData; Layout.fillWidth: true } }
                    Item { implicitHeight: 4 }
                    Text { text: "OFFLINE"; color: Theme.textDim; font.family: Theme.fontMono
                           font.pixelSize: 9; font.letterSpacing: 2 }
                    Repeater { model: root.offlineFriends
                        delegate: FriendRow { required property var modelData; f: modelData; Layout.fillWidth: true } }
                }
            }
        }
    }

    // ---- settings menu ----
    Rectangle {
        visible: root.openMenu === "settings"; z: 50
        anchors { top: topbar.bottom; right: parent.right; topMargin: 6; rightMargin: 70 }
        width: 220; height: scol.implicitHeight + 24
        color: Theme.bgPanel; border.color: Theme.border; border.width: 1
        Rectangle { anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 2; color: Theme.cyan }
        ColumnLayout {
            id: scol; anchors.fill: parent; anchors.margins: 12; spacing: 4
            SectionLabel { label: "SETTINGS" }
            MenuRow { text: "Change username"; onClicked: { root.openMenu = ""; changeUser.open() } }
            MenuRow { text: "Change password"; onClicked: { root.openMenu = ""; changePass.open() } }
            MenuRow { text: "Preferences";      onClicked: { root.openMenu = ""; prefs.open() } }
        }
    }

    // ---- user menu ----
    Rectangle {
        visible: root.openMenu === "user"; z: 50
        anchors { top: topbar.bottom; right: parent.right; topMargin: 6; rightMargin: 22 }
        width: 220; height: ucol.implicitHeight + 24
        color: Theme.bgPanel; border.color: Theme.border; border.width: 1
        Rectangle { anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 2; color: Theme.magenta }
        ColumnLayout {
            id: ucol; anchors.fill: parent; anchors.margins: 12; spacing: 6
            Text { text: root.displayName; color: Theme.textPrimary; font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 16 }
            Text { text: (root.session && root.session.member ? (root.session.member.tier || "MEMBER") : "GUEST")
                         + " · " + (vortex.stationName || "STATION")
                   color: Theme.textMuted; font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 1 }
            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderDim }
            MenuRow { text: "Log out"; accent: Theme.magenta; onClicked: { root.openMenu = ""; root.logoutRequested() } }
        }
    }

    // ================= overlays =================
    ModalOverlay {
        id: msgFriend; property string who: ""
        label: "MESSAGE"; title: "Message " + who; accent: Theme.cyan
        VxField { id: msgText; Layout.fillWidth: true; label: "MESSAGE"; placeholder: "Type a message…" }
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            VxButton { Layout.fillWidth: true; text: "CANCEL"; filled: false; onClicked: msgFriend.close() }
            VxButton { Layout.fillWidth: true; text: "SEND"; onClicked: {
                if (msgText.text.length) { root.toast("Message sent to " + msgFriend.who, Theme.green); msgFriend.close() } } }
        }
        onOpenned: msgText.clear()
    }
    ModalOverlay {
        id: addFriend; label: "ADD FRIEND"; title: "Add a friend"; accent: Theme.cyan
        VxField { id: addName; Layout.fillWidth: true; label: "USERNAME"; placeholder: "their username" }
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            VxButton { Layout.fillWidth: true; text: "CANCEL"; filled: false; onClicked: addFriend.close() }
            VxButton { Layout.fillWidth: true; text: "SEND REQUEST"; onClicked: {
                if (addName.text.length) { root.toast("Friend request sent to " + addName.text, Theme.green); addFriend.close() } } }
        }
        onOpenned: addName.clear()
    }
    ModalOverlay {
        id: changeUser; label: "CHANGE USERNAME"; title: "New username"; accent: Theme.cyan
        VxField { id: newUser; Layout.fillWidth: true; label: "USERNAME"; placeholder: "3+ letters, numbers, _" }
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            VxButton { Layout.fillWidth: true; text: "CANCEL"; filled: false; onClicked: changeUser.close() }
            VxButton { Layout.fillWidth: true; text: "SAVE"; onClicked: {
                var n = newUser.text.trim()
                if (n.length < 3) { root.toast("Username must be 3+ characters", Theme.magenta); return }
                root.nameOverride = n; root.toast("Username changed to " + n, Theme.green); changeUser.close() } }
        }
        onOpenned: newUser.clear()
    }
    ModalOverlay {
        id: changePass; label: "CHANGE PASSWORD"; title: "Update password"; accent: Theme.magenta
        VxField { id: curPass; Layout.fillWidth: true; label: "CURRENT PASSWORD"; echo: true }
        VxField { id: newPass; Layout.fillWidth: true; label: "NEW PASSWORD"; echo: true }
        VxField { id: cfmPass; Layout.fillWidth: true; label: "CONFIRM"; echo: true }
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            VxButton { Layout.fillWidth: true; text: "CANCEL"; filled: false; onClicked: changePass.close() }
            VxButton { Layout.fillWidth: true; text: "UPDATE"; accent: Theme.magenta; onClicked: {
                if (!curPass.text) { root.toast("Enter your current password", Theme.magenta); return }
                if (newPass.text.length < 6) { root.toast("New password must be 6+ chars", Theme.magenta); return }
                if (newPass.text !== cfmPass.text) { root.toast("Passwords do not match", Theme.magenta); return }
                root.toast("Password updated", Theme.green); changePass.close() } }
        }
        onOpenned: { curPass.clear(); newPass.clear(); cfmPass.clear() }
    }
    ModalOverlay {
        id: prefs; label: "PREFERENCES"; title: "Preferences"; accent: Theme.cyan
        PrefToggle { id: pSound; Layout.fillWidth: true; text: "Sound effects"; on: true }
        PrefToggle { id: pNotif; Layout.fillWidth: true; text: "Notifications"; on: true }
        PrefToggle { id: pAuto;  Layout.fillWidth: true; text: "Auto-launch favourites"; on: false }
        PrefToggle { id: pCompact; Layout.fillWidth: true; text: "Compact layout"; on: false }
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            VxButton { Layout.fillWidth: true; text: "CANCEL"; filled: false; onClicked: prefs.close() }
            VxButton { Layout.fillWidth: true; text: "SAVE"; onClicked: { root.toast("Preferences saved", Theme.green); prefs.close() } }
        }
    }

    Toast { id: toastItem }

    // ================= session countdown =================
    Timer {
        interval: 1000; running: root.session !== null && root.remaining > 0; repeat: true
        onTriggered: { root.remaining = root.remaining - 1; if (root.remaining <= 0) vortex.localExpired() }
    }

    // a page slot: parked to the left/right of the current page and faded out,
    // slides to centre + fades in when it becomes the current page (direction-aware).
    component PageSlot: Item {
        property int idx: 0
        default property alias content: holder.data
        readonly property bool active: root.page === idx
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: parent ? parent.width : 0
        x: active ? 0 : (idx < root.page ? -root.parkDist : root.parkDist)
        opacity: active ? 1 : 0
        visible: opacity > 0.01
        Behavior on x { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
        Item { id: holder; anchors.fill: parent }
    }

    // a friend row: coloured avatar + name + status + MESSAGE (matches web)
    component FriendRow: RowLayout {
        property var f: null
        spacing: 10
        opacity: (f && f.online) ? 1.0 : 0.5
        Rectangle {
            Layout.preferredWidth: 32; Layout.preferredHeight: 32; radius: 16
            color: (f && f.av) ? f.av : Theme.surface
            border.color: Theme.border; border.width: (f && f.av) ? 0 : 1
            Text { anchors.centerIn: parent; text: f ? f.name.charAt(0).toUpperCase() : "?"
                   color: (f && f.avText) ? f.avText : Theme.textMuted
                   font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 15 }
        }
        ColumnLayout {
            spacing: 0; Layout.fillWidth: true
            Text { text: f ? f.name : ""; color: Theme.textPrimary
                   font.family: Theme.fontBody; font.pixelSize: 13; Layout.fillWidth: true; elide: Text.ElideRight }
            Text { text: (f && f.online ? "● " : "") + (f ? f.status : "")
                   color: (f && f.online) ? Theme.green : Theme.textDim
                   font.family: Theme.fontMono; font.pixelSize: 10; Layout.fillWidth: true; elide: Text.ElideRight }
        }
        Rectangle {
            Layout.preferredWidth: fmsgRow.implicitWidth + 18; Layout.preferredHeight: 26
            color: Qt.rgba(0, 0.9, 1, 0.10); border.color: Theme.cyan; border.width: 1
            Row {
                id: fmsgRow
                anchors.centerIn: parent
                spacing: 6
                Image { anchors.verticalCenter: parent.verticalCenter; width: 11; height: 11
                        sourceSize.width: 22; sourceSize.height: 22; smooth: true; source: "icons/ui/chat_cyan.png" }
                Text { id: fmsg; anchors.verticalCenter: parent.verticalCenter; text: "MESSAGE"; color: Theme.cyan
                       font.family: Theme.fontMono; font.weight: Font.Bold; font.pixelSize: 10; font.letterSpacing: 1.5 }
            }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: { root.openMenu = ""; msgFriend.who = f.name; msgFriend.open() } }
        }
    }

    // small reusable top-bar button
    component TopButton: Rectangle {
        id: tb
        property string text: ""
        property string icon: ""            // icons/ui/<icon>_cyan|_muted.png; "" = text only
        property bool active: false
        property bool big: false
        signal clicked()
        implicitHeight: 36; implicitWidth: tbRow.implicitWidth + 22
        color: active ? Qt.rgba(0, 0.9, 1, 0.08) : "transparent"
        border.color: active ? Theme.cyan : Theme.border; border.width: 1
        Row {
            id: tbRow
            anchors.centerIn: parent
            spacing: 7
            Image {
                visible: tb.icon.length > 0
                anchors.verticalCenter: parent.verticalCenter
                width: 14; height: 14
                sourceSize.width: 28; sourceSize.height: 28
                smooth: true
                source: tb.icon.length ? "icons/ui/" + tb.icon + (tb.active ? "_cyan" : "_muted") + ".png" : ""
            }
            Text { id: tbt; anchors.verticalCenter: parent.verticalCenter; text: tb.text
                   color: tb.active ? Theme.cyan : Theme.textMuted
                   font.family: tb.big ? Theme.fontBody : Theme.fontDisplay
                   font.weight: Font.Bold; font.pixelSize: tb.big ? 16 : 12; font.letterSpacing: 1.5 }
        }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: tb.clicked() }
    }
    // menu row
    component MenuRow: Rectangle {
        property string text: ""
        property color accent: Theme.cyan
        signal clicked()
        Layout.fillWidth: true; implicitHeight: 34; color: mra.containsMouse ? Qt.rgba(1,1,1,0.04) : "transparent"
        Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 6
               text: parent.text; color: mra.containsMouse ? parent.accent : Theme.textMuted
               font.family: Theme.fontBody; font.pixelSize: 13 }
        MouseArea { id: mra; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: parent.clicked() }
    }
    // preference toggle row
    component PrefToggle: RowLayout {
        property string text: ""
        property bool on: false
        Text { text: parent.text; color: Theme.textPrimary; font.family: Theme.fontBody; font.pixelSize: 13; Layout.fillWidth: true }
        Rectangle {
            width: 44; height: 22; radius: 11
            color: parent.on ? Theme.cyan : Theme.surface
            border.color: parent.on ? Theme.cyan : Theme.border; border.width: 1
            Rectangle { width: 16; height: 16; radius: 8; color: parent.parent.on ? Theme.bgPanel : Theme.textDim
                        anchors.verticalCenter: parent.verticalCenter
                        x: parent.parent.on ? parent.width - width - 3 : 3
                        Behavior on x { NumberAnimation { duration: 120 } } }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: parent.parent.on = !parent.parent.on }
        }
    }
}
