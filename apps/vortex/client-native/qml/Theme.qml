pragma Singleton
import QtQuick

QtObject {
    // ---- Existing core tokens (preserved) ----
    readonly property color bg: "#05050c"
    readonly property color bgPanel: "#0a0a14"
    readonly property color bgPanelAlt: "#08081a"
    readonly property color surface: "#12122a"
    readonly property color surfaceAlt: "#16162b"
    readonly property color cyan: "#00e5ff"
    readonly property color magenta: "#ff3d9a"
    readonly property color green: "#00ff88"
    readonly property color amber: "#ffb800"
    readonly property color red: "#ff4a4a"
    readonly property color textPrimary: "#ffffff"
    readonly property color textMuted: "#8a8aa5"
    readonly property color textDim: "#6a6a80"
    readonly property color textFaint: "#4a4a60"
    readonly property color border: "#2a2a45"
    readonly property color borderDim: "#1a1a2a"
    readonly property string fontDisplay: "Rajdhani"
    readonly property string fontBody: "Chakra Petch"
    readonly property string fontMono: "JetBrains Mono"

    // ---- New: glassy surface tokens ----
    readonly property color glassBg: Qt.rgba(18 / 255, 18 / 255, 42 / 255, 0.55)
    readonly property color glassBorder: Qt.rgba(0.4, 0.42, 0.65, 0.28)

    // ---- New: neon-tinted derived tokens for depth/glow ----
    readonly property color cyanDim: Qt.rgba(0, 0.898, 1, 0.55)
    readonly property color magentaDim: Qt.rgba(1, 0.239, 0.604, 0.55)
    readonly property color cyanFaint: Qt.rgba(0, 0.898, 1, 0.12)
    readonly property color magentaFaint: Qt.rgba(1, 0.239, 0.604, 0.12)
    readonly property color scanline: Qt.rgba(1, 1, 1, 0.04)
    readonly property color shadowSoft: Qt.rgba(0, 0, 0, 0.45)
    readonly property color shadowDeep: Qt.rgba(0, 0, 0, 0.7)
    readonly property color highlightTop: Qt.rgba(1, 1, 1, 0.06)

    // ---- New: layout / motion constants ----
    readonly property int clipCut: 14
    readonly property int radius: 4
    readonly property int radiusLg: 8
    readonly property int animFast: 120
    readonly property int animMed: 220
    readonly property int animSlow: 420

    // ---- New: glow helper. Returns `color` at the given alpha. ----
    function glow(c, alpha) {
        var col = Qt.color(c)
        return Qt.rgba(col.r, col.g, col.b, alpha)
    }

    // ---- New: accent gradient helper. Returns a lighter/darker pair for a base accent. ----
    function accentGrad(c) {
        var col = Qt.color(c)
        return {
            a: Qt.rgba(Math.min(1, col.r * 1.25 + 0.05),
                       Math.min(1, col.g * 1.25 + 0.05),
                       Math.min(1, col.b * 1.25 + 0.05), 1),
            b: Qt.rgba(col.r * 0.55, col.g * 0.55, col.b * 0.55, 1)
        }
    }

    // ---- Internal: stable hash of a string ----
    function _hash(name) {
        var s = (name === undefined || name === null) ? "" : String(name)
        var h = 2166136261
        for (var i = 0; i < s.length; i++) {
            h ^= s.charCodeAt(i)
            h = (h * 16777619) >>> 0
        }
        return h >>> 0
    }

    // ---- Internal: known per-game brand gradient pairs [A, B] ----
    readonly property var _covers: {
        "Valorant": ["#ff4655", "#0f1923"],
        "Fortnite": ["#2ec8ff", "#9b3cff"],
        "League of Legends": ["#0a4d8f", "#001f3f"],
        "Counter-Strike 2": ["#f4a000", "#262626"],
        "Apex Legends": ["#ff4135", "#1a1a1a"],
        "Call of Duty": ["#7a5a00", "#0d0d0d"],
        "Dota 2": ["#a92900", "#1a1a1a"],
        "Elden Ring": ["#c89d49", "#2a1a0a"],
        "GTA V": ["#ffce4a", "#000000"],
        "Rocket League": ["#0050ff", "#ff5e00"],
        "FIFA 26": ["#00d2ff", "#3a47d5"],
        "Minecraft": ["#5d8a3a", "#2c4a1a"],
        "Diablo IV": ["#a40000", "#1a0000"],
        "Cyberpunk 2077": ["#fcee0a", "#000000"],
        "Baldur's Gate 3": ["#5a3a1f", "#1a0d05"],
        "Red Dead 2": ["#a13a00", "#0d0d0d"],
        "Overwatch 2": ["#ff8a00", "#1a1f3c"]
    }

    // ---- Internal: tasteful neon-dark hue set for unknown titles (saturated stop A) ----
    readonly property var _paletteA: [
        "#00e5ff", "#ff3d9a", "#7a3cff", "#00c2a8",
        "#ff6a00", "#3a7bff", "#e0004d", "#9d00ff",
        "#00b0ff", "#ff2e7e", "#00d47a", "#ffab00"
    ]
    // ---- Internal: matching dark stop B, deep and desaturated ----
    readonly property var _paletteB: [
        "#041826", "#1a0512", "#0f0524", "#03170f",
        "#1a0a00", "#050f24", "#1a0008", "#100024",
        "#02121f", "#1a0410", "#021a10", "#1a1200"
    ]

    // ---- New: per-game cover gradient stop A ----
    function coverA(name) {
        var key = (name === undefined || name === null) ? "" : String(name)
        if (_covers.hasOwnProperty(key))
            return _covers[key][0]
        var h = _hash(key)
        return _paletteA[h % _paletteA.length]
    }

    // ---- New: per-game cover gradient stop B ----
    function coverB(name) {
        var key = (name === undefined || name === null) ? "" : String(name)
        if (_covers.hasOwnProperty(key))
            return _covers[key][1]
        var h = _hash(key)
        // rotate B index so A and B rarely align, keeping pairs varied
        return _paletteB[(h + 5) % _paletteB.length]
    }

    // ---- New: brand logo per game/app (simpleicons svg in qml/icons; "" = use letter) ----
    readonly property var _icons: {
        "Valorant": "valorant", "Fortnite": "fortnite",
        "Apex Legends": "apexlegends", "Call of Duty": "callofduty", "Overwatch 2": "overwatch2",
        "League of Legends": "leagueoflegends", "Dota 2": "dota2",
        "Minecraft": "minecraft", "GTA V": "gtav",
        "Rocket League": "rocketleague", "FIFA 26": "fc26", "ARC Raiders": "arcraiders",
        "Chrome": "googlechrome", "YouTube": "youtube", "Spotify": "spotify",
        "Discord": "discord", "Steam": "steam",
        "Epic Games": "epicgames", "EA Play": "ea", "Riot Client": "riotgames"
    }
    function iconFor(name) {
        var key = (name === undefined || name === null) ? "" : String(name)
        return _icons.hasOwnProperty(key) ? ("icons/" + _icons[key] + ".png") : ""
    }

    // ---- Existing: clock -> "H:MM:SS" (preserved behavior) ----
    function clock(secs) {
        var s = Math.max(0, Math.floor(secs))
        var h = Math.floor(s / 3600)
        var m = Math.floor((s % 3600) / 60)
        var sec = s % 60
        var mm = (m < 10 ? "0" : "") + m
        var ss = (sec < 10 ? "0" : "") + sec
        return h + ":" + mm + ":" + ss
    }

    // ---- Existing: hm -> "Hh MMm" or "Mm" (preserved behavior) ----
    function hm(secs) {
        var s = Math.max(0, Math.floor(secs))
        var h = Math.floor(s / 3600)
        var m = Math.floor((s % 3600) / 60)
        if (h > 0) {
            var mm = (m < 10 ? "0" : "") + m
            return h + "h " + mm + "m"
        }
        return m + "m"
    }
}
