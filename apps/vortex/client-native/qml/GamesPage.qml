import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Library page — used for both Games (kind:"game") and Apps (kind:"app").
Item {
    id: root
    property string kind: "game"
    signal notify(string msg)

    property var items: kind === "game" ? vortex.games() : vortex.apps()
    // Only show entries that actually have a brand icon (hide letter-fallback titles).
    readonly property var shown: items.filter(function (g) { return Theme.iconFor(g.name) !== "" })
    property string cat: "all"
    property string search: ""

    function chips() {
        var seen = {}, out = [{ key: "all", label: "ALL" }]
        for (var i = 0; i < shown.length; i++) {
            var c = shown[i].cat
            if (c && !seen[c]) { seen[c] = 1; out.push({ key: c, label: c.toUpperCase() }) }
        }
        return out
    }
    function filtered() {
        var q = search.toLowerCase()
        return shown.filter(function (g) {
            return (cat === "all" || g.cat === cat) && (!q || g.name.toLowerCase().indexOf(q) >= 0)
        })
    }
    function accentFor(i) { return [Theme.cyan, Theme.magenta, Theme.green, Theme.amber][i % 4] }

    ColumnLayout {
        anchors.fill: parent
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 18; Layout.rightMargin: 18
            SectionLabel { label: root.kind === "game" ? "GAMES" : "APPS" }
            Item { Layout.fillWidth: true }
            VxField {
                id: searchField
                Layout.preferredWidth: 240
                label: ""
                placeholder: root.kind === "game" ? "Search games…" : "Search apps…"
                onTextChanged: root.search = text
            }
        }
        FilterChips {
            Layout.fillWidth: true
            Layout.leftMargin: 18; Layout.rightMargin: 18
            model: root.chips()
            current: root.cat
            onPicked: (k) => root.cat = k
        }

        ScrollView {
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true; contentWidth: availableWidth
            // Padded wrapper: a hovered tile lifts (scale) and glows past its bounds, and the
            // ScrollView clips at its edge, so tiles must not sit flush against it.
            Item {
                width: parent.width
                implicitHeight: grid.implicitHeight + 36
                GridLayout {
                    id: grid
                    x: 18; y: 18
                    width: parent.width - 36
                    columns: Math.max(2, Math.floor((root.width - 36) / 200))
                    columnSpacing: 14; rowSpacing: 14
                    Repeater {
                        model: root.filtered()
                        delegate: GameTile {
                            required property var modelData
                            required property int index
                            Layout.fillWidth: true
                            Layout.preferredHeight: width   // square: frame matches the square icon
                            name: modelData.name
                            subtitle: modelData.sub || ""
                            accent: root.accentFor(index)
                            onActivated: { vortex.launch(root.kind, modelData.name); root.notify("Launching " + modelData.name + "…") }
                        }
                    }
                }
            }
        }
        Text {
            visible: root.filtered().length === 0
            text: "NOTHING HERE YET"
            color: Theme.textDim; font.family: Theme.fontMono; font.pixelSize: 12; font.letterSpacing: 2
            Layout.alignment: Qt.AlignHCenter; Layout.topMargin: 20
        }
    }
}
