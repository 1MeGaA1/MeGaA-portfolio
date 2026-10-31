import QtQuick
import "."

// Zoomed waveform around the clip: drag the cyan handles to trim (they snap to word edges,
// hold Alt to stop snapping), click anywhere to seek. Once the clip is split (razor), a click also picks
// the part under it, and a double-click or right-click on a split line removes that line.
Item {
    id: strip
    signal seek(real t)

    property real hoverSplit: -1   // the split line under the mouse (source seconds), -1 = none
    // what the line under the mouse can do (the razor row shows it)
    readonly property string hint: hoverSplit < 0 ? ""
        : Store.splitRemovable(hoverSplit) ? "Double-click the line to remove it" : "Restore the deleted part first"

    property var dragWindow: null
    // the visible time window: the clip with some air around it, else 30 s around the playhead
    readonly property var view: dragWindow || computeWindow()

    function computeWindow() {
        const dur = Store.duration || 1
        let a, b
        if (Store.inT !== null && Store.outT !== null && Store.outT > Store.inT) {
            const pad = Math.max(2, (Store.outT - Store.inT) * 0.25)
            a = Store.inT - pad
            b = Store.outT + pad
        } else {
            a = Store.playhead - 15
            b = Store.playhead + 15
        }
        const span = Math.min(b - a, dur)
        if (a < 0) { a = 0; b = span }
        if (b > dur) { b = dur; a = Math.max(0, dur - span) }
        return [a, b]
    }

    function xOf(t) { return (t - view[0]) / (view[1] - view[0]) * width }

    function snapTime(t, which) {
        const list = which === "in" ? Store.wordStarts : Store.wordEnds
        if (!list.length) return t
        const i = Store.lastAtOrBefore(list, t, v => v)
        let best = t, bestD = 0.25
        for (const j of [i, i + 1]) {
            if (j < 0 || j >= list.length) continue
            const target = which === "in" ? list[j] - 0.05 : list[j] + 0.1
            if (Math.abs(target - t) < bestD) { best = target; bestD = Math.abs(target - t) }
        }
        return best
    }

    // the split line within 5 px of x (source seconds), or -1
    function splitNear(x) {
        for (const p of Store.parts.slice(1)) if (Math.abs(xOf(p[0]) - x) < 5) return p[0]
        return -1
    }

    // the handle within 9 px of x, unless a split line is nearer (a line can sit right next to In / Out): "in" / "out"
    // or "seek"
    function handleAt(x) {
        const dist = t => t === null ? Infinity : Math.abs(xOf(t) - x)
        const line = splitNear(x), lineDist = line >= 0 ? dist(line) : Infinity
        if (dist(Store.inT) < 9 && dist(Store.inT) < lineDist) return "in"
        if (dist(Store.outT) < 9 && dist(Store.outT) < lineDist) return "out"
        return "seek"
    }

    Rectangle { anchors.fill: parent; radius: 10; color: Theme.field; border.color: Theme.line }
    Connections { target: Store; function onPartsChanged() { strip.hoverSplit = -1 } }

    Canvas {
        id: wave
        anchors.fill: parent
        property var sig: [strip.view, Store.inT, Store.outT, Store.peaksStamp, width, height, Store.editKey, Store.parts,
                           Store.selectedPart, strip.hoverSplit]
        onSigChanged: requestPaint()

        onPaint: {
            const c = getContext("2d")
            c.reset()
            c.clearRect(0, 0, width, height)
            if (!Store.duration) return
            const w = width, h = height
            const a = strip.view[0], b = strip.view[1]
            const X = t => (t - a) / (b - a) * w
            const inT = Store.inT, outT = Store.outT
            const hasRange = inT !== null && outT !== null && outT > inT
            const ed = hasRange ? Store.editState() : null
            const segs = ed && ed.segs ? ed.segs : []
            const intro = ed ? ed.intro : null
            c.fillStyle = "#8b5cff"   // muted words: violet bar along the bottom
            for (const m of Store.mutes) if (m[1] > a && m[0] < b) c.fillRect(X(m[0]), h - 4, Math.max(2, X(m[1]) - X(m[0])), 4)
            if (intro && intro[1] > a && intro[0] < b) {   // the teaser: amber band with a top marker
                c.fillStyle = "rgba(255,181,71,0.14)"
                c.fillRect(X(intro[0]), 0, X(intro[1]) - X(intro[0]), h)
                c.fillStyle = "#ffb547"
                c.fillRect(X(intro[0]), 0, X(intro[1]) - X(intro[0]), 3)
            }
            if (hasRange) {
                c.fillStyle = "rgba(0,229,255,0.07)"
                c.fillRect(X(inT), 0, X(outT) - X(inT), h)
                let prev = inT   // parts cut out of the clip: red wash
                c.fillStyle = "rgba(255,77,109,0.13)"
                for (const sg of segs.concat([[outT, outT]])) {
                    if (sg[0] - prev > 0.02) c.fillRect(X(prev), 0, X(sg[0]) - X(prev), h)
                    prev = Math.max(prev, sg[1])
                }
            }
            const mid = h / 2
            const peaks = Store.peaks
            if (peaks) {
                const bar = 2, gap = 1, n = Math.floor(w / (bar + gap))
                const rate = Store.peakRate
                for (let i = 0; i < n; i++) {
                    const t0 = a + (i / n) * (b - a), t1 = a + ((i + 1) / n) * (b - a)
                    const p0 = Math.floor(t0 * rate), p1 = Math.max(p0 + 1, Math.floor(t1 * rate))
                    let peak = 0
                    for (let q = p0; q < p1 && q < peaks.length; q++) if (peaks[q] > peak) peak = peaks[q]
                    const amp = (peak / 255) * h * 0.4 + 1
                    const tm = (t0 + t1) / 2
                    let color = "rgba(123,138,169,0.42)"
                    if (hasRange && tm >= inT && tm <= outT) {
                        const piece = segs.find(sg => tm >= sg[0] && tm <= sg[1])
                        color = !piece ? "rgba(255,77,109,0.55)" : piece[2] !== 1 ? "#a78bff" : "#00e5ff"
                    }
                    c.fillStyle = color
                    c.fillRect(i * (bar + gap), mid - amp, bar, amp * 2)
                }
            } else {
                c.fillStyle = "rgba(123,138,169,0.25)"
                c.fillRect(0, mid - 0.5, w, 1)
            }
            if (hasRange) {   // parts deleted with the razor: red stripes over the red wash
                c.strokeStyle = "rgba(255,77,109,0.4)"
                c.lineWidth = 1.5
                for (const d of Store.drops) {
                    const x0 = X(Math.max(d[0], inT)), x1 = X(Math.min(d[1], outT))
                    if (x1 - x0 < 1) continue
                    c.save()
                    c.beginPath()
                    c.rect(x0, 0, x1 - x0, h)
                    c.clip()
                    c.beginPath()
                    for (let x = x0 - h; x < x1; x += 8) { c.moveTo(x, h); c.lineTo(x + h, 0) }
                    c.stroke()
                    c.restore()
                }
            }
            const parts = hasRange ? Store.parts : []
            const sel = parts[Store.selectedPart]
            if (sel) {   // the picked part: white frame (a lone part can be picked only while it is deleted)
                c.fillStyle = "rgba(232,241,255,0.06)"
                c.fillRect(X(sel[0]), 0, X(sel[1]) - X(sel[0]), h)
                c.strokeStyle = "#e8f1ff"
                c.lineWidth = 2
                c.beginPath()
                c.roundedRect(X(sel[0]) + 1, 1, Math.max(2, X(sel[1]) - X(sel[0]) - 2), h - 2, 4, 4)
                c.stroke()
            }
            if (parts.length > 1) {
                for (const p of parts.slice(1)) {   // split lines: white, with a razor notch on top
                    const x = X(p[0]), hot = Math.abs(p[0] - strip.hoverSplit) < 0.001
                    c.fillStyle = hot ? "#ffffff" : "rgba(232,241,255,0.8)"
                    c.fillRect(x - (hot ? 1.5 : 0.75), 0, hot ? 3 : 1.5, h)
                    c.beginPath()
                    c.moveTo(x - 6, 0)
                    c.lineTo(x + 6, 0)
                    c.lineTo(x, 8)
                    c.closePath()
                    c.fill()
                }
            }
            if (hasRange) {
                for (const pair of [[inT, 1], [outT, -1]]) {
                    const x = X(pair[0])
                    c.shadowColor = "#00e5ff"
                    c.shadowBlur = 10
                    c.fillStyle = "#00e5ff"
                    c.fillRect(x - 1, 0, 2, h)
                    c.shadowBlur = 0
                    c.beginPath()
                    c.roundedRect(pair[1] > 0 ? x : x - 10, 0, 10, 18, 3, 3)
                    c.fill()
                }
            }
            c.font = `10px "${Theme.mono}"`
            c.fillStyle = "rgba(123,138,169,0.9)"
            c.textBaseline = "bottom"
            c.textAlign = "left"
            c.fillText(Store.fmt(a), 6, h - 4)
            c.textAlign = "right"
            c.fillText(Store.fmt(b), w - 6, h - 4)
        }
    }

    // playhead (outside the window it would be drawn over the panels next to the strip)
    Rectangle {
        visible: Store.duration > 0 && Store.playhead >= strip.view[0] && Store.playhead <= strip.view[1]
        x: strip.xOf(Store.playhead) - 1
        width: 2
        height: parent.height
        color: Theme.magenta
        Rectangle { anchors.centerIn: parent; width: 6; height: parent.height; color: Theme.magenta; opacity: 0.18 }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        // the handle under the press ("in" / "out", else "seek") trims only once the mouse moves 3 px: a click there
        // seeks and picks the part like anywhere else (a short part next to In / Out too), and a double-click on a
        // line right by a handle never trims
        property string mode: "seek"      // what the drag does: "seek" (scrub) or "in" / "out" (trim)
        property string grab: "seek"
        property real pressX: 0
        property bool allGone: false      // every part was deleted already when the trim started
        cursorShape: pressed ? (mode === "seek" && grab === "seek" ? Qt.CrossCursor : Qt.SizeHorCursor)
                             : (containsMouse && strip.handleAt(mouseX) !== "seek" ? Qt.SizeHorCursor
                                : strip.hoverSplit >= 0 ? Qt.PointingHandCursor : Qt.CrossCursor)

        function apply(mouse) {
            const a = strip.dragWindow[0], b = strip.dragWindow[1]
            let t = Store.clamp(a + mouse.x / strip.width * (b - a), 0, Store.duration)
            if (mode === "seek") { strip.seek(t); return }
            if (!(mouse.modifiers & Qt.AltModifier)) t = strip.snapTime(t, mode)
            if (mode === "in") Store.setRange(Math.min(t, Store.outT - 0.3), Store.outT)
            else Store.setRange(Store.inT, Math.max(t, Store.inT + 0.3))
            strip.seek(mode === "in" ? Store.inT : Store.outT)
        }
        onPressed: (mouse) => {
            if (!Store.duration) return
            Store.releaseFocus()
            if (mouse.button === Qt.RightButton) {
                const line = strip.splitNear(mouse.x)
                if (line >= 0) { Store.removeSplit(line); strip.hoverSplit = -1 }
                mouse.accepted = false
                return
            }
            mode = "seek"
            grab = strip.handleAt(mouse.x)
            pressX = mouse.x
            strip.dragWindow = strip.view.slice()
            apply(mouse)
            // pick the part under the click (none outside the clip)
            const a = strip.dragWindow[0], b = strip.dragWindow[1]
            Store.selectPart(Store.partAt(a + mouse.x / strip.width * (b - a)))
        }
        onDoubleClicked: (mouse) => {
            const line = mouse.button === Qt.LeftButton ? strip.splitNear(mouse.x) : -1
            if (line >= 0) { Store.removeSplit(line); strip.hoverSplit = -1 }
        }
        onPositionChanged: (mouse) => {
            if (pressed && strip.dragWindow) {
                if (mode === "seek" && grab !== "seek" && Math.abs(mouse.x - pressX) > 3) {
                    mode = grab
                    allGone = Store.allPartsRemoved()
                }
                apply(mouse)
            }
            else if (!pressed) strip.hoverSplit = strip.handleAt(mouse.x) === "seek" ? strip.splitNear(mouse.x) : -1
        }
        onExited: strip.hoverSplit = -1
        onReleased: {
            // the trim went past the last part that was kept (the RazorBar says so too)
            if (mode !== "seek" && !allGone && Store.allPartsRemoved())
                Store.toast("Every part of the clip is deleted now. Pick one and press Delete to restore it.", "info")
            strip.dragWindow = null
        }
        onCanceled: strip.dragWindow = null
    }
}
