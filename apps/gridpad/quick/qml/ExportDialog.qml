import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

// Ctrl+E: export a sheet as delimited text. Pick the sheet and the separator (live preview),
// then Export opens the Save dialog; the chosen separator is remembered as the copy default.
GPDialog {
    id: dlg

    property int _exportSheet: 0
    property bool _animate: false  // off while open() fills the form, so nothing slides in
    // Off while open() fills the form: each field it sets would otherwise re-export the whole
    // sheet in Python. Switching it back on reads the sheet once, fresh.
    property bool _live: false
    readonly property string previewText: dlg._live
        ? backend.exportPreview(sheetBox.currentIndex, sepPicker.currentIndex, sepPicker.customText)
        : ""

    function open() {
        dlg._animate = false
        dlg._live = false
        const names = backend.sheetNames
        sheetBox.model = names
        sheetBox.currentIndex = Math.max(0, Math.min(names.length - 1, backend.currentSheet))
        const sep = backend.separatorState()
        sepPicker.currentIndex = sep.index
        sepPicker.customText = sep.custom
        dlg._live = true
        dlg.visible = true
        sheetBox.forceActiveFocus()
        Qt.callLater(dlg._arm)
    }

    function _arm() { dlg._animate = true }

    function submit() {
        const sheet = sheetBox.currentIndex
        const target = backend.exportTarget(sheet, sepPicker.currentIndex, sepPicker.customText)
        dlg._exportSheet = sheet
        saveDialog.nameFilters = target.filters
        saveDialog.currentFolder = target.folder
        saveDialog.selectedFile = target.file
        dlg.accept()
        saveDialog.open()
    }

    title: "Export sheet"
    preferredWidth: 440

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

        FormLabel { text: "Sheet"; Layout.row: 0; Layout.column: 0 }
        FormCombo {
            id: sheetBox
            objectName: "sheetBox"
            Layout.row: 0
            Layout.column: 1
            model: []
            onSubmitted: dlg.submit()
        }

        FormLabel { text: "Between columns"; Layout.row: 1; Layout.column: 0 }
        SeparatorPicker {
            id: sepPicker
            objectName: "sepPicker"
            Layout.row: 1
            Layout.column: 1
            model: backend.separatorLabels
            animate: dlg._animate
            onSubmitted: dlg.submit()
        }
    }

    Text {
        Layout.topMargin: 2
        text: "Preview"
        font.family: Theme.sans
        font.pixelSize: 11
        font.weight: Theme.wNormal
        color: Theme.c.MUTED
    }

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: previewLabel.implicitHeight + 18
        radius: 4
        color: Theme.c.FIELD
        border.color: Theme.c.BORDER
        clip: true

        Text {
            id: previewLabel
            objectName: "previewLabel"
            x: 9
            y: 9
            width: parent.width - 18
            text: dlg.previewText
            textFormat: Text.PlainText  // notes like "<b>x" must show as typed
            font.family: Theme.mono
            font.pixelSize: 11
            font.weight: Theme.wNormal
            color: Theme.c.TEXT_SOFT
        }
    }

    // The native Save dialog; Export fills in the start folder, file name and filters.
    FileDialog {
        id: saveDialog
        objectName: "saveDialog"
        title: "Export sheet"
        fileMode: FileDialog.SaveFile
        onAccepted: backend.exportTo(dlg._exportSheet, saveDialog.selectedFile.toString())
    }

    buttons: [
        GPButton {
            text: "Cancel"
            Keys.onReturnPressed: dlg.reject()
            Keys.onEnterPressed: dlg.reject()
            onClicked: dlg.reject()
        },
        GPButton {
            text: "Export"
            primary: true
            Keys.onReturnPressed: dlg.submit()
            Keys.onEnterPressed: dlg.submit()
            onClicked: dlg.submit()
        }
    ]
}
