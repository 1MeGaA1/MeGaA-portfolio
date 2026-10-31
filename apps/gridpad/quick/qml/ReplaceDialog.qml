import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Ctrl+H: find and replace across this sheet or the whole workbook.
// open(initialFind): Find starts filled in (the find box's text) and selected; Enter = Replace all.
GPDialog {
    id: dlg

    function open(initialFind) {
        findField.text = initialFind || ""
        replaceField.text = ""
        whereBox.currentIndex = 0
        dlg.visible = true
        findField.selectAll()
        findField.forceActiveFocus()
    }

    function submit() {
        backend.replaceAll(findField.text, replaceField.text, whereBox.currentIndex === 1)
        dlg.accept()
    }

    // Enter on a closed dropdown also means "Replace all", like the classic dialog's default button.
    function _comboEnter(event, combo) {
        if (combo.popup.visible)
            event.accepted = false
        else
            dlg.submit()
    }

    title: "Find and replace"
    preferredWidth: 420

    component FormLabel: Text {
        Layout.alignment: Qt.AlignLeft | Qt.AlignVCenter
        font.family: Theme.sans
        font.pixelSize: 13
        font.weight: Theme.wNormal
        color: Theme.c.TEXT
    }

    GridLayout {
        Layout.fillWidth: true
        columns: 2
        columnSpacing: 12
        rowSpacing: 10

        Keys.onReturnPressed: dlg.submit()
        Keys.onEnterPressed: dlg.submit()

        FormLabel { text: "Find" }
        GPField {
            id: findField
            objectName: "findField"
            Layout.fillWidth: true
            mono: true
        }

        FormLabel { text: "Replace with" }
        GPField {
            id: replaceField
            objectName: "replaceField"
            Layout.fillWidth: true
            mono: true
        }

        FormLabel { text: "Where" }
        GPCombo {
            id: whereBox
            objectName: "whereBox"
            Layout.fillWidth: true
            model: ["This sheet", "All sheets"]
            Keys.onReturnPressed: (event) => dlg._comboEnter(event, whereBox)
            Keys.onEnterPressed: (event) => dlg._comboEnter(event, whereBox)
        }
    }

    Text {
        Layout.fillWidth: true
        Layout.preferredWidth: 100
        Layout.topMargin: 2
        wrapMode: Text.WordWrap
        text: "Matches ignore upper/lower case. Ctrl+Z undoes the whole replace."
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
            text: "Replace all"
            primary: true
            Keys.onReturnPressed: dlg.submit()
            Keys.onEnterPressed: dlg.submit()
            onClicked: dlg.submit()
        }
    ]
}
