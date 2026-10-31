import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Ctrl+I / a dropped .csv or .txt: pick the separator and where the cells go, with a live
// preview of the first rows. open(fileName, targetRef) after backend.importReady.
// Cancel / Esc tells the backend to drop the pending file.
GPDialog {
    id: dlg

    property bool _animate: false  // off while open() fills the form, so nothing slides in
    // Off while open() fills the form: each field it sets would otherwise re-parse the whole
    // file in Python. Switching it back on parses the pending file once.
    property bool _live: false
    readonly property var preview: dlg._live
        ? backend.importPreview(sepPicker.currentIndex, sepPicker.customText)
        : ({ summary: "", preview: "" })

    function open(fileName, targetRef) {
        dlg._animate = false
        dlg._live = false
        dlg.title = fileName || "Import"
        sepPicker.currentIndex = 0
        sepPicker.customText = ";"
        destBox.model = ["In a new sheet", "Here, starting at " + (targetRef || "A1")]
        destBox.currentIndex = 0
        dlg._live = true
        dlg.visible = true
        sepPicker.combo.forceActiveFocus()
        Qt.callLater(dlg._arm)
    }

    function _arm() { dlg._animate = true }

    function submit() {
        backend.finishImport(sepPicker.currentIndex, sepPicker.customText, destBox.currentIndex === 0)
        dlg.accept()
    }

    title: "Import"
    preferredWidth: 470

    onRejected: backend.cancelImport()

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

        FormLabel { text: "Between columns"; Layout.row: 0; Layout.column: 0 }
        SeparatorPicker {
            id: sepPicker
            objectName: "sepPicker"
            Layout.row: 0
            Layout.column: 1
            model: backend.importSeparators
            animate: dlg._animate
            onSubmitted: dlg.submit()
        }

        FormLabel { text: "Put it"; Layout.row: 1; Layout.column: 0 }
        FormCombo {
            id: destBox
            objectName: "destBox"
            Layout.row: 1
            Layout.column: 1
            model: ["In a new sheet", "Here, starting at A1"]
            onSubmitted: dlg.submit()
        }
    }

    Text {
        Layout.topMargin: 2
        Layout.fillWidth: true
        text: dlg.preview.summary || ""
        visible: text !== ""
        font.family: Theme.sans
        font.pixelSize: 11
        font.weight: Theme.wNormal
        color: Theme.c.MUTED
        elide: Text.ElideRight
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
            text: dlg.preview.preview || ""
            textFormat: Text.PlainText  // file content like "<b>x" must show as written
            font.family: Theme.mono
            font.pixelSize: 11
            font.weight: Theme.wNormal
            color: Theme.c.TEXT_SOFT
        }
    }

    buttons: [
        GPButton {
            text: "Cancel"
            Keys.onReturnPressed: dlg.reject()
            Keys.onEnterPressed: dlg.reject()
            onClicked: dlg.reject()
        },
        GPButton {
            text: "Import"
            primary: true
            Keys.onReturnPressed: dlg.submit()
            Keys.onEnterPressed: dlg.submit()
            onClicked: dlg.submit()
        }
    ]
}
