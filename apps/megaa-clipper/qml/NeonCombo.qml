import QtQuick
import QtQuick.Controls.Basic
import "."

// Dark drop-down; model = [{value, label}].
ComboBox {
    id: combo
    textRole: "label"
    valueRole: "value"
    focusPolicy: Qt.NoFocus
    implicitHeight: 38
    font.family: Theme.ui
    font.pixelSize: 13

    contentItem: Text {
        leftPadding: 12
        rightPadding: 28
        text: combo.displayText
        font: combo.font
        color: Theme.text
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    indicator: Text {
        x: combo.width - width - 12
        y: (combo.height - height) / 2
        text: String.fromCharCode(0xE70D)
        font.family: Theme.icons
        font.pixelSize: 10
        color: Theme.muted
    }
    background: Rectangle {
        radius: 10
        color: Theme.field
        border.color: combo.hovered || combo.popup.visible ? Qt.rgba(0, 229 / 255, 1, 0.45) : Theme.line2
    }
    delegate: ItemDelegate {
        required property var modelData
        required property int index
        width: combo.width
        height: 32
        highlighted: combo.highlightedIndex === index
        contentItem: Text {
            text: modelData.label
            color: highlighted ? Theme.cyan : Theme.text
            font: combo.font
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle { color: highlighted ? Theme.cyanSoft : "transparent"; radius: 6 }
    }
    popup: Popup {
        y: combo.height + 4
        width: combo.width
        implicitHeight: Math.min(contentItem.implicitHeight + 8, 300)
        padding: 4
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: combo.popup.visible ? combo.delegateModel : null
            currentIndex: combo.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
        background: Rectangle { radius: 10; color: Theme.panelSolid; border.color: Theme.line2 }
    }
}
