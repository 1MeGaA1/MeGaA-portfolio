import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    id: root
    property var session: null
    property int remaining: 0
    property int budget: 1
    property var peripherals: null
    signal notify(string msg)
    signal recharge()
    signal contactAdmin()
    signal joinFeatured(string title)

    function accentFor(i) { return [Theme.cyan, Theme.magenta, Theme.green, Theme.amber][i % 4] }
    readonly property var recent: vortex.games().filter(function (g) { return Theme.iconFor(g.name) !== "" }).slice(0, 6)
    readonly property var launchers: vortex.apps().filter(function (a) { return a.cat === "launchers" && Theme.iconFor(a.name) !== "" })

    // featured banner event (admin "show on Home"); null = no banner at all
    property var featured: vortex.featured()
    readonly property bool hasFeatured: featured !== null && featured !== undefined
    readonly property color featAccent: (hasFeatured && featured.kind === "offer") ? Theme.amber : Theme.magenta
    Connections {
        target: vortex
        function onEventsChanged() { root.featured = vortex.featured() }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 20

        // ---- main content ----
        ScrollView {
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true; contentWidth: availableWidth
            ColumnLayout {
                // inset so a hovered tile's lift + glow isn't clipped by the ScrollView edge
                x: 18
                width: parent.width - 36
                spacing: 18

                // featured event banner (hidden — no space taken — when nothing is featured)
                Rectangle {
                    id: banner
                    readonly property var f: root.hasFeatured ? root.featured : ({})
                    function detail() {
                        return [f.title, f.game, f.when].filter(function (s) { return s && s.length }).join(" · ")
                    }
                    visible: root.hasFeatured
                    Layout.fillWidth: true
                    implicitHeight: 184
                    color: Theme.bgPanel
                    border.color: Theme.glow(root.featAccent, 0.6); border.width: 1
                    Rectangle { anchors.fill: parent; gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: Theme.glow(root.featAccent, 0.10) }
                        GradientStop { position: 1.0; color: "transparent" } } }
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 22; spacing: 16
                        ColumnLayout {
                            spacing: 6; Layout.fillWidth: true
                            Text { text: "// " + (banner.f.tag || (banner.f.kind === "offer" ? "SPECIAL OFFER" : "FEATURED EVENT"))
                                   color: root.featAccent
                                   font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 2 }
                            Text { text: banner.f.title || ""; color: Theme.textPrimary; Layout.fillWidth: true; elide: Text.ElideRight
                                   font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 28 }
                            RowLayout {
                                spacing: 14
                                Text { visible: text.length > 0; text: banner.f.game || ""; color: Theme.cyan; font.family: Theme.fontMono; font.pixelSize: 12; font.letterSpacing: 1 }
                                Text { visible: text.length > 0; text: banner.f.players || ""; color: Theme.textMuted; font.family: Theme.fontMono; font.pixelSize: 12 }
                                Text { visible: text.length > 0; text: banner.f.when || ""; color: Theme.amber; font.family: Theme.fontMono; font.pixelSize: 12 }
                            }
                            Text { text: banner.f.kind === "offer" ? "PRICE" : "PRIZE POOL"; color: Theme.textDim
                                   font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 2 }
                            Text { text: banner.f.prize || ""; color: Theme.amber
                                   font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 24 }
                        }
                        RowLayout {
                            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                            spacing: 12
                            VxButton { text: "DETAILS"; accent: Theme.cyan; filled: false; hpad: 16
                                       onClicked: root.notify(banner.detail()) }
                            VxButton { text: banner.f.kind === "offer" ? "CLAIM →" : "JOIN NOW →"; accent: root.featAccent
                                       onClicked: root.joinFeatured(banner.f.title || "") }
                        }
                    }
                }

                SectionLabel { label: "RECENTLY USED" }
                GridLayout {
                    Layout.fillWidth: true
                    columns: Math.max(1, Math.floor((root.width - 270) / 214))
                    columnSpacing: 14; rowSpacing: 14
                    Repeater {
                        model: root.recent
                        delegate: GameTile {
                            required property var modelData
                            required property int index
                            Layout.preferredWidth: 200; Layout.preferredHeight: 200
                            name: modelData.name; subtitle: modelData.sub || ""; accent: root.accentFor(index)
                            onActivated: { vortex.launch("game", modelData.name); root.notify("Launching " + modelData.name + "…") }
                        }
                    }
                }

                SectionLabel { label: "LAUNCHERS" }
                GridLayout {
                    Layout.fillWidth: true
                    columns: Math.max(1, Math.floor((root.width - 270) / 214))
                    columnSpacing: 14; rowSpacing: 14
                    Repeater {
                        model: root.launchers
                        delegate: GameTile {
                            required property var modelData
                            required property int index
                            Layout.preferredWidth: 200; Layout.preferredHeight: 200
                            name: modelData.name; subtitle: modelData.sub || ""; accent: root.accentFor(index + 2)
                            onActivated: { vortex.launch("app", modelData.name); root.notify("Launching " + modelData.name + "…") }
                        }
                    }
                }
                Item { Layout.fillHeight: true; implicitHeight: 24 }
            }
        }

        // ---- account sidebar ----
        AccountCard {
            Layout.preferredWidth: 250
            Layout.fillHeight: true
            session: root.session
            remaining: root.remaining
            budget: root.budget
            peripherals: root.peripherals
            onRecharge: root.recharge()
            onContactAdmin: root.contactAdmin()
        }
    }
}
