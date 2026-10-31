import QtQuick
import "."

// Captions, hook title and safe zones drawn over the preview – ported from the web edition's
// drawCaptions / drawHook (same look as the ASS subtitles the engine burns in).
// Everything is drawn in a 540×960 frame (half the 1080×1920 output) and scaled to the phone.
Canvas {
    id: overlay
    readonly property real cw: 540
    readonly property real ch: 960
    readonly property real k: 0.5   // preview pixels per output pixel

    property var hit: null          // caption chunk on screen: {words, active, start, dt}
    property string emoji: ""
    property real emojiTop: 0
    property string lastSig: ""
    property bool hookOn: false
    property bool flashOn: false        // the white flash where the teaser ends
    property real progressFrac: -1      // progress bar fill 0..1; -1 = no bar
    property bool teaserOn: false       // the TEASER label while the teaser plays
    readonly property real unit: width / cw   // phone pixels per 540-frame pixel
    property var cellCache: ({})

    FontMetrics { id: metrics }

    // libass sizes a font so its ascent + descent (the line cell, not the em) equals the ASS font size;
    // the canvas sizes by em, so draw at size * cellScale to get the same letters as the render
    function cellScale(family, bold) {
        const key = family + (bold ? "|b" : "")
        let f = cellCache[key]
        if (f === undefined) {
            metrics.font = Qt.font({ family: family, pixelSize: 200, bold: !!bold })
            const h = metrics.ascent + metrics.descent
            f = h > 0 ? 200 / h : 1
            cellCache[key] = f
        }
        return f
    }

    // called every tick by the stage with the source time t, the clip time out (null outside the clip) and
    // Store.editState(); repaints the canvas only when something it draws changed – web: drawPreview()
    function refresh(t, out, ed) {
        const inClip = out !== null
        const tt = inClip ? out : t     // inside the clip, captions follow the edited timeline
        const st = Store.effectiveStyle()
        let h = null
        if (st && Store.words.length && Store.captionsOn) {
            const timeline = inClip ? Store.timelineFor(st, ed.words, ed.timelines) : Store.timelineFor(st)
            const found = Store.captionAt(tt, timeline)
            if (found) h = { words: found.words, active: found.active, start: found.words[0].s }
        }
        const hs = Store.effectiveHook()
        const hookText = Store.hookText.trim()
        const showHook = !!(hookText && hs && !(inClip && hs.duration && out > hs.duration))  // hook time is clip time
        // cheap per-tick layers (plain items, no repaint): flash, progress bar, TEASER label
        const cutAt = inClip && ed.intro ? ed.introLen / ed.speed : -1
        const flash = inClip && !!ed.intro && Store.edit.introFlash && out >= cutAt - 0.04 && out <= cutAt + 0.1
        if (flash !== flashOn) flashOn = flash
        const frac = Store.edit.progress && inClip && ed.duration ? Store.clamp(out / ed.duration, 0, 1) : -1
        if (Math.abs(frac - progressFrac) > 0.0005) progressFrac = frac
        const teaser = Store.inIntro && inClip
        if (teaser !== teaserOn) teaserOn = teaser

        const dt = h ? tt - h.start : 1
        const popPhase = dt < 0.09 ? Math.round(dt * 100) : -1
        const sig = JSON.stringify([width, height, inClip ? ed.serial : -1, h ? h.start : -1, h ? h.active : -1, popPhase, st,
                                    Store.kw, showHook ? hookText : "", showHook ? hs : null, Store.transcriptVersion])
        if (sig === lastSig) return
        lastSig = sig
        hit = h ? Object.assign({}, h, { dt: dt }) : null
        hookOn = showHook
        requestPaint()
    }

    onWidthChanged: lastSig = ""
    onHeightChanged: lastSig = ""

    // same order as the web edition: captions (+ emoji), hook; then the item layers below (watermark on its own)
    onPaint: {
        const ctx = getContext("2d")
        ctx.reset()
        ctx.clearRect(0, 0, width, height)
        ctx.scale(width / cw, height / ch)
        let emojiNow = ""
        if (hit) emojiNow = drawCaptions(ctx, hit, Store.effectiveStyle())
        if (hookOn) drawHook(ctx, Store.hookText.trim(), Store.effectiveHook())
        emoji = emojiNow
    }

    // the watermark – mirrors the ASS "Mark" style (Segoe UI Semibold 38, margins 50 / 70) – web: drawWatermark().
    // libass fills the letters straight over the video, so they are cut out of the outline first (own layer).
    function drawWatermark(ctx, text, pos) {
        text = text.replace(/\n/g, " ").replace(/[{}\\]/g, "").trim()   // build_ass: clean_word(watermark)
        if (!text) return
        const size = 38 * k * cellScale("Segoe UI Semibold", false), mx = 50 * k, my = 70 * k
        ctx.save()
        ctx.font = `600 ${size.toFixed(1)}px "Segoe UI Semibold"`
        ctx.textAlign = pos[1] === "l" ? "left" : "right"
        ctx.textBaseline = pos[0] === "t" ? "top" : "bottom"
        const x = pos[1] === "l" ? mx : cw - mx, y = pos[0] === "t" ? my : ch - my
        ctx.lineWidth = 4 * k
        ctx.strokeStyle = "rgba(0,0,0,0.6)"   // OutlineColour &H66000000 = 60 % black (ASS alpha 0x66 is 40 % clear)
        ctx.strokeText(text, x, y)
        ctx.globalCompositeOperation = "destination-out"
        ctx.fillStyle = "black"
        ctx.fillText(text, x, y)
        ctx.globalCompositeOperation = "source-over"
        ctx.fillStyle = "rgba(255,255,255,0.8)"
        ctx.fillText(text, x, y)
        ctx.restore()
    }

    function fontFor(st, px) {
        return `${st.bold ? "bold " : ""}${Math.max(1, px).toFixed(1)}px "${st.font}"`
    }

    function drawCaptions(ctx, hit, st) {
        const active = hit.active
        const texts = hit.words.map(w => (st.uppercase ? w.w.toUpperCase() : w.w))
        const size = st.size * k                          // the ASS size = line cell height
        const em = size * cellScale(st.font, st.bold)
        const grow = i => (st.mode === "word" && i === active ? st.active_scale : 1)
        const fontAt = i => fontFor(st, em * grow(i))

        // measure, then wrap into lines that fit (libass wraps the same way)
        ctx.font = fontFor(st, em)
        const space = ctx.measureText(" ").width
        const widths = texts.map((tx, i) => { ctx.font = fontAt(i); return ctx.measureText(tx).width })
        const maxW = cw - 120 * k
        const rows = []
        let line = [], lineW = 0
        texts.forEach((_, i) => {
            const add = (line.length ? space : 0) + widths[i]
            if (line.length && lineW + add > maxW) { rows.push({ idx: line, w: lineW }); line = []; lineW = 0 }
            lineW += (line.length ? space : 0) + widths[i]
            line.push(i)
        })
        if (line.length) rows.push({ idx: line, w: lineW })
        rebalance(rows.map(r => r.idx), widths, space).forEach((idx, r) => {
            rows[r].idx = idx
            rows[r].w = rowWidth(idx, widths, space)
        })

        const dt = hit.dt
        const pop = active === 0 && st.pop !== 1 && st.active_scale === 1 && dt < 0.09 ? st.pop - (st.pop - 1) * (dt / 0.09) : 1
        const lineH = size
        const placed = []
        rows.forEach((ln, r) => {
            let x = -ln.w / 2
            const y = -(rows.length - 1 - r) * lineH
            for (const i of ln.idx) { placed.push({ i: i, x: x, y: y }); x += widths[i] + space }
        })

        ctx.save()
        ctx.translate(cw / 2, ch - st.margin_v * k)
        ctx.scale(pop, pop)
        ctx.textBaseline = "bottom"
        ctx.textAlign = "left"
        ctx.lineJoin = "round"
        const outlineW = st.outline * 2 * k
        const isBoxed = i => st.mode === "box" && i === active
        if (st.shadow) {
            const off = st.shadow * k
            ctx.fillStyle = "rgba(0,0,0,0.5)"
            ctx.strokeStyle = "rgba(0,0,0,0.5)"
            ctx.lineWidth = outlineW
            for (const p of placed) {
                ctx.font = fontAt(p.i)
                if (st.outline) ctx.strokeText(texts[p.i], p.x + off, p.y + off)
                ctx.fillText(texts[p.i], p.x + off, p.y + off)
            }
        }
        for (const p of placed) {
            if (!isBoxed(p.i)) continue
            const s = em * grow(p.i)
            const pad = st.box_pad * k
            ctx.fillStyle = st.accent
            ctx.beginPath()
            ctx.roundedRect(p.x - pad, p.y - s * 0.93 - pad, widths[p.i] + pad * 2, s * 0.74 + pad * 2, pad, pad)
            ctx.fill()
        }
        if (st.outline) {
            ctx.strokeStyle = st.outline_color
            ctx.lineWidth = outlineW
            if (st.glow) { ctx.shadowColor = st.outline_color; ctx.shadowBlur = st.glow * k * 2.4 }
            for (const p of placed) {
                if (isBoxed(p.i)) continue
                ctx.font = fontAt(p.i)
                ctx.strokeText(texts[p.i], p.x, p.y)
            }
            ctx.shadowBlur = 0
            ctx.shadowColor = "transparent"
        }
        for (const p of placed) {
            const lit = (st.mode === "word" && p.i === active) || (st.mode === "fill" && p.i <= active)
            const boxed = isBoxed(p.i)
            const keyword = Store.kw.on && !lit && !boxed && Store.keywordEmoji(texts[p.i])[0]
            ctx.fillStyle = lit ? st.accent : keyword ? Store.kw.color : st.text
            ctx.font = fontAt(p.i)
            ctx.fillText(texts[p.i], p.x, p.y)
        }
        ctx.restore()

        // keyword emoji above the captions – same place clipper.render_clip puts it
        if (!Store.kw.emojis) return ""
        const found = texts.map(tx => Store.keywordEmoji(tx)[1]).find(Boolean) || ""
        if (found) {
            const box = Store.emojiSize * k
            emojiTop = ch - st.margin_v * k - st.size * k * 1.25 - box - 10 * k
        }
        return found
    }

    function rowWidth(idx, widths, space) {
        return idx.reduce((sum, i, n) => sum + widths[i] + (n ? space : 0), 0)
    }

    // libass "smart" wrapping (WrapStyle 0): after the greedy wrap, the last word of a line moves down
    // while that brings the two lines closer in width (the upper line ends up the wider one)
    function rebalance(rows, widths, space) {
        for (let r = 0; r + 1 < rows.length; r++) {
            while (rows[r].length > 1) {
                const last = rows[r][rows[r].length - 1]
                const before = Math.abs(rowWidth(rows[r], widths, space) - rowWidth(rows[r + 1], widths, space))
                const after = Math.abs(rowWidth(rows[r].slice(0, -1), widths, space)
                                       - rowWidth([last].concat(rows[r + 1]), widths, space))
                if (after >= before) break
                rows[r + 1].unshift(rows[r].pop())
            }
        }
        return rows
    }

    function wrapText(ctx, text, maxW) {
        const list = text.split(/\s+/).filter(Boolean)
        const widths = list.map(w => ctx.measureText(w).width)
        const space = ctx.measureText(" ").width
        const rows = []
        let line = []
        list.forEach((_, i) => {
            if (line.length && rowWidth(line.concat([i]), widths, space) > maxW) { rows.push(line); line = [] }
            line.push(i)
        })
        if (line.length) rows.push(line)
        return rebalance(rows, widths, space).map(idx => idx.map(i => list[i]).join(" "))
    }

    // the hook title – mirrors clipper.hook_style_line (box = solid box per line, outline = stroked text)
    function drawHook(ctx, text, hs) {
        const size = hs.size * k, lineH = size, top = hs.margin_v * k   // size = line cell, like libass
        const em = size * cellScale(hs.font, false)
        const boxed = hs.mode === "box"
        const pad = boxed ? hs.pad * k : 0
        ctx.save()
        ctx.font = `${em.toFixed(1)}px "${hs.font}"`
        ctx.textBaseline = "top"
        ctx.textAlign = "center"
        ctx.lineJoin = "round"
        const rows = wrapText(ctx, hs.uppercase ? text.toUpperCase() : text, cw - 180 * k - pad * 2)
        const ys = rows.map((_, i) => top + i * lineH)
        if (boxed) {
            ctx.fillStyle = hs.box
            rows.forEach((line, i) => {
                const w = ctx.measureText(line).width
                ctx.fillRect(cw / 2 - w / 2 - pad, top + i * lineH - pad, w + pad * 2, size + pad * 2)
            })
        } else {
            const outlineW = hs.outline * 2 * k
            if (hs.shadow) {
                ctx.fillStyle = "rgba(0,0,0,0.5)"
                ctx.strokeStyle = "rgba(0,0,0,0.5)"
                ctx.lineWidth = outlineW
                rows.forEach((line, i) => {
                    ctx.strokeText(line, cw / 2 + hs.shadow * k, ys[i] + hs.shadow * k)
                    ctx.fillText(line, cw / 2 + hs.shadow * k, ys[i] + hs.shadow * k)
                })
            }
            if (hs.outline) {
                ctx.strokeStyle = hs.outline_color
                ctx.lineWidth = outlineW
                if (hs.glow) { ctx.shadowColor = hs.outline_color; ctx.shadowBlur = hs.glow * k * 2.4 }
                rows.forEach((line, i) => ctx.strokeText(line, cw / 2, ys[i]))
                ctx.shadowBlur = 0
                ctx.shadowColor = "transparent"
            }
        }
        ctx.fillStyle = hs.text
        rows.forEach((line, i) => ctx.fillText(line, cw / 2, ys[i]))
        ctx.restore()
    }

    function drawSafeZones(ctx) {
        const zones = [[0, 0, 1080, 160], [0, 1600, 1080, 320], [930, 760, 150, 840]]
        ctx.save()
        ctx.fillStyle = "rgba(255,43,214,0.16)"
        ctx.strokeStyle = "rgba(255,43,214,0.75)"
        ctx.lineWidth = 1.5
        for (const z of zones) {
            ctx.fillRect(z[0] * k, z[1] * k, z[2] * k, z[3] * k)
            ctx.strokeRect(z[0] * k + 0.75, z[1] * k + 0.75, z[2] * k - 1.5, z[3] * k - 1.5)
        }
        ctx.fillStyle = "rgba(255,170,240,0.95)"
        ctx.font = `bold 11px "${Theme.mono}"`
        ctx.textBaseline = "top"
        ctx.textAlign = "left"
        ctx.fillText("APP UI COVERS THIS", 10, 1610 * k)
        ctx.restore()
    }

    // keyword emoji: the engine's own PNG (same picture as the render), else the emoji font
    Item {
        visible: overlay.emoji !== ""
        readonly property real box: Store.emojiSize * overlay.k * overlay.width / overlay.cw
        width: box
        height: box
        x: (overlay.width - box) / 2
        y: overlay.emojiTop * overlay.height / overlay.ch
        Image {
            id: emojiPng
            anchors.fill: parent
            source: overlay.emoji ? backend.emojiUrl(overlay.emoji) : ""
            smooth: true
            mipmap: true
        }
        Text {
            anchors.centerIn: parent
            visible: emojiPng.status !== Image.Ready
            text: overlay.emoji
            font.family: "Segoe UI Emoji"
            font.pixelSize: parent.box * 0.86
        }
    }

    // the watermark above the captions and hook (ASS layer 2), under the flash and the bar like the render
    Canvas {
        id: markLayer
        anchors.fill: parent
        readonly property string text: Store.edit.watermark
        readonly property string pos: Store.edit.watermarkPos
        visible: text !== ""
        onTextChanged: requestPaint()
        onPosChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            ctx.clearRect(0, 0, width, height)
            ctx.scale(width / overlay.cw, height / overlay.ch)
            if (text) overlay.drawWatermark(ctx, text, pos)
        }
    }

    // the white flash where the teaser ends (render: drawbox white@0.85 from cut-0.04 to cut+0.1)
    Rectangle {
        anchors.fill: parent
        visible: overlay.flashOn
        color: Qt.rgba(1, 1, 1, 0.85)
    }

    // progress bar: 16 output px along the bottom, growing over the finished clip's length
    Rectangle {
        visible: overlay.progressFrac >= 0
        x: 0
        height: 16 * overlay.k * overlay.unit
        y: overlay.height - height
        width: overlay.width * Math.max(0, overlay.progressFrac)
        color: Store.edit.progressColor
    }

    // "▶ TEASER" while the teaser plays (preview only)
    Text {
        visible: overlay.teaserOn
        anchors.horizontalCenter: parent.horizontalCenter
        y: 40 * overlay.unit
        text: String.fromCharCode(0x25B6) + " TEASER"
        color: Qt.rgba(1, 181 / 255, 71 / 255, 0.95)
        font.family: Theme.mono
        font.pixelSize: Math.max(1, Math.round(11 * overlay.unit))
        font.weight: Font.DemiBold
    }

    // safe zones on top of everything (web: drawSafeZones last)
    Canvas {
        id: safeLayer
        anchors.fill: parent
        visible: Store.safe
        onVisibleChanged: if (visible) requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            ctx.clearRect(0, 0, width, height)
            ctx.scale(width / overlay.cw, height / overlay.ch)
            overlay.drawSafeZones(ctx)
        }
    }
}
