import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import "."

// Edit tab, "Pop-ups" (web: pro.js #pop-field / renderPopups): a picture, GIF or short video shown for a moment where
// the playhead is – memes, reactions, B-roll. Each row: file, moment, Go there, Remove, then seconds, size, place.
ColumnLayout {
    id: field
    spacing: 7

    FieldLabel { label: "Pop-ups"; note: "picture, GIF or video on top" }

    RowLayout {
        Layout.fillWidth: true
        spacing: 10
        NeonButton {
            small: true
            iconText: Theme.icPicture
            text: "Add at playhead"
            onClicked: {
                Store.releaseFocus()
                const at = Store.popupAddTime()   // checked before the file is picked, like the web edition
                if (at === null) return
                picker.at = at
                picker.open()
            }
        }
        Text {
            Layout.fillWidth: true
            text: "Shows for a moment where the playhead is – memes, reactions, B-roll."
            wrapMode: Text.WordWrap
            color: Theme.dim
            font.pixelSize: 11
        }
    }

    // the model is the COUNT, not the array: editing a pop-up reassigns Store.popups, and an int model keeps the rows
    // (and a Seconds box being typed in) until one is added or removed
    Repeater {
        model: Store.popups.length

        Rectangle {
            id: row
            required property int index
            readonly property var p: Store.popups[index] || null
            readonly property var media: p ? Store.popupMedia[p.path] || null : null
            readonly property bool missing: !!media && (!media.exists || !!media.error)

            Layout.fillWidth: true
            implicitHeight: rowColumn.implicitHeight + 16
            radius: 10
            color: Theme.field
            border.color: Theme.line2

            ColumnLayout {
                id: rowColumn
                anchors.fill: parent
                anchors.margins: 8
                spacing: 6

                // name · @ moment · Go there · Remove
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text {
                        Layout.fillWidth: true
                        text: row.p ? Store.popupName(row.p.path) : ""
                        color: row.missing ? Theme.bad : Theme.text
                        font.pixelSize: 12
                        elide: Text.ElideRight
                        HoverHandler { id: nameHover }
                        ToolTip.visible: nameHover.hovered && text !== ""
                        ToolTip.delay: 500
                        // a missing or unreadable file: the engine's own render error
                        ToolTip.text: !row.p ? "" : !row.missing ? row.p.path
                                    : row.media.error || `Pop-up file not found: ${row.p.path}`
                    }
                    Text {
                        text: row.p ? `@ ${Store.fmt(row.p.at)}` : ""
                        color: Theme.dim
                        font.family: Theme.mono
                        font.pixelSize: 11
                    }
                    IconButton {
                        size: 28
                        implicitHeight: 26
                        glyph: Theme.icPlay
                        ToolTip.text: "Go there"
                        onClicked: { Store.releaseFocus(); Store.seekRequested(row.p.at) }
                    }
                    IconButton {
                        size: 28
                        implicitHeight: 26
                        danger: true
                        glyph: Theme.icClose
                        ToolTip.text: "Remove"
                        onClicked: { Store.releaseFocus(); Store.removePopup(row.index) }
                    }
                }

                // Seconds | Size | top / center / bottom (web: a 64px | 1fr | 1.4fr grid, bottom-aligned)
                RowLayout {
                    id: controls
                    Layout.fillWidth: true
                    spacing: 8
                    readonly property real share: Math.max(0, width - 64 - spacing * 2) / 2.4

                    ColumnLayout {
                        Layout.preferredWidth: 64
                        Layout.alignment: Qt.AlignBottom
                        spacing: 3
                        Text { text: "Seconds"; color: Theme.dim; font.pixelSize: 11 }
                        NeonField {
                            id: durField
                            Layout.fillWidth: true
                            implicitHeight: 28
                            mono: true
                            font.pixelSize: 12
                            leftPadding: 7
                            rightPadding: 7
                            validator: RegularExpressionValidator { regularExpression: /^\d{0,2}(\.\d{0,2})?$/ }
                            // live, like the web's input event: empty, 0 or junk counts as 1.5
                            onTextEdited: Store.setPopup(row.index, { dur: Store.clamp(Number(text) || 1.5, 0.3, 10) })
                            // the arrow keys step 0.1, like the web's number box
                            function step(d) {
                                const v = Store.round(Store.clamp((Number(text) || 1.5) + d, 0.3, 10), 1)
                                text = String(v)
                                Store.setPopup(row.index, { dur: v })
                            }
                            Keys.onUpPressed: step(0.1)
                            Keys.onDownPressed: step(-0.1)
                            // the stored (clamped) value whenever the box is not being typed in
                            Binding {
                                target: durField
                                property: "text"
                                value: row.p ? String(row.p.dur) : ""
                                when: !durField.activeFocus
                                restoreMode: Binding.RestoreNone
                            }
                        }
                    }
                    ColumnLayout {
                        Layout.preferredWidth: controls.share
                        Layout.alignment: Qt.AlignBottom
                        spacing: 3
                        Text { text: "Size"; color: Theme.dim; font.pixelSize: 11 }
                        NeonSlider {
                            Layout.fillWidth: true
                            implicitHeight: 28
                            from: 20; to: 100; stepSize: 1
                            value: row.p ? Math.round(row.p.size * 100) : 80
                            onMoved: Store.setPopup(row.index, { size: Store.clamp(value / 100, 0.2, 1) })
                        }
                    }
                    Segmented {
                        Layout.preferredWidth: controls.share * 1.4
                        Layout.alignment: Qt.AlignBottom
                        buttonHeight: 22
                        inset: 3
                        fontSize: 9
                        letterSpacing: 0.9
                        model: [{ value: "top", label: "top" }, { value: "center", label: "center" }, { value: "bottom", label: "bottom" }]
                        current: row.p ? row.p.pos : "center"
                        onPicked: (value) => Store.setPopup(row.index, { pos: value })
                    }
                }
            }
        }
    }

    FileDialog {
        id: picker
        property real at: 0
        title: "Choose a picture, GIF or short video"
        nameFilters: [Store.popupFilter, "All files (*)"]
        onAccepted: Store.addPopupFile(selectedFile.toString(), at)
    }
}
