import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Effects
import "."

// Uppercase pill button: primary = solid cyan with glow, otherwise a dark ghost button.
Button {
    id: btn
    property bool primary: false
    property bool small: false
    property color accent: Theme.cyan
    property string iconText: ""
    property bool active: false             // a tool that is switched on: tinted with activeColor + glow
    property color activeColor: Theme.magenta
    property real activeFill: 0.16          // web .btn.small.on: 16 % tint, 30 % glow
    property real activeGlow: 0.3

    implicitHeight: small ? 30 : 38
    leftPadding: small ? 12 : 18
    rightPadding: small ? 12 : 18
    font.family: Theme.display
    font.pixelSize: small ? 11 : 12.5
    font.weight: Font.DemiBold
    font.letterSpacing: 1.4
    font.capitalization: Font.AllUppercase
    hoverEnabled: true
    focusPolicy: Qt.NoFocus

    contentItem: Row {
        spacing: 7
        Text {
            visible: btn.iconText !== ""
            text: btn.iconText
            color: label.color
            font.pixelSize: btn.font.pixelSize + 2
            font.family: btn.iconText.length === 1 && btn.iconText.charCodeAt(0) >= 0xE000 ? Theme.icons : Theme.ui
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            id: label
            text: btn.text
            font: btn.font
            color: btn.primary ? "#00141a" : btn.active ? "#ffffff" : (btn.hovered ? btn.accent : Theme.text)
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    background: Rectangle {
        radius: 10
        color: btn.primary ? (btn.down ? Theme.cyan2 : (btn.hovered ? "#6ff4ff" : btn.accent))
             : btn.active ? Qt.rgba(btn.activeColor.r, btn.activeColor.g, btn.activeColor.b, btn.activeFill)
             : (btn.hovered ? Qt.rgba(0, 229 / 255, 1, 0.06) : Theme.raised)
        border.width: btn.primary ? 0 : 1
        border.color: btn.active ? btn.activeColor
                    : btn.hovered ? Qt.rgba(btn.accent.r, btn.accent.g, btn.accent.b, 0.6) : Theme.line2
        opacity: btn.enabled ? 1 : 0.35
        layer.enabled: (btn.primary || btn.active) && btn.enabled
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: btn.primary ? btn.accent : btn.activeColor
            shadowBlur: 0.8
            shadowOpacity: btn.primary ? (btn.hovered ? 0.8 : 0.5) : btn.activeGlow
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 0
        }
    }
    opacity: enabled ? 1 : 0.5
}
