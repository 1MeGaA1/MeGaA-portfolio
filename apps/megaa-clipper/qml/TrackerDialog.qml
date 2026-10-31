import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Earnings tracker (web pro.js #tracker): every posted clip, its views and estimated earnings (views x the
// campaign's pay per 1,000 views), totals per campaign and which caption style / layout / teaser works best.
NeonDialog {
    id: dlg
    title: "Earnings tracker"
    width: Math.min(960, (parent ? parent.width : 1000) - 80)
    height: Math.min(700, (parent ? parent.height : 760) - 80)

    readonly property var entries: Store.trackerEntries
    readonly property real totalViews: entries.reduce((s, e) => s + e.views, 0)
    readonly property real totalMoney: entries.reduce((s, e) => s + Store.earned(e), 0)
    readonly property var best: entries.length ? entries.slice().sort((a, b) => b.views - a.views)[0] : null

    function show() { Store.loadTracker(); open() }

    function campaignName(id) {
        const c = Store.campaigns.find(x => x.id === id)
        return c ? c.name : "No campaign"
    }

    // views and earnings per campaign
    readonly property var byCampaign: {
        const groups = {}
        for (const e of entries) {
            const key = e.campaign || ""
            groups[key] = groups[key] || { name: campaignName(e.campaign), views: 0, money: 0, clips: 0 }
            groups[key].views += e.views
            groups[key].money += Store.earned(e)
            groups[key].clips += 1
        }
        return Object.keys(groups).map(k => groups[k])
    }

    // the best average views by caption style, layout and teaser – what to make more of
    readonly property var whatWorks: {
        if (!entries.length) return []
        const sorts = [
            ["Caption style", e => Store.styles[e.style] ? Store.styles[e.style].label : e.style],
            ["Layout", e => e.layout === "fit" ? "fit + blur" : e.layout],
            ["Teaser", e => e.teaser ? "with teaser" : "no teaser"]
        ]
        return sorts.map(pair => {
            const groups = {}
            for (const e of entries) {
                const key = pair[1](e) || "—"
                groups[key] = groups[key] || []
                groups[key].push(e.views)
            }
            const rows = Object.keys(groups).map(k => [k, groups[k].reduce((a, b) => a + b, 0) / groups[k].length, groups[k].length])
            rows.sort((a, b) => b[1] - a[1])
            return { label: pair[0], best: rows[0][0], avg: rows[0][1], n: rows[0][2] }
        })
    }

    component Tile: Rectangle {
        property string label: ""
        property string value: ""
        property bool big: true
        Layout.fillWidth: true
        implicitHeight: 74
        radius: 12
        color: Theme.field
        border.color: Theme.line
        Column {
            x: 14
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 28
            spacing: 6
            FieldLabel { label: parent.parent.label }
            Text {
                width: parent.width
                text: parent.parent.value
                elide: Text.ElideRight
                color: Theme.text
                font.family: Theme.mono
                font.pixelSize: parent.parent.big ? 20 : 13
                font.weight: Font.DemiBold
            }
        }
    }

    component Line: RowLayout {
        property string name: ""
        property string info: ""
        property string amount: ""
        property color amountColor: Theme.ok
        Layout.fillWidth: true
        spacing: 10
        Text { Layout.fillWidth: true; text: parent.name; elide: Text.ElideRight; color: Theme.text; font.pixelSize: 12 }
        Text { text: parent.info; color: Theme.muted; font.family: Theme.mono; font.pixelSize: 11 }
        Text { text: parent.amount; color: parent.amountColor; font.family: Theme.mono; font.pixelSize: 12 }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 10
        Tile { label: "Est. earnings"; value: Store.money(dlg.totalMoney) }
        Tile { label: "Total views"; value: Store.count(dlg.totalViews) }
        Tile { label: "Clips posted"; value: String(dlg.entries.length) }
        Tile { label: "Best clip"; big: false; value: dlg.best ? `${dlg.best.clip} · ${Store.count(dlg.best.views)}` : "—" }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 18
        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            spacing: 6
            FieldLabel { label: "By campaign" }
            Repeater {
                model: dlg.byCampaign
                Line {
                    required property var modelData
                    name: modelData.name
                    info: `${modelData.clips} clip${modelData.clips === 1 ? "" : "s"} · ${Store.count(modelData.views)} views`
                    amount: Store.money(modelData.money)
                }
            }
            Text { visible: !dlg.entries.length; text: "Nothing posted yet."; color: Theme.dim; font.pixelSize: 12 }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            spacing: 6
            FieldLabel { label: "What works best" }
            Repeater {
                model: dlg.whatWorks
                Line {
                    required property var modelData
                    name: `${modelData.label}: ${modelData.best}`
                    info: `${modelData.n} post${modelData.n === 1 ? "" : "s"}`
                    amount: `avg ${Store.count(modelData.avg)} views`
                    amountColor: Theme.cyan
                }
            }
            Text {
                visible: !dlg.entries.length
                Layout.fillWidth: true
                text: "Post a few clips (the ✓ on a rendered clip) and track their views to see what works."
                wrapMode: Text.WordWrap
                color: Theme.dim
                font.pixelSize: 12
            }
        }
    }

    FieldLabel { label: "Posted clips"; note: "type the views as they grow" }

    // the posts: date, clip (opens the post), campaign, platform, views (editable), earned, remove
    ListView {
        id: table
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        spacing: 4
        model: dlg.entries
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: NeonScrollBar {}
        readonly property var widths: [86, 0, 150, 70, 110, 90, 32]   // 0 = takes the rest

        header: RowLayout {
            width: table.width - 12
            spacing: 10
            Repeater {
                model: ["Date", "Clip", "Campaign", "Platform", "Views", "Earned", ""]
                FieldLabel {
                    required property string modelData
                    required property int index
                    label: modelData
                    Layout.fillWidth: table.widths[index] === 0
                    Layout.preferredWidth: table.widths[index]
                    Layout.bottomMargin: 6
                }
            }
        }

        delegate: Rectangle {
            id: row
            required property var modelData
            width: table.width - 12
            implicitHeight: 48
            radius: 10
            color: Theme.field
            border.color: Theme.line
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 6
                spacing: 10
                Text {
                    Layout.preferredWidth: table.widths[0] - 10
                    text: row.modelData.posted || ""
                    color: Theme.muted
                    font.family: Theme.mono
                    font.pixelSize: 11
                }
                Column {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        readonly property bool link: /^https?:/i.test(row.modelData.url || "")
                        width: parent.width
                        text: row.modelData.clip || ""
                        elide: Text.ElideRight
                        color: link ? Theme.cyan : Theme.text
                        font.underline: link && clipLink.containsMouse
                        font.pixelSize: 13
                        MouseArea {
                            id: clipLink
                            anchors.fill: parent
                            enabled: parent.link
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: Qt.openUrlExternally(row.modelData.url)
                        }
                    }
                    Text {
                        width: parent.width
                        visible: !!row.modelData.hook
                        text: row.modelData.hook || ""
                        elide: Text.ElideRight
                        color: Theme.dim
                        font.pixelSize: 11
                    }
                }
                Text {
                    Layout.preferredWidth: table.widths[2]
                    text: row.modelData.campaign ? dlg.campaignName(row.modelData.campaign) : "—"
                    elide: Text.ElideRight
                    color: Theme.muted
                    font.pixelSize: 12
                }
                Text {
                    Layout.preferredWidth: table.widths[3]
                    text: row.modelData.platform || ""
                    color: Theme.muted
                    font.pixelSize: 12
                }
                NeonField {
                    Layout.preferredWidth: table.widths[4]
                    implicitHeight: 32
                    mono: true
                    text: String(row.modelData.views)
                    validator: IntValidator { bottom: 0 }
                    onEditingFinished: {
                        const views = parseInt(text) || 0
                        if (views !== row.modelData.views) Store.setViews(row.modelData, views)
                    }
                }
                Text {
                    Layout.preferredWidth: table.widths[5]
                    text: Store.money(Store.earned(row.modelData))
                    horizontalAlignment: Text.AlignRight
                    color: Theme.ok
                    font.family: Theme.mono
                    font.pixelSize: 12
                }
                IconButton {
                    glyph: Theme.icClose
                    size: 28
                    danger: true
                    ToolTip.text: "Remove from the tracker"
                    onClicked: Store.ask("Remove this post?", `Remove ${row.modelData.clip} from the earnings tracker?`, "Remove",
                                         () => Store.deleteEntry(row.modelData.id))
                }
            }
        }
    }
}
