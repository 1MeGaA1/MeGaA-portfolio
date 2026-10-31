import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Edit tab: final length, teaser, pauses, cut / mute words, punch-ins, speed, progress bar, music, pop-ups and
// watermark – the settings the engine applies when it renders the clip (same order as the web edition).
ScrollPane {
    id: tab

    readonly property var len: Store.lengthInfo()   // re-evaluates on range / edit changes (editKey)

    // hint · control · value in one row (web: .sub-row)
    component SubRow: RowLayout {
        property string label: ""
        property string value: ""
        default property alias inner: holder.data
        spacing: 10
        Text { text: parent.label; color: Theme.dim; font.pixelSize: 11 }
        Item { id: holder; Layout.fillWidth: true; implicitHeight: 22 }
        Text { text: parent.value; color: Theme.dim; font.family: Theme.mono; font.pixelSize: 11; Layout.preferredWidth: 44; horizontalAlignment: Text.AlignRight }
    }

    component Hint: Text {
        wrapMode: Text.WordWrap
        color: Theme.dim
        font.pixelSize: 11
    }

    // a chosen file's name (the whole path on hover), or a dim "none" text (web: .music-name)
    component FileName: Text {
        property string path: ""
        property string none: ""
        text: path ? path.split(/[\\/]/).pop() : none
        color: path ? Theme.text : Theme.dim
        font.pixelSize: 12
        elide: Text.ElideRight
        ToolTip.visible: nameHover.hovered && path !== ""
        ToolTip.text: path
        ToolTip.delay: 500
        HoverHandler { id: nameHover }
    }

    // final length (teaser + edits + speed) – web: updateLength()
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: finalRow.implicitHeight + 20
        radius: 10
        border.color: Qt.rgba(0, 229 / 255, 1, 0.25)
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Qt.rgba(0, 229 / 255, 1, 0.08) }
            GradientStop { position: 1; color: Qt.rgba(139 / 255, 92 / 255, 1, 0.06) }
        }
        RowLayout {
            id: finalRow
            anchors.fill: parent
            anchors.margins: 10
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 10
            FieldLabel { label: "Final length" }
            Text {
                text: tab.len.text
                color: tab.len.level === "warn" ? Theme.warn : tab.len.level === "bad" ? Theme.bad : Theme.cyan
                font.family: Theme.mono
                font.pixelSize: 22
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: tab.len.editHint
                wrapMode: Text.WordWrap
                color: Theme.muted
                font.pixelSize: 12
            }
        }
    }

    // teaser at the start
    TeaserSection { Layout.fillWidth: true }

    // remove pauses
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 7
        NeonSwitch {
            big: true
            text: "Remove pauses"
            checked: Store.edit.removePauses
            onToggled: Store.setEdit({ removePauses: checked })
        }
        SubRow {
            Layout.fillWidth: true
            label: "Silences longer than"
            value: `${Store.edit.pauseMin.toFixed(2).replace(/0$/, "")}s`
            NeonSlider {
                anchors.fill: parent
                from: 20; to: 150; stepSize: 5
                value: Store.edit.pauseMin * 100
                onMoved: Store.setEdit({ pauseMin: Store.round(value / 100, 2) })
            }
        }
    }

    // cut words
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 7
        WordToolRow { Layout.fillWidth: true; list: "cuts" }
        Hint {
            Layout.fillWidth: true
            text: "Turn on the cut tool, then click words in the transcript to remove them (Shift+click for a run of words)."
        }
    }

    // mute words
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 7
        WordToolRow { Layout.fillWidth: true; list: "mutes" }
        Hint { Layout.fillWidth: true; text: "Sound on muted words – click one to hear it" }
        SoundGrid { Layout.fillWidth: true }
        RowLayout {   // the custom sound's file, only while Custom is chosen
            Layout.fillWidth: true
            visible: Store.edit.muteSound === "custom"
            spacing: 10
            FileName { Layout.fillWidth: true; path: Store.edit.muteSfx; none: "No sound file" }
            NeonButton {
                small: true
                text: "Choose file"
                onClicked: { Store.releaseFocus(); Store.pickCustomSound() }
            }
        }
        SubRow {
            Layout.fillWidth: true
            visible: Store.edit.muteSound !== "silence"
            label: "Effect volume"
            value: `${Math.round(Store.edit.muteSfxVolume * 100)}%`
            NeonSlider {
                anchors.fill: parent
                from: 0; to: 150; stepSize: 5
                value: Store.edit.muteSfxVolume * 100
                onMoved: Store.setEdit({ muteSfxVolume: Store.round(value / 100, 2) })
            }
        }
        NeonSwitch {
            text: "Censor captions (f***)"
            checked: Store.edit.muteCaptions
            onToggled: Store.setEdit({ muteCaptions: checked })
        }
        Hint {
            Layout.fillWidth: true
            text: "Turn on the mute tool, then click words in the transcript – the video keeps playing, only the sound goes."
        }
    }

    // zoom punch-ins
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 7
        NeonSwitch {
            big: true
            text: "Zoom punch-ins"
            checked: Store.edit.zoom
            onToggled: Store.setEdit({ zoom: checked })
        }
        SubRow {
            Layout.fillWidth: true
            label: "Amount"
            value: `${Math.round(Store.edit.zoomAmount * 100)}%`
            NeonSlider {
                anchors.fill: parent
                from: 105; to: 140; stepSize: 1
                value: Store.edit.zoomAmount * 100
                onMoved: Store.setEdit({ zoomAmount: Store.round(value / 100, 2) })
            }
        }
    }

    // speed
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 7
        FieldLabel { label: "Speed" }
        Segmented {
            Layout.fillWidth: true
            buttonHeight: 28
            model: Store.speeds.map(v => ({ value: v, label: v + String.fromCharCode(0xD7) }))
            current: Store.edit.speed
            onPicked: (value) => Store.setEdit({ speed: value })
        }
    }

    // progress bar
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 9
        NeonSwitch {
            big: true
            text: "Progress bar"
            checked: Store.edit.progress
            onToggled: Store.setEdit({ progress: checked })
        }
        Swatches {
            Layout.fillWidth: true
            colors: Store.barColors
            current: Store.edit.progressColor
            onPicked: (color) => Store.setEdit({ progressColor: color, progress: true })   // a colour turns the bar on
        }
    }

    // background music
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 7
        FieldLabel { label: "Background music" }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            NeonButton {
                small: true
                iconText: Theme.icMusic
                text: "Choose"
                onClicked: { Store.releaseFocus(); Store.pickMusic() }
            }
            FileName { Layout.fillWidth: true; path: Store.edit.music; none: "No music" }
            IconButton {
                visible: Store.edit.music !== ""
                size: 28
                danger: true
                glyph: Theme.icClose
                ToolTip.text: "Remove music"
                onClicked: { Store.releaseFocus(); Store.clearMusic() }
            }
        }
        SubRow {
            Layout.fillWidth: true
            label: "Volume"
            value: `${Math.round(Store.edit.musicVolume * 100)}%`
            NeonSlider {
                anchors.fill: parent
                from: 0; to: 60; stepSize: 1
                value: Store.edit.musicVolume * 100
                onMoved: Store.setEdit({ musicVolume: Store.round(value / 100, 2) })
            }
        }
        Hint { Layout.fillWidth: true; text: "The music dips automatically while someone is talking." }
    }

    // pop-ups (the web edition puts them right above the watermark)
    PopupsField { Layout.fillWidth: true }

    // watermark
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 7
        FieldLabel { label: "Watermark" }
        NeonField {
            Layout.fillWidth: true
            placeholderText: "@yourhandle"
            maximumLength: 40
            text: Store.edit.watermark
            // typing drops the binding (the stored text is trimmed); leaving the field brings it back
            onTextEdited: { const raw = text; text = raw; Store.setEdit({ watermark: raw.trim() }) }
            onEditingFinished: text = Qt.binding(() => Store.edit.watermark)
        }
        Segmented {
            Layout.fillWidth: true
            buttonHeight: 28
            model: [{ value: "tl", label: String.fromCharCode(0x2196) + " TL" }, { value: "tr", label: String.fromCharCode(0x2197) + " TR" },
                    { value: "bl", label: String.fromCharCode(0x2199) + " BL" }, { value: "br", label: String.fromCharCode(0x2198) + " BR" }]
            current: Store.edit.watermarkPos
            onPicked: (value) => Store.setEdit({ watermarkPos: value })
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 10
        NeonButton {
            small: true
            text: "Apply to all clips"
            ToolTip.visible: hovered
            ToolTip.delay: 600
            ToolTip.text: "Copy these settings (not the cuts) to every clip"
            onClicked: Store.applyEditToAll()
        }
        Hint {
            Layout.fillWidth: true
            text: `Audio is always levelled to ${String.fromCharCode(0x2212)}14 LUFS, the TikTok / Reels / Shorts standard.`
        }
    }
}
