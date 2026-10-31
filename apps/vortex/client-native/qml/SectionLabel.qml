import QtQuick

// The // COMMENT-STYLE label used throughout Vortex — a neon marker.
// The crisp accent text sits on top of a faint accent halo built from offset
// copies (renders in the offscreen software grab; no shader required).
Text {
    id: lbl
    property color accent: Theme.cyan
    property string label: ""
    text: "// " + label
    color: accent
    font.family: Theme.fontMono
    font.pixelSize: 11
    font.letterSpacing: 2.5
    font.capitalization: Font.AllUppercase

    // Faint accent glow: low-alpha copies smeared around the glyphs, drawn behind
    // the crisp text (negative z renders below the parent's own content).
    Repeater {
        model: [
            { dx: -1.4, dy:  0.0, a: 0.22 },
            { dx:  1.4, dy:  0.0, a: 0.22 },
            { dx:  0.0, dy: -1.4, a: 0.22 },
            { dx:  0.0, dy:  1.4, a: 0.22 },
            { dx: -1.0, dy: -1.0, a: 0.14 },
            { dx:  1.0, dy: -1.0, a: 0.14 },
            { dx: -1.0, dy:  1.0, a: 0.14 },
            { dx:  1.0, dy:  1.0, a: 0.14 }
        ]
        delegate: Text {
            required property var modelData
            z: -1
            x: modelData.dx
            y: modelData.dy
            text: lbl.text
            font: lbl.font
            color: lbl.accent
            opacity: modelData.a
        }
    }
}
