import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Viral moments: the best clips in this video, scored. Find (free) works offline; AI picks ask Claude.
// Preview a moment, Add it, or Add all to the queue (web pro.js #moments).
NeonDialog {
    id: dlg
    title: "Viral moments"
    width: Math.min(840, (parent ? parent.width : 900) - 80)
    height: Math.min(660, (parent ? parent.height : 700) - 80)

    function show() {
        if (!Store.lines.length) { Store.toast("Transcribe the video first.", "info"); return }
        const camp = Store.currentCampaign   // the campaign's lengths are the best start
        if (camp && camp.min_len) minBox.text = String(camp.min_len)
        if (camp && camp.max_len) maxBox.text = String(camp.max_len)
        open()
        if (!Store.moments.length && !Store.aiBusy) find()
    }

    function number(text, fallback, low, high) {
        const v = parseFloat(text)
        return isFinite(v) ? Math.min(high, Math.max(low, v)) : fallback
    }
    function options() {
        return { count: Math.round(number(countBox.text, 10, 1, 30)), min: number(minBox.text, 20, 5, 600),
                 max: number(maxBox.text, 60, 5, 600) }
    }
    function find() { const o = options(); Store.findMoments(o.count, o.min, o.max) }
    function ai() { const o = options(); Store.aiMoments(o.count, o.min, o.max) }

    component SmallBox: NeonField {
        mono: true
        implicitHeight: 32
        Layout.preferredWidth: 58
        horizontalAlignment: TextInput.AlignHCenter
        validator: IntValidator { bottom: 1; top: 600 }
        onAccepted: dlg.find()
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        FieldLabel { label: "Clips" }
        SmallBox { id: countBox; text: "10" }
        FieldLabel { label: "Min s"; Layout.leftMargin: 6 }
        SmallBox { id: minBox; text: "20" }
        FieldLabel { label: "Max s"; Layout.leftMargin: 6 }
        SmallBox { id: maxBox; text: "60" }
        Item { Layout.fillWidth: true }
        NeonButton { primary: true; small: true; text: "Find (free)"; onClicked: dlg.find() }
        NeonButton {
            small: true
            iconText: Theme.icStar
            text: Store.aiBusy ? "Working…" : "AI picks"
            enabled: !Store.aiBusy
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: "Uses Claude through your API key – about $0.10–0.20 per hour of video"
            onClicked: dlg.ai()
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 10
        Text {
            Layout.fillWidth: true
            text: Store.momentsNote
            wrapMode: Text.WordWrap
            color: Store.aiBusy ? Theme.cyan : Theme.muted
            font.pixelSize: 12
        }
        NeonButton {
            small: true
            text: "Add all to queue"
            visible: Store.moments.length > 0
            onClicked: { Store.addMoments(Store.moments, Store.moments.map((m, i) => i)); dlg.close() }
        }
    }

    ListView {
        id: list
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        spacing: 8
        model: Store.moments
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: NeonScrollBar {}

        Text {
            anchors.centerIn: parent
            visible: !Store.moments.length
            text: Store.aiBusy ? "Claude is reading the transcript…" : "No moments found – try a shorter min length."
            color: Theme.dim
            font.pixelSize: 13
        }

        delegate: Rectangle {
            id: row
            required property var modelData
            required property int index
            readonly property bool added: !!Store.momentsAdded[index]
            width: ListView.view.width - 12
            implicitHeight: rowLayout.implicitHeight + 20
            radius: 12
            color: Theme.field
            border.color: Theme.line

            RowLayout {
                id: rowLayout
                anchors.fill: parent
                anchors.margins: 10
                spacing: 12

                // the score as a ring: green 80+, cyan 60+, amber below
                Canvas {
                    id: ring
                    Layout.preferredWidth: 46
                    Layout.preferredHeight: 46
                    Layout.alignment: Qt.AlignTop
                    readonly property int score: row.modelData.score || 0
                    readonly property color tint: score >= 80 ? Theme.ok : score >= 60 ? Theme.cyan : Theme.warn
                    onScoreChanged: requestPaint()
                    onPaint: {
                        const c = getContext("2d")
                        c.reset()
                        c.lineWidth = 4
                        c.strokeStyle = "rgba(130,170,255,0.15)"
                        c.beginPath(); c.arc(23, 23, 19, 0, Math.PI * 2); c.stroke()
                        c.strokeStyle = tint
                        c.beginPath(); c.arc(23, 23, 19, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * score / 100); c.stroke()
                    }
                    Text {
                        anchors.centerIn: parent
                        text: ring.score
                        color: ring.tint
                        font.family: Theme.mono
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3
                    Text {
                        Layout.fillWidth: true
                        text: row.modelData.hook || ""
                        wrapMode: Text.WordWrap
                        color: Theme.text
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                    }
                    Text {
                        Layout.fillWidth: true
                        text: `${Store.fmt(row.modelData.start)} → ${Store.fmt(row.modelData.end)} · `
                              + `${(row.modelData.end - row.modelData.start).toFixed(0)}s · ${(row.modelData.why || []).join(" · ")}`
                        wrapMode: Text.WordWrap
                        color: Theme.muted
                        font.family: Theme.mono
                        font.pixelSize: 11
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: !!row.modelData.post_caption
                        text: row.modelData.post_caption || ""
                        wrapMode: Text.WordWrap
                        color: Theme.dim
                        font.pixelSize: 12
                    }
                }
                NeonButton {
                    small: true
                    iconText: Theme.icPlay
                    text: "Preview"
                    onClicked: { Store.previewMoment(row.modelData); dlg.close() }
                }
                NeonButton {
                    small: true
                    primary: !row.added
                    text: row.added ? "Added" : "Add"
                    enabled: !row.added
                    onClicked: Store.addMoments([row.modelData], [row.index])
                }
            }
        }
    }
}
