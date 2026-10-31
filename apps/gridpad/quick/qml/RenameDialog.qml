import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Rename a sheet (double-click a tab, Ctrl+T's new sheet, the tab menu).
// open(index, name): the field starts with the current name selected; Enter = OK.
GPDialog {
    id: dlg

    property int sheetIndex: -1

    function open(index, name) {
        dlg.sheetIndex = index
        nameField.text = name || ""
        dlg.visible = true
        nameField.selectAll()
        nameField.forceActiveFocus()
    }

    function submit() {
        backend.renameSheet(dlg.sheetIndex, nameField.text)
        dlg.accept()
    }

    title: "Rename sheet"
    preferredWidth: 360

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 6

        Keys.onReturnPressed: dlg.submit()
        Keys.onEnterPressed: dlg.submit()

        Text {
            text: "Sheet name"
            font.family: Theme.sans
            font.pixelSize: 13
            font.weight: Theme.wNormal
            color: Theme.c.TEXT
        }

        GPField {
            id: nameField
            objectName: "nameField"
            Layout.fillWidth: true
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
            text: "OK"
            primary: true
            Keys.onReturnPressed: dlg.submit()
            Keys.onEnterPressed: dlg.submit()
            onClicked: dlg.submit()
        }
    ]
}
