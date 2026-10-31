import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import QtQuick.Layouts

// Base for every dialog: a modal card that fades and scales in over a dimmed window.
// Children go in the body (a ColumnLayout); GPButtons go in `buttons` (right-aligned footer).
// accept() / reject() emit their signal and close; Esc counts as reject.
Popup {
    id: dlg

    property string title
    property int preferredWidth: 460
    default property alias content: body.data
    property alias buttons: buttonRow.data
    property bool _settled: false

    signal accepted()
    signal rejected()

    function accept() { dlg._settled = true; dlg.accepted(); dlg.close() }
    function reject() { dlg._settled = true; dlg.rejected(); dlg.close() }

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(dlg.preferredWidth, parent ? parent.width - 32 : dlg.preferredWidth)
    modal: true
    focus: true
    padding: 18
    closePolicy: Popup.CloseOnEscape

    onAboutToShow: dlg._settled = false
    onClosed: if (!dlg._settled) dlg.rejected()

    Overlay.modal: Rectangle {
        color: Qt.rgba(0, 0, 0, 0.42)
    }

    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 150; easing.type: Easing.OutCubic }
            NumberAnimation { property: "scale"; from: 0.95; to: 1; duration: 180; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; to: 0; duration: 110; easing.type: Easing.InCubic }
            NumberAnimation { property: "scale"; to: 0.97; duration: 110; easing.type: Easing.InCubic }
        }
    }

    background: Rectangle {
        color: Theme.c.PANEL
        radius: 8
        border.color: Theme.c.MENU_BORDER
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: "#000000"
            shadowOpacity: 0.55
            shadowBlur: 1.0
            shadowVerticalOffset: 8
            blurMax: 32
        }
    }

    contentItem: ColumnLayout {
        spacing: 14

        Text {
            Layout.fillWidth: true
            visible: dlg.title !== ""
            text: dlg.title
            textFormat: Text.PlainText
            font.family: Theme.sans
            font.pixelSize: 15
            font.weight: Theme.wBold
            color: Theme.c.TEXT
            elide: Text.ElideRight
        }

        ColumnLayout {
            id: body
            Layout.fillWidth: true
            spacing: 10
        }

        RowLayout {
            id: buttonRow
            Layout.alignment: Qt.AlignRight
            visible: children.length > 0
            spacing: 8
        }
    }
}
