import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Effects
import "."

// Small square icon button; `glyph` is a text symbol, `danger` turns the hover red.
Button {
    id: btn
    property string glyph: ""
    property bool danger: false
    property bool active: false
    property color activeColor: Theme.magenta   // border while active
    property color activeText: activeColor      // glyph while active
    property real activeFill: 0.12              // background tint while active
    property real activeGlow: 0.3               // glow while active (web .icon-btn.on: 12 px at 30 %)
    property int size: 32

    implicitWidth: size
    implicitHeight: size
    hoverEnabled: true
    focusPolicy: Qt.NoFocus
    ToolTip.visible: hovered && ToolTip.text !== ""
    ToolTip.delay: 500

    contentItem: Text {
        text: btn.glyph
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.pixelSize: btn.size * 0.45
        // private-use glyphs come from the Windows icon font
        font.family: btn.glyph.length === 1 && btn.glyph.charCodeAt(0) >= 0xE000 ? Theme.icons : Theme.ui
        color: btn.active ? btn.activeText : (btn.hovered ? (btn.danger ? Theme.bad : Theme.cyan) : Theme.muted)
    }
    background: Rectangle {
        radius: 9
        color: btn.active ? Qt.rgba(btn.activeColor.r, btn.activeColor.g, btn.activeColor.b, btn.activeFill)
                          : (btn.hovered ? Qt.rgba(0, 229 / 255, 1, 0.06) : "transparent")
        border.width: 1
        border.color: btn.active ? btn.activeColor
                                 : (btn.hovered ? (btn.danger ? Theme.bad : Qt.rgba(0, 229 / 255, 1, 0.45)) : Theme.line)
        layer.enabled: btn.active
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: btn.activeColor
            shadowBlur: 0.6
            shadowOpacity: btn.activeGlow
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 0
        }
    }
    opacity: enabled ? 1 : 0.3
}
