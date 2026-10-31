pragma Singleton
import QtQuick

// The active theme's colors and fonts (Python's Palette, exposed as `themeSource`).
// Everything binds here, so Appearance changes restyle the whole window live.
// Colors are the classic token names: Theme.c.BG, Theme.c.ACCENT, Theme.c.TAG_BG, ...
QtObject {
    readonly property var c: themeSource.c
    readonly property string mono: themeSource.mono
    readonly property string sans: themeSource.sans
    readonly property int wNormal: themeSource.wNormal
    readonly property int wBold: themeSource.wBold
    readonly property bool bold: themeSource.bold

    // Grid metrics shared by the grid, its headers and the pinned row.
    readonly property int rowHeight: 28
    readonly property int rowHeaderWidth: 44

    function alpha(color, a) {
        const k = Qt.darker(color, 1.0)
        return Qt.rgba(k.r, k.g, k.b, a)
    }

    // image://icons/<name>/<rrggbb> — stroke icons drawn by Python (see quick/main.py).
    function icon(name, color) {
        return "image://icons/" + name + "/" + String(color).replace("#", "")
    }
}
