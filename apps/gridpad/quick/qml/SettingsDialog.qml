import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Ctrl+, "Appearance": theme, fonts, bold text, background effect and the column separator.
// The card under the form is a live preview drawn in the chosen theme and fonts (the classic
// dialog's _refresh pixmap, redrawn by the scene graph); its colours glide between themes.
// Apply hands everything to backend.applySettings, which restyles the window live.
GPDialog {
    id: dlg

    property bool _animate: false  // off while open() fills the form, so the preview doesn't glide in
    readonly property var effectNames: backend.effectList.map(e => String(e[0]))
    readonly property var effectLabels: backend.effectList.map(e => e[0] + "  ·  " + e[1])
    // The separators behind backend.separatorLabels (app/export.py SEPARATORS); the last row is Custom.
    readonly property var separatorValues: backend.separatorValues
    readonly property string separator: sepPicker.customRow
                                        ? (sepPicker.customText || ",")
                                        : (dlg.separatorValues[sepPicker.currentIndex] ?? ",")
    // What the preview shows: the chosen entries, or — while a dropdown is open — the entry under
    // the mouse / keyboard highlight, so browsing themes and fonts previews them before choosing.
    readonly property string previewTheme: dlg._browsed(themeBox)
    readonly property string previewMono: dlg._browsed(monoBox)
    readonly property string previewSans: dlg._browsed(sansBox)
    readonly property var colors: backend.themeColors(dlg.previewTheme)

    function _browsed(combo) {
        if (combo.popup.visible && combo.highlightedIndex >= 0)
            return combo.textAt(combo.highlightedIndex)
        return combo.currentText
    }

    function open() {
        dlg._animate = false
        const s = backend.settingsState()
        themeBox.currentIndex = Math.max(0, backend.themeNames.indexOf(s.theme))
        const monos = backend.monoFamilies()
        monoBox.model = monos
        monoBox.currentIndex = Math.max(0, monos.indexOf(s.mono))
        const sanses = backend.uiFamilies()
        sansBox.model = sanses
        sansBox.currentIndex = Math.max(0, sanses.indexOf(s.sans))
        boldCheck.checked = !!s.bold
        effectBox.currentIndex = Math.max(0, dlg.effectNames.indexOf(s.effect))
        sepPicker.currentIndex = s.sepIndex
        sepPicker.customText = s.custom
        dlg.visible = true
        themeBox.forceActiveFocus()
        Qt.callLater(dlg._arm)
    }

    function _arm() { dlg._animate = true }

    function submit() {
        backend.applySettings(themeBox.currentText, monoBox.currentText, sansBox.currentText,
                              boldCheck.checked, dlg.effectNames[effectBox.currentIndex] || "None",
                              sepPicker.currentIndex, sepPicker.customText)
        dlg.accept()
    }

    title: "Appearance"
    preferredWidth: 464  // 428px of content, the classic preview's width

    // ---- form pieces (same look in every dialog: sans 13 labels, 30px fields) ----
    component FormLabel: Text {
        Layout.alignment: Qt.AlignLeft | Qt.AlignTop
        Layout.preferredHeight: 30
        verticalAlignment: Text.AlignVCenter
        font.family: Theme.sans
        font.pixelSize: 13
        font.weight: Theme.wNormal
        color: Theme.c.TEXT
    }

    // A dropdown where Enter (while closed) is the dialog's default button, as in a QDialog.
    component FormCombo: GPCombo {
        id: fc
        signal submitted()
        Layout.fillWidth: true
        Keys.onReturnPressed: (event) => { if (fc.popup.visible) event.accepted = false; else fc.submitted() }
        Keys.onEnterPressed: (event) => { if (fc.popup.visible) event.accepted = false; else fc.submitted() }
    }

    // Separator dropdown + the Custom text field, which slides open only for the Custom row.
    component SeparatorPicker: ColumnLayout {
        id: picker
        property alias model: box.model
        property alias currentIndex: box.currentIndex
        property alias customText: custom.text
        property alias combo: box
        property bool animate: false
        readonly property bool customRow: box.currentIndex === box.count - 1
        property real reveal: picker.customRow ? 1 : 0
        signal submitted()

        Layout.fillWidth: true
        spacing: 0
        Behavior on reveal {
            enabled: picker.animate
            NumberAnimation { duration: 170; easing.type: Easing.OutCubic }
        }

        FormCombo {
            id: box
            onSubmitted: picker.submitted()
        }
        GPField {
            id: custom
            Layout.fillWidth: true
            Layout.topMargin: 10 * picker.reveal
            Layout.preferredHeight: 30 * picker.reveal
            visible: picker.reveal > 0.001
            opacity: picker.reveal
            clip: true
            mono: true
            placeholderText: "Type any separator"
        }
    }

    GridLayout {
        Layout.fillWidth: true
        columns: 2
        columnSpacing: 12
        rowSpacing: 10

        Keys.onReturnPressed: dlg.submit()
        Keys.onEnterPressed: dlg.submit()

        FormLabel { text: "Theme"; Layout.row: 0; Layout.column: 0 }
        FormCombo {
            id: themeBox
            objectName: "themeBox"
            Layout.row: 0
            Layout.column: 1
            model: backend.themeNames
            onSubmitted: dlg.submit()
        }

        FormLabel { text: "Notes font"; Layout.row: 1; Layout.column: 0 }
        FormCombo {
            id: monoBox
            objectName: "monoBox"
            Layout.row: 1
            Layout.column: 1
            model: []
            previewFonts: true
            onSubmitted: dlg.submit()
        }

        FormLabel { text: "App font"; Layout.row: 2; Layout.column: 0 }
        FormCombo {
            id: sansBox
            objectName: "sansBox"
            Layout.row: 2
            Layout.column: 1
            model: []
            previewFonts: true
            onSubmitted: dlg.submit()
        }

        GPCheck {
            id: boldCheck
            objectName: "boldCheck"
            Layout.row: 3
            Layout.column: 1
            leftPadding: 0
            text: "Bold text everywhere"
        }

        FormLabel { text: "Effect"; Layout.row: 4; Layout.column: 0 }
        FormCombo {
            id: effectBox
            objectName: "effectBox"
            Layout.row: 4
            Layout.column: 1
            model: dlg.effectLabels
            onSubmitted: dlg.submit()
        }

        FormLabel { text: "Between columns"; Layout.row: 5; Layout.column: 0 }
        SeparatorPicker {
            id: sepPicker
            objectName: "sepPicker"
            Layout.row: 5
            Layout.column: 1
            model: backend.separatorLabels
            animate: dlg._animate
            onSubmitted: dlg.submit()
        }
    }

    // ---- live preview: 428 x 104, laid out like the classic pixmap ----
    Rectangle {
        id: card
        objectName: "card"

        readonly property string monoFamily: dlg.previewMono
        readonly property string sansFamily: dlg.previewSans
        readonly property int heavy: boldCheck.checked ? Font.DemiBold : Font.Normal
        readonly property int titleWeight: boldCheck.checked ? Font.Bold : Font.DemiBold

        // The previewed theme's tokens; each one eases to the next theme's value.
        property color cBg: dlg.colors.BG
        property color cPanel: dlg.colors.PANEL
        property color cBorder: dlg.colors.BORDER
        property color cText: dlg.colors.TEXT
        property color cMuted: dlg.colors.MUTED
        property color cAccent: dlg.colors.ACCENT
        property color cAccentBg: dlg.colors.ACCENT_BG
        property color cHi: dlg.colors.HI
        property color cHiText: dlg.colors.HI_TEXT
        property color cTag: dlg.colors.TAG
        property color cTagBg: dlg.colors.TAG_BG

        Behavior on cBg { enabled: dlg._animate; ColorAnimation { duration: 260; easing.type: Easing.OutCubic } }
        Behavior on cPanel { enabled: dlg._animate; ColorAnimation { duration: 260; easing.type: Easing.OutCubic } }
        Behavior on cBorder { enabled: dlg._animate; ColorAnimation { duration: 260; easing.type: Easing.OutCubic } }
        Behavior on cText { enabled: dlg._animate; ColorAnimation { duration: 260; easing.type: Easing.OutCubic } }
        Behavior on cMuted { enabled: dlg._animate; ColorAnimation { duration: 260; easing.type: Easing.OutCubic } }
        Behavior on cAccent { enabled: dlg._animate; ColorAnimation { duration: 260; easing.type: Easing.OutCubic } }
        Behavior on cAccentBg { enabled: dlg._animate; ColorAnimation { duration: 260; easing.type: Easing.OutCubic } }
        Behavior on cHi { enabled: dlg._animate; ColorAnimation { duration: 260; easing.type: Easing.OutCubic } }
        Behavior on cHiText { enabled: dlg._animate; ColorAnimation { duration: 260; easing.type: Easing.OutCubic } }
        Behavior on cTag { enabled: dlg._animate; ColorAnimation { duration: 260; easing.type: Easing.OutCubic } }
        Behavior on cTagBg { enabled: dlg._animate; ColorAnimation { duration: 260; easing.type: Easing.OutCubic } }

        Layout.fillWidth: true
        Layout.topMargin: 4
        implicitHeight: 104
        radius: 6
        color: card.cBg

        // Top strip (PANEL) with the theme name and "sans + mono".
        Rectangle {
            width: parent.width
            height: 26
            radius: card.radius
            color: card.cPanel
        }
        Rectangle {  // squares off the strip's bottom corners
            y: 26 - card.radius
            width: parent.width
            height: card.radius
            color: card.cPanel
        }
        Rectangle {
            y: 26
            width: parent.width
            height: 1
            color: card.cBorder
        }
        Text {
            id: themeLabel
            x: 12
            height: 26
            verticalAlignment: Text.AlignVCenter
            text: dlg.previewTheme
            font.family: card.sansFamily
            font.pixelSize: 12
            font.weight: card.titleWeight
            color: card.cText
        }
        Text {
            anchors.right: parent.right
            anchors.rightMargin: 12
            width: Math.max(0, card.width - 24 - themeLabel.implicitWidth - 16)
            height: 26
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideRight
            text: card.sansFamily + " + " + card.monoFamily
            font.family: card.sansFamily
            font.pixelSize: 11
            font.weight: card.heavy
            color: card.cMuted
        }

        // A selected cell with a tag pill.
        Rectangle {
            id: cell
            x: 12
            y: 38
            width: Math.min(310, card.width - 24)
            height: 26
            color: card.cAccentBg
            border.width: 1
            border.color: card.cAccent

            Text {
                x: 8
                width: Math.max(0, cell.width - 68)
                height: cell.height
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                text: "Call plumber — £180"
                font.family: card.monoFamily
                font.pixelSize: 13
                font.weight: card.heavy
                color: card.cText
            }
            Rectangle {
                x: cell.width - 55
                y: 4
                width: 48
                height: 17
                radius: 3
                color: card.cTagBg
                Text {
                    anchors.centerIn: parent
                    text: "#home"
                    font.family: card.monoFamily
                    font.pixelSize: 11
                    font.weight: card.heavy
                    color: card.cTag
                }
            }
        }

        // A find highlight and the copy separator.
        Rectangle {
            x: 12
            y: 74
            width: 62
            height: 20
            color: card.cHi
            Text {
                anchors.centerIn: parent
                text: "found"
                font.family: card.monoFamily
                font.pixelSize: 13
                font.weight: card.heavy
                color: card.cHiText
            }
        }
        Text {
            x: 86
            y: 74
            width: Math.max(0, card.width - 98)
            height: 20
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            text: "copy: aa" + dlg.separator.replace(/\t/g, "⇥") + "bb · 18 notes"
            textFormat: Text.PlainText  // a typed separator like "<b>" must show as typed
            font.family: card.monoFamily
            font.pixelSize: 13
            font.weight: card.heavy
            color: card.cMuted
        }

        Rectangle {  // outline in the previewed theme, so the card reads as a little window
            anchors.fill: parent
            radius: card.radius
            color: "transparent"
            border.color: card.cBorder
        }
    }

    Text {
        Layout.fillWidth: true
        Layout.preferredWidth: 100
        wrapMode: Text.WordWrap
        text: "Applies right away and is remembered. The separator is used when copying blocks and as the export default. Install a font and it appears here."
        font.family: Theme.sans
        font.pixelSize: 11
        font.weight: Theme.wNormal
        color: Theme.c.MUTED
    }

    buttons: [
        GPButton {
            text: "Cancel"
            Keys.onReturnPressed: dlg.reject()
            Keys.onEnterPressed: dlg.reject()
            onClicked: dlg.reject()
        },
        GPButton {
            text: "Apply"
            primary: true
            Keys.onReturnPressed: dlg.submit()
            Keys.onEnterPressed: dlg.submit()
            onClicked: dlg.submit()
        }
    ]
}
