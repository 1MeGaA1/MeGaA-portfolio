pragma Singleton
import QtQuick

// The same neon palette and fonts as the web edition (ui/app.css).
QtObject {
    readonly property color bg: "#04060b"
    readonly property color panel: Qt.rgba(12 / 255, 17 / 255, 29 / 255, 0.86)
    readonly property color panelSolid: "#0a0f1a"
    readonly property color raised: "#111a2b"
    readonly property color field: "#070c16"
    readonly property color line: Qt.rgba(130 / 255, 170 / 255, 1, 0.10)
    readonly property color line2: Qt.rgba(130 / 255, 170 / 255, 1, 0.18)
    readonly property color text: "#e8f1ff"
    readonly property color muted: "#7b8aa9"
    readonly property color dim: "#4d5a76"
    readonly property color cyan: "#00e5ff"
    readonly property color cyan2: "#00b8d4"
    readonly property color cyanSoft: Qt.rgba(0, 229 / 255, 1, 0.12)
    readonly property color magenta: "#ff2bd6"
    readonly property color violet: "#8b5cff"
    readonly property color ok: "#2bffa0"
    readonly property color warn: "#ffb547"
    readonly property color bad: "#ff4d6d"
    readonly property color pickBg: "#0d2b3a"

    readonly property string ui: "Segoe UI"
    readonly property string display: "Bahnschrift"
    readonly property string mono: "Cascadia Mono"
    readonly property int radius: 14

    // Windows 11 icon font (Segoe Fluent Icons) glyphs
    readonly property string icons: "Segoe Fluent Icons"
    readonly property string icPlay: String.fromCharCode(0xE768)
    readonly property string icPause: String.fromCharCode(0xE769)
    readonly property string icBack: String.fromCharCode(0xEB9E)
    readonly property string icForward: String.fromCharCode(0xEB9D)
    readonly property string icRender: String.fromCharCode(0xE896)
    readonly property string icFolder: String.fromCharCode(0xE838)
    readonly property string icOpen: String.fromCharCode(0xE8E5)
    readonly property string icDelete: String.fromCharCode(0xE74D)
    readonly property string icEdit: String.fromCharCode(0xE70F)
    readonly property string icClose: String.fromCharCode(0xE711)
    readonly property string icSearch: String.fromCharCode(0xE721)
    readonly property string icRefresh: String.fromCharCode(0xE72C)
    readonly property string icVideo: String.fromCharCode(0xE714)
    readonly property string icAdd: String.fromCharCode(0xE710)
    readonly property string icMic: String.fromCharCode(0xE720)
    readonly property string icCheck: String.fromCharCode(0xE73E)
    readonly property string icWarn: String.fromCharCode(0xE7BA)
    readonly property string icInfo: String.fromCharCode(0xE946)
    readonly property string icCut: String.fromCharCode(0xE8C6)     // scissors
    readonly property string icMute: String.fromCharCode(0xE74F)    // speaker with a cross
    readonly property string icVolume: String.fromCharCode(0xE767)  // speaker (sound tiles)
    readonly property string icMusic: String.fromCharCode(0xEC4F)   // music note
    readonly property string icPicture: String.fromCharCode(0xE8B9) // photo (pop-ups)
    readonly property string icUndo: String.fromCharCode(0xE7A7)    // undo, restore a deleted part
    readonly property string icRedo: String.fromCharCode(0xE7A6)
    readonly property string icSettings: String.fromCharCode(0xE713)   // gear
    readonly property string icPackage: String.fromCharCode(0xE7B8)    // box (export pack)
    readonly property string icStar: String.fromCharCode(0xE735)       // filled star (viral moments)
    readonly property string icClips: String.fromCharCode(0xE8C8)   // copy (split into clips)
}
