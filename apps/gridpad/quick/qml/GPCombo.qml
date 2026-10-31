import QtQuick
import QtQuick.Controls

// Dropdown over a plain JS array of strings. `previewFonts` draws each entry in its own
// font family (the font pickers in Appearance).
ComboBox {
    id: cb

    property bool previewFonts: false

    implicitHeight: 30
    hoverEnabled: true
    font.family: Theme.sans
    font.pixelSize: 13
    font.weight: Theme.wNormal

    delegate: ItemDelegate {
        id: entry
        required property int index
        required property var modelData

        width: ListView.view ? ListView.view.width : cb.width
        implicitHeight: 28
        highlighted: cb.highlightedIndex === entry.index
        hoverEnabled: true

        contentItem: Text {
            text: String(entry.modelData)
            textFormat: Text.PlainText
            font.family: cb.previewFonts ? String(entry.modelData) : Theme.sans
            font.pixelSize: 13
            font.weight: Theme.wNormal
            color: Theme.c.TEXT
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: 4
            color: entry.highlighted || entry.hovered ? Theme.c.HOVER : "transparent"
        }
    }

    indicator: Icon {
        x: cb.width - width - 8
        y: (cb.height - height) / 2
        name: "chevron-down"
        size: 14
        color: Theme.c.MUTED
    }

    contentItem: Text {
        leftPadding: 8
        rightPadding: 28
        text: cb.displayText
        textFormat: Text.PlainText
        font.family: cb.previewFonts ? cb.displayText : Theme.sans
        font.pixelSize: 13
        font.weight: Theme.wNormal
        color: Theme.c.TEXT
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        implicitWidth: 200
        radius: 4
        color: Theme.c.FIELD
        border.color: cb.popup.visible || cb.visualFocus ? Theme.c.ACCENT
                      : (cb.hovered ? Theme.c.MENU_BORDER : Theme.c.BORDER)
        Behavior on border.color { ColorAnimation { duration: 120 } }
    }

    popup: Popup {
        y: cb.height + 3
        width: cb.width
        implicitHeight: Math.min(contentItem.implicitHeight + topPadding + bottomPadding, 320)
        padding: 5

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: cb.popup.visible ? cb.delegateModel : null
            currentIndex: cb.highlightedIndex
            highlightMoveDuration: 0
            boundsBehavior: Flickable.StopAtBounds
            ScrollIndicator.vertical: ScrollIndicator { }
        }

        background: Rectangle {
            color: Theme.c.MENU_BG
            border.color: Theme.c.MENU_BORDER
            radius: 6
        }

        enter: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 120; easing.type: Easing.OutCubic }
                NumberAnimation { property: "y"; from: cb.height - 4; to: cb.height + 3; duration: 140; easing.type: Easing.OutCubic }
            }
        }
        exit: Transition {
            NumberAnimation { property: "opacity"; to: 0; duration: 80 }
        }
    }
}
