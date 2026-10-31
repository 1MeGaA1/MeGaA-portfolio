import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Clip tab: name, in / out, layout + framing, speaker switches, hook text and look, post caption.
ScrollPane {
    id: tab

    readonly property var hs: Store.effectiveHook()
    readonly property var lim: Store.zoomLimits[Store.layout]
    readonly property var len: Store.lengthInfo()   // re-evaluates on range / edit changes (editKey)

    component TimeBox: NeonField {
        id: box
        property var value: null
        property string key: "I"
        readonly property string shown: value === null || value === undefined ? "" : Store.fmt(value)
        signal commit(real t)
        signal mark()
        mono: true
        implicitHeight: 34
        rightPadding: 38
        placeholderText: "0:00.0"
        text: shown
        onTextEdited: bad = false
        // the range was set from outside the boxes: show it, without the red of an old typed time (web: setRange)
        function reset() {
            bad = false
            text = Qt.binding(() => box.shown)
        }
        // a typed time sets the range and moves the preview there (web: change on #f-in / #f-out);
        // the shown time typed again keeps the exact edge (0.1 s rounded on screen)
        onEditingFinished: {
            if (text === shown) return
            const t = Store.parseTime(text)
            bad = t === null
            if (t === null) return
            commit(t)
            Store.seekRequested(t)
            reset()
        }
        Rectangle {
            anchors.right: parent.right
            anchors.rightMargin: 4
            anchors.verticalCenter: parent.verticalCenter
            width: 28; height: 26; radius: 7
            color: markArea.containsMouse ? Theme.cyanSoft : Theme.raised
            border.color: markArea.containsMouse ? Qt.rgba(0, 229 / 255, 1, 0.5) : Theme.line2
            Text { anchors.centerIn: parent; text: box.key; color: Theme.cyan; font.family: Theme.mono; font.pixelSize: 11; font.bold: true }
            MouseArea {
                id: markArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: { Store.releaseFocus(); box.mark() }
            }
            ToolTip.visible: markArea.containsMouse
            ToolTip.delay: 400
            ToolTip.text: box.key === "I" ? "Start at the playhead (I)" : "End at the playhead (O)"
        }
    }

    component Labeled: RowLayout {
        property string label: ""
        property string value: ""
        default property alias inner: holder.data
        spacing: 10
        Text { text: parent.label; color: Theme.muted; font.pixelSize: 12; Layout.preferredWidth: 48 }
        Item { id: holder; Layout.fillWidth: true; implicitHeight: 22 }
        Text { text: parent.value; color: Theme.dim; font.family: Theme.mono; font.pixelSize: 11; Layout.preferredWidth: 40; horizontalAlignment: Text.AlignRight }
    }

    // the campaign's rules, checked live on this clip (web pro.js #rule-box)
    Rectangle {
        id: ruleBox
        readonly property var checks: Store.currentCampaign ? Store.liveChecks() : null
        readonly property bool bad: !!checks && checks.some(c => c.level === "error")
        readonly property color tint: !checks ? Theme.muted : bad ? Theme.bad : checks.length ? Theme.warn : Theme.ok
        visible: !!checks
        Layout.fillWidth: true
        implicitHeight: ruleCol.implicitHeight + 20
        radius: 12
        color: Qt.rgba(tint.r, tint.g, tint.b, 0.06)
        border.color: Qt.rgba(tint.r, tint.g, tint.b, 0.4)
        Column {
            id: ruleCol
            x: 12
            y: 10
            width: parent.width - 24
            spacing: 5
            FieldLabel { label: Store.currentCampaign ? Store.currentCampaign.name : "" }
            Repeater {
                model: ruleBox.checks || []
                Text {
                    required property var modelData
                    width: ruleCol.width
                    text: (modelData.level === "error" ? "✕  " : "!  ") + modelData.text
                    wrapMode: Text.WordWrap
                    color: modelData.level === "error" ? Theme.bad : Theme.warn
                    font.pixelSize: 12
                }
            }
            Text {
                visible: !!ruleBox.checks && !ruleBox.checks.length
                text: "✓  Fits all the campaign rules"
                color: Theme.ok
                font.pixelSize: 12
            }
        }
    }

    // name
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 7
        FieldLabel { label: "Name" }
        NeonField {
            Layout.fillWidth: true
            text: Store.clipName
            onTextEdited: Store.clipName = text
        }
    }

    // I / O, a line pick, the strip, a clip load or New set the range – also to the same times: both boxes show it
    // again (web: setRange). A typed time sets it fromInputs: the other box keeps its text
    Connections {
        target: Store
        function onRangeSet() { inBox.reset(); outBox.reset() }
    }

    // in / out
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 7
        FieldLabel { label: "In / Out" }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            TimeBox {
                id: inBox
                Layout.fillWidth: true
                value: Store.inT
                key: "I"
                onCommit: (t) => Store.setRange(t, Store.outT, true)
                onMark: Store.setIn()
            }
            Text { text: "→"; color: Theme.dim; font.pixelSize: 14 }
            TimeBox {
                id: outBox
                Layout.fillWidth: true
                value: Store.outT
                key: "O"
                onCommit: (t) => Store.setRange(Store.inT, t, true)
                onMark: Store.setOut()
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Text {
                text: tab.len.text
                color: tab.len.level === "ok" ? Theme.cyan : tab.len.level === "warn" ? Theme.warn
                     : tab.len.level === "bad" ? Theme.bad : Theme.dim
                font.family: Theme.mono
                font.pixelSize: 15
                font.bold: true
            }
            Text {
                Layout.fillWidth: true
                text: tab.len.clipHint
                color: Theme.muted
                font.pixelSize: 12
                elide: Text.ElideRight
            }
        }
    }

    // layout + framing
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 9
        FieldLabel { label: "Layout" }
        Segmented {
            Layout.fillWidth: true
            model: [{ value: "crop", label: "Crop" }, { value: "fit", label: "Fit + blur" }]
            current: Store.layout
            onPicked: (value) => Store.setLayout(value)
        }
        Labeled {
            Layout.fillWidth: true
            label: "Zoom"
            value: `${Math.round(Store.frameZoom * 100)}%`
            NeonSlider {
                anchors.fill: parent
                from: tab.lim[0] * 100
                to: tab.lim[1] * 100
                stepSize: 5
                value: Store.frameZoom * 100
                onMoved: Store.setFrameZoom(value / 100)
            }
        }
        Labeled {
            Layout.fillWidth: true
            label: "Left/right"
            value: `${Math.round(Store.cropX * 100)}%`
            NeonSlider {
                anchors.fill: parent
                from: 0
                to: 1
                value: Store.cropX
                onMoved: Store.cropX = Store.round(value, 3)
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: "Scroll on the preview to zoom · drag it to move the video"
                wrapMode: Text.WordWrap
                color: Theme.dim
                font.pixelSize: 11
            }
            NeonButton {
                small: true
                text: "Reset"
                onClicked: { Store.setFrameZoom(1); Store.cropX = 0.5; Store.frameY = 0.5 }
            }
        }
    }

    // speaker switches (web: right after the crop field, ui/pro.js 519)
    SpeakerSwitches { Layout.fillWidth: true }

    // hook
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 9
        FieldLabel { label: "Hook"; note: "text on top" }
        NeonArea {
            Layout.fillWidth: true
            placeholderText: "Nobody tells you this about money…"
            text: Store.hookText
            onTextChanged: if (text !== Store.hookText) Store.hookText = text
        }
        GridLayout {
            Layout.fillWidth: true
            columns: 4
            columnSpacing: 5
            rowSpacing: 5
            Repeater {
                model: Store.hookOrder
                HookTile {
                    required property string modelData
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    hs: Store.hooks[modelData]
                    on: Store.hook.style === modelData
                    onClicked: Store.setHook({ style: modelData })
                }
            }
        }
        Labeled {
            Layout.fillWidth: true
            label: "Size"
            value: `${Store.hook.size}%`
            NeonSlider {
                anchors.fill: parent
                from: 60; to: 180; stepSize: 5
                value: Store.hook.size
                onMoved: Store.setHook({ size: Math.round(value) })
            }
        }
        Labeled {
            Layout.fillWidth: true
            label: "Height"
            value: tab.hs ? `${Math.round(tab.hs.margin_v / 1920 * 100)}%` : ""
            NeonSlider {
                anchors.fill: parent
                from: 40; to: 1500; stepSize: 10
                value: tab.hs ? tab.hs.margin_v : 230
                onMoved: Store.setHook({ pos: Math.round(value) })
            }
        }
        Segmented {
            Layout.fillWidth: true
            buttonHeight: 28
            model: [{ value: 0, label: "Whole" }, { value: 3, label: "3 s" }, { value: 5, label: "5 s" }, { value: 8, label: "8 s" }]
            current: Store.hook.duration
            onPicked: (value) => Store.setHook({ duration: value })
            ToolTip.visible: hoverHook.hovered
            ToolTip.delay: 600
            ToolTip.text: "How long the hook stays on screen"
            HoverHandler { id: hoverHook }
        }
        NeonButton {
            small: true
            text: "Hook look → all clips"
            onClicked: Store.applyToAll(Store.hookFields(), "Hook look")
        }
    }

    // post caption
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 7
        FieldLabel { label: "Post caption"; note: "for TikTok / Reels" }
        NeonArea {
            Layout.fillWidth: true
            placeholderText: "Pay yourself first #money #finance"
            text: Store.postText
            onTextChanged: if (text !== Store.postText) Store.postText = text
        }
    }
}
