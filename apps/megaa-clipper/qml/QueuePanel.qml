import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// The clips of this video, left to right; click a card to edit that clip.
Panel {
    id: queue
    title: "Queue"
    tag: `${Store.clips.length}`

    readonly property var stateLabel: ({ new: "Not rendered", queued: "Queued", ready: "Ready", error: "Error" })

    component Pill: Rectangle {
        property string text: ""
        property color tint: Theme.muted
        implicitWidth: pillText.implicitWidth + 14
        implicitHeight: 19
        radius: 6
        color: Qt.rgba(tint.r, tint.g, tint.b, 0.12)
        border.color: Qt.rgba(tint.r, tint.g, tint.b, 0.35)
        Text {
            id: pillText
            anchors.centerIn: parent
            text: parent.text
            color: parent.tint
            font.family: Theme.mono
            font.pixelSize: 10
            font.capitalization: Font.AllUppercase
        }
    }

    // same rule as the web edition's isEdited (a teaser or mutes get pills of their own)
    function isEdited(c) { return (c.cuts && c.cuts.length) || (c.drops && c.drops.length) || c.remove_pauses || c.zoom || (c.speed && c.speed !== 1) }

    header: [
        NeonButton {
            small: true
            text: "Export pack"
            iconText: Theme.icPackage
            enabled: Store.clips.some(c => c.status && c.status.state === "ready")
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: "Copy every rendered clip + captions.txt into one folder"
            onClicked: Store.exportPack(false)
        },
        NeonButton {
            small: true
            text: "ZIP"
            enabled: Store.clips.some(c => c.status && c.status.state === "ready")
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: "The same, as one ZIP file"
            onClicked: Store.exportPack(true)
        },
        NeonButton {
            small: true
            text: "Open folder"
            iconText: Theme.icFolder
            enabled: !!Store.video
            onClicked: backend.openOutput()
        },
        NeonButton {
            small: true
            primary: true
            text: "Render all"
            enabled: !Store.busy && Store.clips.length > 0
            onClicked: Store.renderSome(Store.clips)
        }
    ]

    Text {
        anchors.centerIn: parent
        visible: Store.clips.length === 0
        text: "NO CLIPS YET  ·  PICK A MOMENT, THEN “ADD TO QUEUE”"
        color: Theme.dim
        font.family: Theme.mono
        font.pixelSize: 12
        font.letterSpacing: 1.4
    }

    ListView {
        id: cards
        anchors.fill: parent
        anchors.margins: 12
        anchors.bottomMargin: 8
        orientation: ListView.Horizontal
        spacing: 12
        clip: true
        model: Store.clips
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.horizontal: NeonScrollBar {}

        delegate: Rectangle {
            id: card
            required property var modelData
            readonly property var cl: modelData
            readonly property var st: cl.status || { state: "new" }
            readonly property bool ready: st.state === "ready"
            readonly property bool editing: cl.name === Store.editing

            width: 286
            height: ListView.view.height - 10
            radius: 12
            border.width: editing ? 1.5 : 1
            border.color: editing ? Theme.cyan : cardArea.containsMouse ? Qt.rgba(0, 229 / 255, 1, 0.45) : Theme.line2
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.rgba(20 / 255, 30 / 255, 50 / 255, 0.95) }
                GradientStop { position: 1; color: Qt.rgba(10 / 255, 15 / 255, 26 / 255, 0.95) }
            }
            clip: true

            MouseArea {
                id: cardArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: { Store.releaseFocus(); Store.applyClip(card.cl) }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                anchors.topMargin: 10
                anchors.bottomMargin: 8
                spacing: 6

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text {
                        Layout.fillWidth: true
                        text: card.cl.name
                        elide: Text.ElideRight
                        color: Theme.text
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                    // the campaign's rules this clip breaks (red: an error, amber: only warnings)
                    Pill {
                        id: rulePill
                        readonly property var checks: card.cl.checks || []
                        visible: checks.length > 0
                        text: `⚠ ${checks.length}`
                        tint: checks.some(x => x.level === "error") ? Theme.bad : Theme.warn
                        MouseArea { id: ruleHover; anchors.fill: parent; hoverEnabled: true }
                        ToolTip.visible: ruleHover.containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: rulePill.checks.map(x => x.text).join(String.fromCharCode(10))
                    }
                    Pill {
                        text: card.st.state === "rendering" ? `Rendering ${card.st.progress || 0}%` : (queue.stateLabel[card.st.state] || card.st.state)
                        tint: card.st.state === "ready" ? Theme.ok : card.st.state === "error" ? Theme.bad
                            : card.st.state === "rendering" || card.st.state === "queued" ? Theme.cyan : Theme.muted
                    }
                }
                Text {
                    // the finished length (edits, deleted parts and speed included), else the range's
                    text: `${Store.fmt(card.cl.start)} → ${Store.fmt(card.cl.end)}  ·  ${(typeof card.st.length === "number" ? card.st.length : card.cl.end - card.cl.start).toFixed(1)}s`
                    color: Theme.muted
                    font.family: Theme.mono
                    font.pixelSize: 11
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 5
                    Pill { text: card.cl.layout || "crop"; tint: Theme.cyan }
                    Pill {
                        text: card.cl.captions === false ? "no captions"
                            : (Store.styles[card.cl.caption_style] ? Store.styles[card.cl.caption_style].label : "Classic")
                        tint: Theme.magenta
                    }
                    Pill { visible: !!queue.isEdited(card.cl); text: "edited"; tint: Theme.cyan }
                    Pill { visible: card.cl.intro_start !== undefined && card.cl.intro_start !== null; text: "teaser"; tint: Theme.warn }
                    Pill { visible: !!(card.cl.mutes && card.cl.mutes.length); text: "muted"; tint: Theme.violet }
                }
                Text {
                    // takes only the room left over, so many tags never push the buttons off the card
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredHeight: 0
                    Layout.minimumHeight: 0
                    clip: true
                    text: card.cl.hook || "No hook text"
                    color: card.cl.hook ? "#b9c6de" : Theme.dim
                    font.italic: !card.cl.hook
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                    elide: Text.ElideRight
                    maximumLineCount: height >= 32 ? 2 : 1
                    opacity: height >= 15 ? 1 : 0
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    IconButton {
                        glyph: Theme.icPlay
                        size: 30
                        enabled: card.ready
                        ToolTip.text: "Watch the rendered clip"
                        onClicked: Store.playClip(card.cl)
                    }
                    IconButton {
                        glyph: Theme.icRender
                        size: 30
                        enabled: !Store.busy
                        ToolTip.text: "Render this clip"
                        onClicked: Store.renderSome([card.cl])
                    }
                    IconButton {
                        glyph: Theme.icFolder
                        size: 30
                        enabled: card.ready
                        ToolTip.text: "Show in folder"
                        onClicked: backend.reveal(card.cl.name)
                    }
                    IconButton {
                        glyph: Theme.icCheck
                        size: 30
                        enabled: card.ready
                        ToolTip.text: "Mark as posted (earnings tracker)"
                        onClicked: Store.askPosted(card.cl)
                    }
                    Item { Layout.fillWidth: true }
                    IconButton {
                        glyph: Theme.icDelete
                        size: 30
                        danger: true
                        ToolTip.text: "Remove from queue"
                        onClicked: Store.deleteClip(card.cl.name)
                    }
                }
            }

            // render progress along the bottom
            Rectangle {
                visible: card.st.state === "rendering"
                anchors.left: parent.left
                anchors.bottom: parent.bottom
                height: 3
                width: parent.width * (card.st.progress || 0) / 100
                color: Theme.cyan
                Behavior on width { NumberAnimation { duration: 300 } }
            }

            ToolTip.visible: cardArea.containsMouse && !!card.st.error
            ToolTip.delay: 500
            ToolTip.text: card.st.error || ""
        }
    }
}
