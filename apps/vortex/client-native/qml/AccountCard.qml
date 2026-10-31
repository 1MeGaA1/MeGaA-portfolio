import QtQuick
import QtQuick.Layouts

VxCard {
    id: root
    property var session: null
    property int remaining: 0
    property int budget: 1
    property var peripherals: null
    property int points: 42024
    signal recharge()
    signal contactAdmin()
    accent: Theme.cyan

    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        SectionLabel { label: "ACCOUNT" }
        Text {
            text: root.session && root.session.member ? root.session.member.username : "GUEST"
            color: Theme.textPrimary; font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 20
        }
        Text {
            text: (root.session && root.session.member ? (root.session.member.tier || "MEMBER") : "WALK-IN")
                  + " · " + (vortex.stationName || "STATION")
            color: Theme.textMuted; font.family: Theme.fontMono; font.pixelSize: 11; font.letterSpacing: 1
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderDim }

        Text { text: "SESSION TIME"; color: Theme.textDim; font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 2 }
        Text {
            text: Theme.clock(root.remaining)
            color: root.remaining < 600 ? Theme.magenta : (root.remaining < 1800 ? Theme.amber : Theme.cyan)
            font.family: Theme.fontMono; font.weight: Font.Medium; font.pixelSize: 26
        }
        Rectangle {
            Layout.fillWidth: true; height: 6; color: Theme.surface
            Rectangle { height: parent.height; color: Theme.cyan
                        width: parent.width * Math.min(1, root.remaining / Math.max(1, root.budget)) }
        }
        Text {
            text: Theme.hm(Math.max(0, root.budget - root.remaining)) + " used · " + Theme.hm(root.remaining) + " left"
            color: Theme.textDim; font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 1
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderDim }

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 2
                Text { text: "POINTS"; color: Theme.textDim; font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 2 }
                Text { text: root.points.toLocaleString(Qt.locale(), "f", 0); color: Theme.textPrimary
                       font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 20 }
            }
            Item { Layout.fillWidth: true }
            VxButton { text: "RECHARGE"; accent: Theme.magenta; filled: false; hpad: 12; onClicked: root.recharge() }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderDim }

        Text { text: (vortex.stationName || "STATION"); color: Theme.textDim; font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 2 }
        Repeater {
            model: [ { k: "Screen", key: "screen" }, { k: "Mouse", key: "mouse" },
                     { k: "Keyboard", key: "keyboard" }, { k: "Headset", key: "headset" } ]
            delegate: RowLayout {
                required property var modelData
                Layout.fillWidth: true
                Text { text: modelData.k; color: Theme.textMuted; font.family: Theme.fontBody; font.pixelSize: 13 }
                Item { Layout.fillWidth: true }
                Text {
                    property var info: root.peripherals ? root.peripherals[modelData.key] : null
                    text: "● " + (info ? info.meta : "—")
                    color: !info ? Theme.textDim : (info.status === "ok" ? Theme.green : (info.status === "missing" ? Theme.magenta : Theme.textDim))
                    font.family: Theme.fontMono; font.pixelSize: 12
                }
            }
        }
        Item { Layout.fillHeight: true }
        VxButton { Layout.fillWidth: true; text: "CONTACT ADMIN"; accent: Theme.cyan; filled: false; onClicked: root.contactAdmin() }
    }
}
