import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// A centred window over the editor with a title and a close button. Esc or a click outside closes it,
// and while it is open the editor's shortcuts stay quiet (it is modal).
Popup {
    id: dlg
    property string title: ""
    default property alias content: body.data
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: 460
    modal: true
    focus: true
    padding: 22
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle { radius: 16; color: Theme.panelSolid; border.color: Theme.line2 }
    Overlay.modal: Rectangle { color: Qt.rgba(2 / 255, 4 / 255, 8 / 255, 0.6) }

    contentItem: ColumnLayout {
        spacing: 14
        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: dlg.title
                color: Theme.text
                elide: Text.ElideRight
                font.family: Theme.display
                font.pixelSize: 16
                font.weight: Font.DemiBold
                font.letterSpacing: 0.6
            }
            IconButton { glyph: Theme.icClose; size: 28; ToolTip.text: "Close (Esc)"; onClicked: dlg.close() }
        }
        ColumnLayout {
            id: body
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12
        }
    }
}
