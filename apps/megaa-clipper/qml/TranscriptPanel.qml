import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// The transcript: click a line to start a clip, shift+click to end it, double-click to play.
// With the cut / mute tool (or teaser picking) on, clicks go to single words instead.
Panel {
    id: tp
    title: "Transcript"
    tag: Store.lines.length && width >= 520 ? `${Store.lines.length} lines` : ""   // a narrow header keeps the tools

    // which word tool is on: "cut", "mute", "teaser" or ""
    readonly property string tool: Store.cutMode ? "cut" : Store.muteMode ? "mute" : Store.teaserPick ? "teaser" : ""
    // web: body.cut-mode / mute-mode / teaser-pick .panel.transcript { border-color }
    border.color: tool === "cut" ? Qt.rgba(1, 43 / 255, 214 / 255, 0.45)
                : tool === "mute" ? Qt.rgba(139 / 255, 92 / 255, 1, 0.55)
                : tool === "teaser" ? Qt.rgba(1, 181 / 255, 71 / 255, 0.5) : Theme.line
    // web: body.<mode> .line .w:hover { background }
    readonly property color hoverTint: tool === "cut" ? Qt.rgba(1, 77 / 255, 109 / 255, 0.22)
                                     : tool === "mute" ? Qt.rgba(139 / 255, 92 / 255, 1, 0.25)
                                     : Qt.rgba(1, 181 / 255, 71 / 255, 0.3)
    property var hits: []
    property int hitIndex: -1
    property int editingLine: -1
    property int scrollTarget: -1   // the line the running scroll animation is bringing into view
    property int settles: 0         // short glides left that put it exactly in the middle
    property int keepTop: -1        // the top line (and how far it was scrolled) while the transcript reloads
    property real keepOffset: 0

    readonly property var languages: [
        { value: "en", label: "English" }, { value: "auto", label: "Auto detect" }, { value: "ar", label: "Arabic" },
        { value: "es", label: "Spanish" }, { value: "fr", label: "French" }, { value: "de", label: "German" },
        { value: "pt", label: "Portuguese" }, { value: "it", label: "Italian" }, { value: "tr", label: "Turkish" },
        { value: "hi", label: "Hindi" }, { value: "ja", label: "Japanese" }, { value: "ko", label: "Korean" },
        { value: "zh", label: "Chinese" }]

    function updateHits() {
        const query = Store.search.trim().toLowerCase()
        const found = []
        if (query) Store.lines.forEach((line, i) => { if (line.text.toLowerCase().includes(query)) found.push(i) })
        hits = found
        hitIndex = -1
    }

    // web nextHit: the found line becomes the clip (and the Shift+click anchor) and the preview jumps there
    function nextHit(step) {
        if (!hits.length) return
        hitIndex = (hitIndex + step + hits.length) % hits.length
        const i = hits[hitIndex]
        scrollTo(i)
        Store.anchorLine = i
        Store.pickLines(i, i)
        Store.seekRequested(Store.lines[i].s)
    }

    // smooth scroll so line i sits in the middle. positionViewAtIndex lays out the rows around line i with
    // their real heights; a far jump glides only the last 3/4 of a view, over rows that are laid out (rows
    // far away only have estimated heights - lines wrap - so a long glide would end on another line)
    function scrollTo(i) {
        const before = list.contentY
        list.positionViewAtIndex(i, ListView.Center)
        const after = list.contentY
        if (Math.abs(after - before) < 1) return
        const span = list.height * 0.75
        list.contentY = Math.abs(after - before) > span ? after + (before < after ? -span : span) : before
        scrollTarget = i
        settles = 2
        scrollAnim.duration = 280
        scrollAnim.to = after
        scrollAnim.restart()
    }

    // after a glide: rows laid out on the way can have moved the line, so a short glide centres it (web: block center)
    function settle() {
        const i = scrollTarget
        if (i < 0 || scrollAnim.running) return
        const item = list.itemAtIndex(i)
        if (!item) { list.positionViewAtIndex(i, ListView.Center); return }
        const lowest = list.originY - list.topMargin, highest = list.originY + list.contentHeight + list.bottomMargin - list.height
        const want = Math.max(lowest, Math.min(item.y + item.height / 2 - list.height / 2, Math.max(lowest, highest)))
        if (Math.abs(want - list.contentY) < 2) return
        if (settles-- <= 0) { list.positionViewAtIndex(i, ListView.Center); return }
        scrollAnim.duration = 160
        scrollAnim.to = want
        scrollAnim.restart()
    }

    function isVisible(i) {
        const item = list.itemAtIndex(i)
        return item && item.y >= list.contentY + 30 && item.y + item.height <= list.contentY + list.height - 30
    }

    Connections {
        target: Store
        // a new lines array resets the view to the top: the web keeps its scroll position, so put it back
        function onTranscriptReloading() {
            scrollAnim.stop()
            tp.scrollTarget = -1
            tp.keepTop = list.indexAt(10, list.contentY + 1)
            const item = tp.keepTop >= 0 ? list.itemAtIndex(tp.keepTop) : null
            tp.keepOffset = item ? list.contentY - item.y : 0
        }
        function onTranscriptVersionChanged() {
            tp.updateHits()
            if (tp.keepTop < 0) return
            const top = Math.min(tp.keepTop, Store.lines.length - 1)
            tp.keepTop = -1
            if (top < 0) return
            list.positionViewAtIndex(top, ListView.Beginning)
            const item = list.itemAtIndex(top)
            if (!item) return
            const lowest = list.originY - list.topMargin, highest = list.originY + list.contentHeight + list.bottomMargin - list.height
            list.contentY = Math.max(lowest, Math.min(item.y + tp.keepOffset, Math.max(lowest, highest)))
        }
        function onSearchChanged() { tp.updateHits() }
        // the box is hidden without a transcript: a hidden box would take every key
        function onSearchRequested() { if (!search.visible) return; search.forceActiveFocus(); search.selectAll() }
        function onLiveLineChanged() {
            // a line being fixed stays where it is (scrolling it away would end the edit)
            if (follow.checked && Store.playing && Store.liveLine >= 0 && tp.editingLine < 0 && !tp.isVisible(Store.liveLine))
                tp.scrollTo(Store.liveLine)
        }
        function onShowLine(i) { if (!tp.isVisible(i)) tp.scrollTo(i) }
    }

    header: [
        IconButton {
            visible: Store.lines.length > 0
            glyph: Theme.icStar
            ToolTip.text: "Viral moments: find the best clips in this video"
            onClicked: { Store.releaseFocus(); Store.dialogRequested("moments") }
        },
        NeonField {
            id: search
            visible: Store.lines.length > 0
            // shrinks first when the panel is narrow (web: 230 px, 170 px at 1350 px and less, then flex-shrinks)
            Layout.fillWidth: true
            Layout.preferredWidth: 200
            Layout.maximumWidth: 200
            Layout.minimumWidth: 90
            implicitHeight: 32
            leftPadding: 30
            placeholderText: "Search words…"
            onTextChanged: Store.search = text
            Keys.onReturnPressed: (event) => tp.nextHit(event.modifiers & Qt.ShiftModifier ? -1 : 1)
            Keys.onEnterPressed: (event) => tp.nextHit(event.modifiers & Qt.ShiftModifier ? -1 : 1)
            Text {
                x: 10
                anchors.verticalCenter: parent.verticalCenter
                text: Theme.icSearch
                font.family: Theme.icons
                font.pixelSize: 12
                color: Theme.dim
            }
            Text {
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                visible: Store.search.trim() !== ""
                text: tp.hitIndex >= 0 ? `${tp.hitIndex + 1}/${tp.hits.length}` : `${tp.hits.length}`
                color: tp.hits.length ? Theme.cyan : Theme.bad
                font.family: Theme.mono
                font.pixelSize: 11
            }
        },
        IconButton {
            visible: Store.lines.length > 0
            glyph: Theme.icCut
            active: Store.cutMode
            ToolTip.text: "Cut tool: click words to remove them from the clip (X)"
            onClicked: { Store.releaseFocus(); Store.setCutMode(!Store.cutMode) }
        },
        IconButton {
            visible: Store.lines.length > 0
            glyph: Theme.icMute
            active: Store.muteMode
            activeColor: Theme.violet
            activeText: "#ffffff"
            activeFill: 0.18
            activeGlow: 0.35
            ToolTip.text: "Mute tool: click words to silence or bleep them (M)"
            onClicked: { Store.releaseFocus(); Store.setMuteMode(!Store.muteMode) }
        },
        IconButton {
            visible: Store.lines.length > 0
            glyph: Theme.icRefresh
            enabled: !Store.busy
            ToolTip.text: "Transcribe again"
            onClicked: { Store.releaseFocus(); retranscribeAsk.open() }
        }
    ]

    // web: confirm() before the transcript (and every caption fix in it) is replaced
    Popup {
        id: retranscribeAsk
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 400
        modal: true
        focus: true
        padding: 22
        background: Rectangle { radius: 16; color: Theme.panelSolid; border.color: Theme.line2 }
        Overlay.modal: Rectangle { color: Qt.rgba(2 / 255, 4 / 255, 8 / 255, 0.6) }
        function accept() { close(); Store.transcribe(lang.currentValue || "en") }
        contentItem: ColumnLayout {
            spacing: 12
            focus: true
            Keys.onReturnPressed: retranscribeAsk.accept()
            Keys.onEnterPressed: retranscribeAsk.accept()
            Text {
                text: "Transcribe again?"
                color: Theme.text
                font.family: Theme.display
                font.pixelSize: 16
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: "Transcribe this video again? The current transcript will be replaced, and the caption text you fixed goes with it."
                wrapMode: Text.WordWrap
                color: Theme.muted
                font.pixelSize: 13
                lineHeight: 1.2
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 8
                spacing: 10
                Item { Layout.fillWidth: true }
                NeonButton { text: "Cancel"; onClicked: retranscribeAsk.close() }
                NeonButton { primary: true; text: "Transcribe"; onClicked: retranscribeAsk.accept() }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: Store.lines.length > 0
            clip: true
            model: Store.lines
            boundsBehavior: Flickable.StopAtBounds
            topMargin: 6
            bottomMargin: 6
            reuseItems: true
            ScrollBar.vertical: NeonScrollBar {}
            NumberAnimation {
                id: scrollAnim
                target: list
                property: "contentY"
                duration: 280
                easing.type: Easing.OutCubic
                onFinished: Qt.callLater(tp.settle)   // only after a glide that ran to its end
            }
            // a scroll by the user ends the glide (and the settling)
            onMovementStarted: { scrollAnim.stop(); tp.scrollTarget = -1 }

            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                readonly property bool selected: Store.lineSelected(index)
                readonly property bool live: Store.liveLine === index
                readonly property bool queued: Store.lineQueued(index)
                readonly property bool current: tp.hitIndex >= 0 && tp.hits[tp.hitIndex] === index
                readonly property bool editing: tp.editingLine === index
                // first / count come from one binding: a reused row must never see a new first with an old end
                readonly property var range: Store.lineWords[index] || [0, 0]
                readonly property int first: range[0]
                readonly property int count: range[1] - range[0]
                readonly property bool rtl: Store.isRtl(modelData.text)
                property int hoverWord: -1        // the word under the mouse (tinted while a word tool is on)
                ListView.onReused: hoverWord = -1
                // the row of the line being fixed scrolled far away: its delegate goes to the pool and comes back
                // as another line, so the edit ends (like the web's blur) instead of moving to that line
                ListView.onPooled: if (row.editing) tp.editingLine = -1

                // the word under a point of the row's mouse area, or -1
                function wordAt(x, y) {
                    if (!count) return -1
                    const p = area.mapToItem(flow, x, y)
                    const chip = flow.childAt(p.x, p.y)
                    return chip && chip.wi !== undefined ? chip.wi : -1
                }

                width: ListView.view.width
                height: Math.max(38, (count ? flow.implicitHeight : plain.implicitHeight) + 16,
                                 editor.visible ? editor.implicitHeight + 14 : 0)
                color: editing ? Theme.raised : selected ? Qt.rgba(0, 229 / 255, 1, 0.08)
                     : current ? Qt.rgba(1, 181 / 255, 71 / 255, 0.10)
                     : area.containsMouse ? Qt.rgba(130 / 255, 170 / 255, 1, 0.05) : "transparent"

                // selection bar on the left, magenta while this line is playing
                Rectangle {
                    width: 3
                    height: parent.height - 8
                    anchors.verticalCenter: parent.verticalCenter
                    x: 4
                    radius: 2
                    visible: row.selected || row.live
                    color: row.live ? Theme.magenta : Theme.cyan
                }

                Text {
                    id: time
                    x: 16
                    y: 10
                    width: 58
                    text: Store.fmt(modelData.s)
                    color: row.live ? Theme.magenta : row.selected ? Theme.cyan : Theme.dim
                    font.family: Theme.mono
                    font.pixelSize: 11
                }
                // the words, each one clickable; a line without word timings shows its text
                Flow {
                    id: flow
                    visible: !row.editing && row.count > 0
                    anchors.left: time.right
                    anchors.right: parent.right
                    anchors.rightMargin: 40
                    y: 8
                    spacing: 4
                    layoutDirection: row.rtl ? Qt.RightToLeft : Qt.LeftToRight
                    Repeater {
                        model: row.count
                        TranscriptWord {
                            required property int index
                            wi: row.first + index
                            text: { const w = Store.words[row.first + index]; return w ? w.w : "" }   // stale while a transcript reloads
                            hot: tp.tool !== "" && row.hoverWord === wi
                            hoverTint: tp.hoverTint
                            base: row.selected || row.live ? Theme.text : "#b9c6de"
                        }
                    }
                }
                Text {
                    id: plain
                    visible: !row.editing && row.count === 0
                    anchors.left: time.right
                    anchors.right: parent.right
                    anchors.rightMargin: 40
                    y: 8
                    text: row.modelData.text
                    wrapMode: Text.WordWrap
                    color: row.selected || row.live ? Theme.text : "#b9c6de"
                    font.pixelSize: 14
                    lineHeight: 1.15
                }
                NeonField {
                    id: editor
                    visible: row.editing
                    anchors.left: time.right
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    implicitHeight: 32
                    property int line: -1   // the line this edit belongs to (row.index changes when the row is reused)
                    onVisibleChanged: {
                        if (visible) {
                            line = row.index
                            text = Store.lineText(row.index)
                            forceActiveFocus()
                            selectAll()
                        } else if (activeFocus) {   // the row was reused for another line: end the edit, free the keys
                            if (tp.editingLine === line) tp.editingLine = -1
                            Store.releaseFocus()
                        }
                    }
                    // the text goes to the line the edit was opened on, never to whatever line the row shows now
                    function commit() {
                        const i = line
                        if (!row.editing || i !== row.index) return
                        const fixed = text.replace(/\s+/g, " ").trim()
                        tp.editingLine = -1
                        Store.releaseFocus()
                        if (fixed !== Store.lineText(i)) Store.editLine(i, fixed)
                    }
                    Keys.onReturnPressed: commit()
                    Keys.onEnterPressed: commit()
                    Keys.onEscapePressed: { tp.editingLine = -1; Store.releaseFocus() }
                    onActiveFocusChanged: if (!activeFocus && row.editing) tp.editingLine = -1
                }

                // violet dot: this line is already in a queued clip
                Rectangle {
                    visible: row.queued && !row.editing
                    width: 6; height: 6; radius: 3
                    color: Theme.violet
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    y: 15
                }

                MouseArea {
                    id: area
                    anchors.fill: parent
                    enabled: !row.editing
                    hoverEnabled: true
                    // web: .line { cursor: pointer } beats the tools' cursors, so it is a hand in every mode
                    cursorShape: Qt.PointingHandCursor
                    // tracked in every mode, so a tool switched on by key tints the word under a resting mouse
                    onPositionChanged: (mouse) => row.hoverWord = row.wordAt(mouse.x, mouse.y)
                    onExited: row.hoverWord = -1

                    // word tools: a click on a word goes to the tool, a click beside the words does nothing
                    function toolClick(mouse) {
                        const wi = row.wordAt(mouse.x, mouse.y)
                        if (wi < 0) return
                        if (Store.teaserPick) Store.clickTeaserWord(wi)
                        else Store.clickToolWord(Store.cutMode ? "cuts" : "mutes", wi, (mouse.modifiers & Qt.ShiftModifier) !== 0)
                    }

                    onClicked: (mouse) => {
                        Store.releaseFocus()
                        if (tp.tool) { toolClick(mouse); return }
                        if ((mouse.modifiers & Qt.ShiftModifier) && Store.anchorLine >= 0 && Store.anchorLine < Store.lines.length) {
                            Store.pickLines(Math.min(Store.anchorLine, row.index), Math.max(Store.anchorLine, row.index))
                        } else {
                            Store.anchorLine = row.index
                            Store.pickLines(row.index, row.index)
                            Store.seekRequested(row.modelData.s)
                        }
                    }
                    onDoubleClicked: (mouse) => {
                        // the browser sends two clicks before a dblclick: the second one goes to the tool too
                        if (tp.tool) { toolClick(mouse); return }
                        Store.seekRequested(row.modelData.s)
                        Store.playRequested()
                    }
                }

                IconButton {
                    visible: area.containsMouse && !row.editing && !Store.cutMode && !Store.muteMode
                    anchors.right: parent.right
                    anchors.rightMargin: 6
                    y: 4
                    size: 28
                    glyph: Theme.icEdit
                    ToolTip.text: "Fix the caption text"
                    onClicked: tp.editingLine = row.index
                }
            }
        }

        // no transcript yet
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: Store.lines.length === 0

            ColumnLayout {
                anchors.centerIn: parent
                width: Math.min(parent.width - 60, 330)
                spacing: 12
                visible: !!Store.video

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: 64; Layout.preferredHeight: 64
                    radius: 32
                    color: Theme.cyanSoft
                    border.color: Qt.rgba(0, 229 / 255, 1, 0.4)
                    Text {
                        anchors.centerIn: parent
                        text: Theme.icMic
                        font.family: Theme.icons
                        font.pixelSize: 24
                        color: Theme.cyan
                    }
                }
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "No transcript yet"
                    color: Theme.text
                    font.family: Theme.display
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: "Turn the speech into text with word timings, then pick your moments."
                    color: Theme.muted
                    font.pixelSize: 13
                }
                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 6
                    spacing: 8
                    NeonCombo {
                        id: lang
                        Layout.preferredWidth: 140
                        model: tp.languages
                    }
                    NeonButton {
                        Layout.fillWidth: true
                        primary: true
                        enabled: !Store.busy
                        text: Store.job.running && Store.job.kind === "transcribe" ? `Transcribing ${Store.job.progress}%` : "Transcribe"
                        onClicked: Store.transcribe(lang.currentValue || "en")
                    }
                }
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            Layout.leftMargin: 16
            Layout.rightMargin: 12
            spacing: 14
            // key hints: in a narrow panel the last ones are left out, Follow keeps its place
            Item {
                id: hintBox
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                implicitHeight: hints.implicitHeight
                Row {
                    id: hints
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 14
                    Repeater {
                        model: [["Click", "start"], ["Shift+Click", "end"], ["Dbl-click", "play"], ["/", "search"]]
                        Row {
                            required property var modelData
                            spacing: 6
                            visible: modelData[0] !== "/" || Store.lines.length > 0   // '/' does nothing without a transcript
                            opacity: x + width <= hintBox.width ? 1 : 0   // not visible: hiding would move the others
                            Rectangle {
                                width: key.implicitWidth + 10
                                height: 18
                                radius: 4
                                color: Theme.raised
                                border.color: Theme.line2
                                anchors.verticalCenter: parent.verticalCenter
                                Text { id: key; anchors.centerIn: parent; text: modelData[0]; color: Theme.muted; font.family: Theme.mono; font.pixelSize: 10 }
                            }
                            Text { text: modelData[1]; color: Theme.dim; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        }
                    }
                }
            }
            NeonSwitch { id: follow; text: "Follow"; checked: true }
        }
    }
}
