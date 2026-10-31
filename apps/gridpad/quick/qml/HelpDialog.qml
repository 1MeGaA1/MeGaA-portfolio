import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// F1: every keyboard shortcut on one card. Fits the window and scrolls (eased wheel, arrows,
// Page Up/Down, Home/End) when it doesn't; Enter or Esc closes.
GPDialog {
    id: dlg

    function open() {
        list.contentY = 0
        scroller.to = 0
        dlg.visible = true
        list.forceActiveFocus()
    }

    // Eased scroll to an absolute offset, clamped to the content.
    function scrollTo(y) {
        const target = Math.max(0, Math.min(list.contentHeight - list.height, y))
        if (target === scroller.to && scroller.running)
            return
        scroller.stop()
        scroller.from = list.contentY
        scroller.to = target
        scroller.start()
    }

    function scrollBy(dy) {
        dlg.scrollTo((scroller.running ? scroller.to : list.contentY) + dy)
    }

    title: "Keyboard"
    preferredWidth: 600

    Flickable {
        id: list
        objectName: "list"

        // Title, gaps, the button row and the card's padding take ~150px; keep 24px of window margin.
        readonly property real roomForList: (dlg.parent ? dlg.parent.height : 800) - 48 - 150

        Layout.fillWidth: true
        Layout.preferredHeight: Math.max(120, Math.min(keys.implicitHeight, roomForList))
        contentWidth: width
        contentHeight: keys.implicitHeight
        clip: true
        interactive: false  // the WheelHandler below scrolls with easing instead of Flickable's fling
        boundsBehavior: Flickable.StopAtBounds
        focus: true
        activeFocusOnTab: true  // Tab to Close and back still reaches the scroll keys

        Keys.onReturnPressed: dlg.accept()
        Keys.onEnterPressed: dlg.accept()
        Keys.onUpPressed: dlg.scrollBy(-48)
        Keys.onDownPressed: dlg.scrollBy(48)
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_PageUp)
                dlg.scrollBy(-list.height * 0.9)
            else if (event.key === Qt.Key_PageDown)
                dlg.scrollBy(list.height * 0.9)
            else if (event.key === Qt.Key_Home)
                dlg.scrollTo(0)
            else if (event.key === Qt.Key_End)
                dlg.scrollTo(list.contentHeight)
            else
                return
            event.accepted = true
        }

        NumberAnimation {
            id: scroller
            target: list
            property: "contentY"
            duration: 260
            easing.type: Easing.OutCubic
        }

        WheelHandler {
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: (event) => {
                if (event.pixelDelta.y !== 0) {  // touchpads already scroll smoothly: follow them 1:1
                    scroller.stop()
                    list.contentY = Math.max(0, Math.min(list.contentHeight - list.height,
                                                         list.contentY - event.pixelDelta.y))
                } else {
                    dlg.scrollBy(-event.angleDelta.y / 120 * 72)
                }
            }
        }

        ScrollBar.vertical: ScrollBar {
            id: bar
            policy: list.contentHeight > list.height + 1 ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
            padding: 1
            contentItem: Rectangle {
                implicitWidth: 6
                radius: 3
                color: bar.pressed || bar.hovered ? Theme.c.MUTED : Theme.c.SCROLL
                Behavior on color { ColorAnimation { duration: 120 } }
            }
            background: Item { }
        }

        GridLayout {
            id: keys
            width: list.width - (bar.visible ? 14 : 0)
            columns: 2
            columnSpacing: 16
            rowSpacing: 9

            Repeater {
                model: backend.helpKeys
                delegate: Rectangle {
                    id: keyChip
                    required property int index
                    required property var modelData
                    Layout.row: index
                    Layout.column: 0
                    Layout.alignment: Qt.AlignLeft | Qt.AlignTop
                    implicitWidth: chip.implicitWidth + 14
                    implicitHeight: chip.implicitHeight + 6
                    radius: 4
                    color: "transparent"
                    border.color: Theme.c.MENU_BORDER
                    Text {
                        id: chip
                        anchors.centerIn: parent
                        text: keyChip.modelData[0]
                        textFormat: Text.PlainText
                        font.family: Theme.mono
                        font.pixelSize: 11
                        font.weight: Theme.wNormal
                        color: Theme.c.TEXT_SOFT
                    }
                }
            }

            Repeater {
                model: backend.helpKeys
                delegate: Text {
                    id: keyText
                    required property int index
                    required property var modelData
                    Layout.row: index
                    Layout.column: 1
                    Layout.fillWidth: true
                    Layout.preferredWidth: 100
                    Layout.alignment: Qt.AlignTop
                    Layout.topMargin: 2
                    text: keyText.modelData[1]
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                    font.family: Theme.sans
                    font.pixelSize: 12
                    font.weight: Theme.wNormal
                    color: Theme.c.TEXT_SOFT
                }
            }
        }
    }

    buttons: [
        GPButton {
            text: "Close"
            primary: true
            Keys.onReturnPressed: dlg.accept()
            Keys.onEnterPressed: dlg.accept()
            onClicked: dlg.accept()
        }
    ]
}
