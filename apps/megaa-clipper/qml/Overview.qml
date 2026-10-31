import QtQuick
import "."

// The whole video at a glance: waveform, queued clips (violet), the current clip (cyan)
// and the strip's window (white frame). Click or drag to seek.
Item {
    id: ov
    signal seek(real t)
    property var view: [0, 0]   // the strip's visible window
    property var bins: null

    function xOf(t) { return Store.duration ? t / Store.duration * width : 0 }

    // one peak per pixel column, recomputed only when the peaks or the width change
    function computeBins() {
        const peaks = Store.peaks
        const w = Math.max(1, Math.round(width))
        if (!peaks) { bins = null; return }
        const out = new Array(w).fill(0)
        const per = peaks.length / w
        for (let x = 0; x < w; x++) {
            const from = Math.floor(x * per), to = Math.max(from + 1, Math.floor((x + 1) * per))
            let peak = 0
            for (let q = from; q < to && q < peaks.length; q++) if (peaks[q] > peak) peak = peaks[q]
            out[x] = peak
        }
        bins = out
    }

    onWidthChanged: computeBins()
    Connections { target: Store; function onPeaksChanged() { ov.computeBins() } }

    Canvas {
        id: canvas
        anchors.fill: parent
        property var sig: [ov.bins, Store.clipsSig, Store.inT, Store.outT, ov.view, width, height, Store.editKey]
        onSigChanged: requestPaint()
        onPaint: {
            const c = getContext("2d")
            c.reset()
            c.clearRect(0, 0, width, height)
            const w = width, h = height
            c.fillStyle = "rgba(130,170,255,0.07)"
            c.beginPath()
            c.roundedRect(0, 0, w, h, 4, 4)
            c.fill()
            if (!Store.duration) return
            const X = t => t / Store.duration * w
            if (ov.bins) {
                c.fillStyle = "rgba(123,138,169,0.35)"
                const scale = w / ov.bins.length
                for (let x = 0; x < ov.bins.length; x++) {
                    const amp = ov.bins[x] / 255 * (h - 4)
                    c.fillRect(x * scale, (h - amp) / 2, Math.max(1, scale), amp)
                }
            }
            c.fillStyle = "rgba(139,92,255,0.7)"
            for (const clip of Store.clips) c.fillRect(X(clip.start), 0, Math.max(2, X(clip.end) - X(clip.start)), h)
            if (Store.inT !== null && Store.outT !== null) {
                c.fillStyle = "rgba(0,229,255,0.55)"
                c.fillRect(X(Store.inT), 0, Math.max(2, X(Store.outT) - X(Store.inT)), h)
            }
            const intro = Store.edit.intro
            if (intro) {   // the teaser
                c.fillStyle = "#ffb547"
                c.fillRect(X(intro[0]), 0, Math.max(2, X(intro[1]) - X(intro[0])), h)
            }
            c.strokeStyle = "rgba(232,241,255,0.4)"
            c.lineWidth = 1
            c.strokeRect(X(ov.view[0]) + 0.5, 0.5, Math.max(2, X(ov.view[1]) - X(ov.view[0])) - 1, h - 1)
        }
    }

    Rectangle {
        visible: Store.duration > 0
        x: ov.xOf(Store.playhead) - 1
        width: 2
        height: parent.height
        color: Theme.magenta
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onPressed: (mouse) => { Store.releaseFocus(); ov.seek(Store.clamp(mouse.x / width, 0, 1) * Store.duration) }
        onPositionChanged: (mouse) => { if (pressed) ov.seek(Store.clamp(mouse.x / width, 0, 1) * Store.duration) }
    }
}
