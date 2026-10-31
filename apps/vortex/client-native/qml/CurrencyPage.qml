import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    id: root
    signal notify(string msg)
    property int sel: 0
    readonly property var game: Content.currency[sel]

    ColumnLayout {
        anchors.fill: parent
        spacing: 14
        SectionLabel { label: "GAMES CURRENCY" }

        // game selector
        Flow {
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: Content.currency
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    implicitWidth: gt.implicitWidth + 26; implicitHeight: 34
                    color: root.sel === index ? Qt.rgba(0, 0.9, 1, 0.10) : "transparent"
                    border.color: root.sel === index ? modelData.a : Theme.border
                    border.width: 1
                    Text { id: gt; anchors.centerIn: parent; text: modelData.name
                           color: root.sel === index ? Theme.textPrimary : Theme.textMuted
                           font.family: Theme.fontDisplay; font.weight: Font.Medium; font.pixelSize: 13; font.letterSpacing: 1 }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.sel = index }
                }
            }
        }

        // selected game header
        VxCard {
            Layout.fillWidth: true
            implicitHeight: 84
            accent: root.game.a
            RowLayout {
                anchors.fill: parent
                Rectangle {
                    width: 48; height: 48; radius: 6
                    gradient: Gradient { GradientStop { position: 0; color: root.game.a } GradientStop { position: 1; color: root.game.b } }
                    Text { anchors.centerIn: parent; text: root.game.name.charAt(0)
                           color: "#ffffff"; font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 24 }
                }
                ColumnLayout {
                    spacing: 2; Layout.leftMargin: 6
                    Text { text: root.game.name + " · " + root.game.cur; color: Theme.textPrimary
                           font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 18 }
                    Text { text: "BALANCE " + root.game.balance.toLocaleString(Qt.locale(), "f", 0) + " " + root.game.cur
                           color: Theme.textMuted; font.family: Theme.fontMono; font.pixelSize: 11; font.letterSpacing: 1 }
                }
                Item { Layout.fillWidth: true }
            }
        }

        SectionLabel { label: "TOP UP " + root.game.cur; accent: Theme.magenta }
        ScrollView {
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true; contentWidth: availableWidth
            GridLayout {
                width: parent.width
                columns: Math.max(2, Math.floor(root.width / 175))
                columnSpacing: 14; rowSpacing: 14
                Repeater {
                    model: Content.currencyPacks
                    delegate: CurrencyCard {
                        required property var modelData
                        Layout.fillWidth: true; Layout.preferredHeight: 120
                        amount: modelData.amount; price: modelData.price; unit: root.game.cur; accent: root.game.a
                        onBuy: root.notify(modelData.amount + " " + root.game.cur + " · $" + modelData.price + " · charged to session")
                    }
                }
            }
        }
    }
}
