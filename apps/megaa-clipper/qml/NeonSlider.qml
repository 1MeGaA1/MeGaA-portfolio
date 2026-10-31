import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Effects
import "."

// Thin cyan slider with a glowing white knob.
Slider {
    id: s
    implicitHeight: 22
    focusPolicy: Qt.NoFocus
    background: Item {
        x: s.leftPadding
        y: s.topPadding + s.availableHeight / 2 - 2
        width: s.availableWidth
        height: 4
        Rectangle { anchors.fill: parent; radius: 2; color: Theme.raised }
        Rectangle { width: s.visualPosition * parent.width; height: parent.height; radius: 2; color: Theme.cyan }
    }
    handle: Rectangle {
        x: s.leftPadding + s.visualPosition * (s.availableWidth - width)
        y: s.topPadding + s.availableHeight / 2 - height / 2
        width: 16; height: 16; radius: 8
        color: "white"
        border.width: 3
        border.color: Theme.cyan
        layer.enabled: true
        layer.effect: MultiEffect { shadowEnabled: true; shadowColor: Theme.cyan; shadowBlur: 0.6; shadowOpacity: 0.9; shadowHorizontalOffset: 0; shadowVerticalOffset: 0 }
    }
}
