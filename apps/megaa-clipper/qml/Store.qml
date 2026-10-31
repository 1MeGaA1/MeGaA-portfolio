pragma Singleton
import QtQuick

// Editor state + logic shared by every view (the QML twin of the web edition's app.js state).
QtObject {
    id: store

    signal toast(string message, string kind)
    signal seekRequested(real t)
    signal playRequested()
    signal pauseRequested()
    signal releaseFocus()       // click outside a text box: give the keyboard back to the shortcuts
    signal playClip(var clip)   // open the rendered-clip player
    signal searchRequested()
    signal showLine(int index)  // scroll the transcript to a line
    signal transcriptReloading()  // this video's transcript is about to be replaced (the view keeps its place)
    signal jumpRequested(real t)  // move the playhead without leaving the teaser (teaser start, loop, cut skips)
    signal previewSound(real toneSeconds, string pulseKey)  // play the muted-word sound once; that tile pulses
    signal pickAudioRequested(string kind)  // open the audio file dialog: "music", "sfx" or "sfx-tile"
    signal askRequested(string title, string text, string okText, var action)   // a yes / no question first
    signal dialogRequested(string name)  // open a window: "settings", "campaigns", "moments", "tracker"
    signal rangeSet()           // the clip range was set from anywhere but the In / Out boxes (web: setRange)

    // ------------------------------------------------------------ server state
    property var job: ({ kind: null, running: false, progress: 0, message: "Ready", error: null, seq: 0 })
    property var prep: ({ state: "idle", progress: 0, message: "" })
    property var recent: []
    property var video: null
    property string videoKey: ""
    property var info: null
    property real duration: 0
    property string mediaUrl: ""
    property var mediaStamp: undefined
    property var transcriptStamp: undefined
    property var peaksStamp: undefined
    property var lines: []
    property var words: []
    property var wordStarts: []
    property var wordEnds: []
    property var lineWords: []  // [first, end) word indexes of each transcript line
    property var peaks: null
    property int peakRate: 20
    property var clips: []
    property string clipsSig: ""
    property var finishedSeq: undefined
    property int transcriptVersion: 0
    readonly property bool busy: job.running

    // ------------------------------------------------------------ presets (from the engine)
    property var styles: ({})
    property var hooks: ({})
    property var keywords: ({})
    property var styleOrder: []
    property var hookOrder: []
    property var muteSounds: ({})     // {key: {label, kind: none|tone|hit, freq}} – clipper.MUTE_SOUNDS
    property var muteSoundOrder: []
    property int emojiSize: 150
    property string defaultStyle: "classic"
    property string defaultHook: "white"
    property int hookTop: 230

    // ------------------------------------------------------------ the clip being edited
    property string editing: ""
    property string clipName: "clip_01"
    property var inT: null
    property var outT: null
    property string layout: "crop"
    property real cropX: 0.5
    property real frameY: 0.5
    property real frameZoom: 1.0
    property string hookText: ""
    property string postText: ""
    property bool captionsOn: true
    property var cap: ({ style: "classic", color: null, size: 100, pos: null })
    property var kw: ({ on: false, color: "#39FF14", emojis: false })
    property var hook: ({ style: "white", size: 100, pos: null, duration: 0 })
    property var extra: ({})   // settings this edition doesn't edit yet – kept untouched when saving
    property int anchorLine: -1

    // ------------------------------------------------------------ playback (set by the stage)
    property real playhead: 0
    property bool playing: false
    property bool loop: true
    property bool safe: false
    property int liveLine: -1
    property string search: ""

    readonly property var zoomLimits: ({ fit: [0.5, 2.5], crop: [1, 2.5] })
    readonly property var swatches: ["#FFFF00", "#FFD400", "#39FF14", "#00E5FF", "#FF2BD6", "#8B5CFF", "#FF3B30", "#FF9500", "#FFFFFF"]

    // ------------------------------------------------------------ helpers
    function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)) }
    function round(v, d) { const k = Math.pow(10, d); return Math.round(v * k) / k }

    function fmt(t) {
        t = Math.round(Math.max(0, t || 0) * 10) / 10
        const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60)
        const s = (t % 60).toFixed(1).padStart(4, "0")
        return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`
    }

    function parseTime(text) {
        const parts = String(text).trim().split(":")
        if (!parts[0] || parts.length > 3) return null
        let total = 0
        for (const part of parts) {
            if (!/^\d+(\.\d+)?$/.test(part.trim())) return null
            total = total * 60 + parseFloat(part)
        }
        return total
    }

    function safeName(text) {
        return String(text).trim().replace(/[^A-Za-z0-9_-]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 60)
    }

    function lastAtOrBefore(items, t, key) {
        let lo = 0, hi = items.length - 1, found = -1
        while (lo <= hi) {
            const mid = (lo + hi) >> 1
            if (key(items[mid]) <= t) { found = mid; lo = mid + 1 } else hi = mid - 1
        }
        return found
    }

    // ------------------------------------------------------------ polling the engine
    function poll() {
        applyState(backend.state())
        return job.running || prep.state === "working"
    }

    function applyState(st) {
        const v = st.video
        if (!v) {
            if (video) { video = null; videoKey = "" }
            if (JSON.stringify(st.recent) !== JSON.stringify(recent)) recent = st.recent
            applyJob(st.job, st.prep)
            return
        }
        setClips(st.clips)
        if (v.key !== videoKey) loadProject(v)
        video = v
        if (v.media !== mediaStamp) { mediaStamp = v.media; mediaUrl = v.media ? backend.mediaUrl() : "" }
        if (v.transcript !== transcriptStamp) loadTranscript(v.transcript)
        if (v.peaks !== peaksStamp) loadPeaks(v.peaks)
        applyJob(st.job, st.prep)
    }

    function applyJob(j, p) {
        if (finishedSeq === undefined) finishedSeq = j.running ? j.seq - 1 : j.seq
        if (!j.running && j.seq !== finishedSeq) {
            finishedSeq = j.seq
            if (j.error) toast(j.error, "error")
            else if (j.kind === "render") toast(j.message, "ok")
            else if (j.kind === "transcribe") toast("Transcript ready. Click a line to start a clip.", "ok")
        }
        job = j
        prep = p
    }

    function loadProject(v) {
        videoKey = v.key
        info = v.info
        duration = v.info.duration
        mediaStamp = undefined; transcriptStamp = undefined; peaksStamp = undefined
        lines = []; words = []; clearWordIndex(); peaks = null
        newClip(true)
        resetHistory()   // another video: nothing to undo
        moments = []; momentsAdded = ({})
    }

    // the transcript is gone (another video, or none yet): no word edges to snap to, no line anchor
    function clearWordIndex() {
        wordStarts = []; wordEnds = []; lineWords = []
        timelineCache = ({})
        liveLine = -1
        anchorLine = -1
    }

    function loadTranscript(stamp) {
        transcriptStamp = stamp
        if (!stamp) { lines = []; words = []; clearWordIndex(); transcriptVersion++; return }
        const d = backend.transcript()
        if (d.error) { toast(d.error, "error"); return }
        if (lines.length) transcriptReloading()   // a fix or a new transcription of the same video
        // plain JS objects: indexing the engine's list makes a new object on every read (10k words per pass)
        lines = d.lines.map(l => ({ s: l.s, e: l.e, text: l.text }))
        if (anchorLine >= lines.length) anchorLine = -1
        words = d.words.map(w => ({ w: w.w, s: w.s, e: w.e }))
        wordStarts = words.map(w => w.s)
        wordEnds = words.map(w => w.e).sort((a, b) => a - b)
        // words belong to the line they start in (the next line's start is the boundary)
        const ranges = []
        let wi = 0
        for (let i = 0; i < lines.length; i++) {
            const next = lines[i + 1]
            while (wi < words.length && words[wi].s < lines[i].s - 0.005) wi++
            const first = wi
            while (wi < words.length && (!next || words[wi].s < next.s - 0.005)) wi++
            ranges.push([first, wi])
        }
        lineWords = ranges
        toolAnchor = ({ cuts: -1, mutes: -1 })   // word indexes changed: an old anchor would point at another word
        liveLine = -1
        timelineCache = ({})
        transcriptVersion++
    }

    function loadPeaks(stamp) {
        peaksStamp = stamp
        const raw = stamp ? backend.peaks() : ""
        if (!raw) { peaks = null; return }
        const d = JSON.parse(raw)
        peakRate = d.rate
        peaks = d.peaks
    }

    function loadStyles() {
        const d = backend.styles()
        styles = d.styles
        hooks = d.hooks
        keywords = d.keywords
        styleOrder = d.style_order
        hookOrder = d.hook_order
        muteSounds = d.mute_sounds
        muteSoundOrder = d.mute_order
        emojiSize = d.emoji_size
        defaultStyle = d["default"]
        defaultHook = d.default_hook
        hookTop = d.hook_top
    }

    // ------------------------------------------------------------ clip range
    // fromInputs: a time typed in the In / Out box (the boxes keep what was typed)
    function setRange(a, b, fromInputs) {
        const dur = duration || Infinity
        const before = [inT, outT]
        inT = a === null || a === undefined ? null : round(clamp(a, 0, dur), 2)
        outT = b === null || b === undefined ? null : round(clamp(b, 0, dur), 2)
        if (inT !== before[0] || outT !== before[1]) selectedPart = -1   // the parts moved
        if (!fromInputs) rangeSet()
    }

    function pickLines(first, last) {
        setRange(lines[first].s - 0.15, lines[last].e + 0.3)
    }

    function setIn() {
        const t = playhead
        setRange(t, outT !== null && outT > t + 0.2 ? outT : Math.min(t + 30, duration))
    }

    function setOut() {
        const t = playhead
        setRange(inT !== null && inT < t - 0.2 ? inT : Math.max(0, t - 30), t)
    }

    // ------------------------------------------------------------ framing
    function setFrameZoom(z) {
        const lim = zoomLimits[layout]
        frameZoom = round(clamp(z, lim[0], lim[1]), 3)
    }

    function setLayout(value) {
        layout = value
        setFrameZoom(frameZoom)
    }

    // ------------------------------------------------------------ speaker switches (web: ui/pro.js 517-560, app.js 1613-1631)
    // [{t, x, y}] sorted by t. t is in SOURCE seconds; x / y is the frame position from 0 to 1 (like cropX / frameY).
    // From each switch on, the frame sits at that switch's position; before the first one, at cropX / frameY.
    property var keyframes: []

    // the frame position at source time t (default: the playhead): the last switch at or before t, else the
    // clip's own – same rule as clipper.position_track. idx = index of that switch, or -1
    function framePos(t) {
        if (t === undefined || t === null) t = playhead
        let idx = -1
        keyframes.forEach((k, i) => { if (k.t <= t + 0.001) idx = i })
        return idx >= 0 ? { x: keyframes[idx].x, y: keyframes[idx].y, idx: idx } : { x: cropX, y: frameY, idx: -1 }
    }

    // the same at the playhead as plain values: int / real properties only notify when the value really
    // changes, so the preview geometry is not recomputed on every playback tick
    readonly property var framePosNow: framePos(playhead)
    readonly property int activeKeyframe: framePosNow.idx
    readonly property real posX: framePosNow.x
    readonly property real posY: framePosNow.y

    // moving the picture changes whichever position is active at the playhead
    function setFramePos(x, y) {
        const pos = framePos()
        if (pos.idx >= 0) {
            const list = keyframes.slice()
            list[pos.idx] = { t: list[pos.idx].t, x: round(clamp(x, 0, 1), 3), y: round(clamp(y, 0, 1), 3) }
            keyframes = list
        } else {
            cropX = round(clamp(x, 0, 1), 3)
            frameY = round(clamp(y, 0, 1), 3)
        }
    }

    // "+ Switch here"
    function addKeyframe() {
        // the web rounds to 0.01 s, which can put the switch up to 5 ms AFTER the playhead – it is then not
        // active yet and the next drag moves the previous position. Rounding down keeps it active.
        const t = Math.floor(playhead * 100 + 1e-6) / 100
        if (inT === null || outT === null || t < inT || t > outT) { toast("Move the playhead inside the clip first.", "info"); return }
        if (keyframes.some(k => Math.abs(k.t - t) < 0.1)) { toast("There is already a switch here.", "info"); return }
        const pos = framePos()
        const list = keyframes.concat([{ t: t, x: pos.x, y: pos.y }])
        list.sort((a, b) => a.t - b.t)
        keyframes = list
        toast("Switch added – now drag the preview to frame the other person.", "ok")
    }

    function removeKeyframe(i) {
        const list = keyframes.slice()
        list.splice(i, 1)
        keyframes = list
    }

    // "Go there": 20 ms after the switch so it is the active one (stage.seek also leaves the teaser)
    function gotoKeyframe(i) {
        if (keyframes[i]) seekRequested(keyframes[i].t + 0.02)
    }

    // where the video sits in the 9:16 frame (w x h = the phone preview size) – mirrors clipper.layout_filter.
    // pos = {x, y} from 0 to 1; default: the position active at the playhead (a speaker switch, else the clip's own)
    function frameGeometry(vw, vh, w, h, pos) {
        if (!pos) pos = { x: posX, y: posY }
        const z = frameZoom
        if (layout === "fit") {
            const fw = w * z, fh = fw * vh / vw
            return { mode: "fit", w: fw, h: fh, x: (w - fw) * pos.x, y: (h - fh) * pos.y }
        }
        const cw = Math.min(vh * 9 / 16, vw) / z, ch = vh / z
        const s = w / cw
        const sx = (vw - cw) * pos.x, sy = (vh - ch) * pos.y
        return { mode: "crop", w: vw * s, h: vh * s, x: -sx * s, y: -sy * s, cw: cw, ch: ch }
    }

    // ------------------------------------------------------------ caption + hook looks
    function effectiveStyle() {
        const base = styles[cap.style] || styles[defaultStyle]
        if (!base) return null
        const st = Object.assign({}, base)
        if (cap.color) st.accent = cap.color
        st.size = Math.round(base.size * clamp(cap.size, 50, 200) / 100)
        if (cap.pos !== null && cap.pos !== undefined) st.margin_v = cap.pos
        return st
    }

    function setCap(changes) { cap = Object.assign({}, cap, changes) }
    function setKw(changes) { kw = Object.assign({}, kw, changes) }
    function setHook(changes) { hook = Object.assign({}, hook, changes) }

    function effectiveHook() {
        const base = hooks[hook.style] || hooks[defaultHook]
        if (!base) return null
        return Object.assign({}, base, {
            size: Math.round(base.size * clamp(hook.size, 50, 200) / 100),
            margin_v: hook.pos !== null && hook.pos !== undefined ? hook.pos : hookTop,
            duration: hook.duration
        })
    }

    // same grouping as clipper.caption_chunks / caption_timeline
    property var timelineCache: ({})
    // ws / cache: another word list and its cache (the edited clip's), else the transcript's
    function timelineFor(st, ws, cache) {
        if (!ws) { ws = words; cache = timelineCache }
        const key = `${st.max_words}|${st.max_chars}`
        if (cache[key]) return cache[key]
        const chunks = []
        let cur = []
        for (const w of ws) {
            if (cur.length) {
                const last = cur[cur.length - 1]
                const joined = cur.map(x => x.w).join(" ").length + 1 + w.w.length
                if (cur.length >= st.max_words || joined > st.max_chars || /[.?!,]$/.test(last.w) || w.s - last.e > 0.5) {
                    chunks.push(cur)
                    cur = []
                }
            }
            cur.push(w)
        }
        if (cur.length) chunks.push(cur)
        const timeline = chunks.map((chunk, i) => {
            let end = chunk[chunk.length - 1].e
            if (i + 1 < chunks.length && chunks[i + 1][0].s - end < 0.35) end = chunks[i + 1][0].s
            return { words: chunk, end: end }
        })
        cache[key] = timeline
        return timeline
    }

    function captionAt(t, timeline) {
        const idx = lastAtOrBefore(timeline, t, c => c.words[0].s)
        if (idx < 0 || t >= timeline[idx].end) return null
        const ws = timeline[idx].words
        const active = Math.max(0, lastAtOrBefore(ws, t, w => w.s))
        // build_ass writes no event for a word shown under 0.05 s: the render has no caption there
        const until = active + 1 < ws.length ? ws[active + 1].s : timeline[idx].end
        if (until - ws[active].s < 0.05) return null
        return { words: ws, active: active }
    }

    // same as clipper.bare_word / keyword_emoji: [is keyword, emoji or ""]
    // letters of any script count as word characters (\w alone only knows A-Z)
    readonly property var wordJunk: new RegExp("[^\\w$%'\\-" + String.fromCharCode(0xC0) + "-" + String.fromCharCode(0x1FFF)
                                               + String.fromCharCode(0x2C00) + "-" + String.fromCharCode(0xFFFD) + "]", "g")
    function keywordEmoji(text) {
        const word = text.toLowerCase().replace(wordJunk, "").replace(/^['-]+|['-]+$/g, "")
        if (!word) return [false, ""]
        if (/\d/.test(word) || word.startsWith("$") || word.endsWith("%")) return [true, word.startsWith("$") ? "💰" : ""]
        const emoji = keywords[word] || (word.endsWith("s") ? keywords[word.slice(0, -1)] : "")
        return emoji ? [true, emoji] : [false, ""]
    }

    // ------------------------------------------------------------ edit model (Stage 2) – ported from app.js
    property var edit: ({
        removePauses: false, pauseMin: 0.5, zoom: false, zoomAmount: 1.15, speed: 1, progress: false,
        progressColor: "#00E5FF", music: "", musicVolume: 0.15, watermark: "", watermarkPos: "tr",
        intro: null, introFlash: true, muteSound: "silence", muteCaptions: true, muteSfx: "", muteSfxVolume: 0.8
    })
    property var cuts: []               // [[a, b]] source seconds removed from the clip (normalised)
    property var drops: []              // [[a, b]] parts deleted with the razor – removed like cuts, kept apart from them
    property var mutes: []              // [[a, b]] source seconds whose sound is silenced
    property bool inIntro: false        // the preview is playing the teaser (web: S.inIntro)
    property var memo: ({})             // plain cache holder; its fields are never bound to
    readonly property var barColors: ["#00E5FF", "#FF2BD6", "#FFFF00", "#39FF14", "#FFFFFF", "#FF3B30"]
    readonly property var speeds: [1, 1.1, 1.2, 1.3]

    // changes exactly when the edit model's result can change (web: the editState() cache key)
    readonly property string editKey: JSON.stringify([inT, outT, cuts, drops, edit.removePauses, edit.pauseMin, edit.zoom,
        edit.zoomAmount, edit.speed, edit.intro, mutes, edit.muteCaptions, transcriptVersion, duration, videoKey])

    function setEdit(changes) { edit = Object.assign({}, edit, changes) }

    function wordMid(w) { return (w.s + w.e) / 2 }

    // sorted, merged, rounded ranges (web: normaliseCuts)
    function normaliseCuts(ranges) {
        const sorted = ranges.filter(r => r[1] - r[0] > 0.01).sort((x, y) => x[0] - y[0])
        const out = []
        for (const r of sorted) {
            const last = out[out.length - 1]
            if (last && r[0] <= last[1] + 0.001) last[1] = Math.max(last[1], r[1])
            else out.push([r[0], r[1]])
        }
        return out.map(r => [round(r[0], 3), round(r[1], 3)])
    }

    // the parts of the source kept in the clip, [[a, b, zoom]] – same rules as clipper.edit_segments.
    // dropList: other deleted parts to try instead of the clip's own (the razor checks a delete before doing it)
    function editSegments(dropList) {
        if (inT === null || outT === null || outT <= inT) return null
        const start = inT, end = Math.min(outT, duration || outT), ed = edit   // clipper.plan_clip ends at the video's end
        const removed = cuts.concat(dropList || drops).map(r => [r[0], r[1]])
        const inside = words.filter(w => w.e > start && w.s < end)
        if (ed.removePauses && inside.length) {
            const gap = ed.pauseMin, lead = 0.08, tail = 0.12
            if (inside[0].s - start > gap) removed.push([start, inside[0].s - lead])
            for (let i = 1; i < inside.length; i++) {
                if (inside[i].s - inside[i - 1].e > gap) removed.push([inside[i - 1].e + tail, inside[i].s - lead])
            }
            const last = inside[inside.length - 1]
            if (end - last.e > gap) removed.push([last.e + tail, end])
        }
        removed.sort((x, y) => x[0] - y[0] || x[1] - y[1])
        let kept = [[start, end]]
        for (const r of removed) {
            const a = r[0], b = r[1]
            const pieces = []
            for (const k of kept) {
                const s = k[0], e = k[1]
                if (b <= s || a >= e) { pieces.push([s, e]); continue }
                if (a > s) pieces.push([s, a])
                if (b < e) pieces.push([b, e])
            }
            kept = pieces
        }
        kept = kept.filter(k => k[1] - k[0] >= 0.12)
        if (!ed.zoom) return kept.map(k => [k[0], k[1], 1])
        // punch in on every other piece; long pieces are split where transcript lines start
        const marks = lines.map(l => l.s)
        const pieces = []
        for (const k of kept) {
            const s = k[0], e = k[1]
            const edges = [s].concat(marks.filter(m => s + 0.8 < m && m < e - 0.8), [e])
            for (let i = 0; i + 1 < edges.length; i++) pieces.push([edges[i], edges[i + 1]])
        }
        return pieces.map((p, i) => [p[0], p[1], i % 2 ? ed.zoomAmount : 1])
    }

    // source time t -> seconds into the kept pieces (after speed); clamps to the nearest piece edge
    function outputTime(t, segs, speed) {
        let offset = 0
        for (const sg of segs) {
            if (t < sg[0]) break
            if (t <= sg[1]) return (offset + t - sg[0]) / speed
            offset += sg[1] - sg[0]
        }
        return offset / speed
    }

    // the teaser range, clamped like clipper.teaser_piece (edit.intro must be set)
    function teaserRange() {
        const a = Math.max(0, edit.intro[0])
        const b = Math.min(edit.intro[1], duration, a + 15)
        return b - a >= 0.3 ? [a, b] : null
    }

    // 'damn,' -> 'd***,' – same as clipper.censor
    function censor(text) {
        const core = text.replace(/[.,!?;:"']+$/, "")
        if (!core) return text
        return (core.length > 1 ? core[0] + "*".repeat(core.length - 1) : "*") + text.slice(core.length)
    }

    // Python's sum() of floats (compensated since 3.12), so the clip length is the engine's to the last bit:
    // a zero-length word right at the clip's end is kept or dropped (build_ass) the same way
    function pySum(values) {
        let s = 0, c = 0
        for (const x of values) {
            const t = s + x
            c += Math.abs(s) >= Math.abs(x) ? (s - t) + x : (x - t) + s
            s = t
        }
        return s + c
    }

    // segments, final length and the clip's own caption words; recomputed only when editKey changes
    function editState() {
        const key = editKey
        if (memo.edit && memo.edit.key === key) return memo.edit
        const segs = editSegments()
        const speed = edit.speed
        const intro = edit.intro && duration ? teaserRange() : null
        memo.serial = (memo.serial || 0) + 1
        const cache = { key: key, serial: memo.serial, segs: segs, speed: speed, intro: intro,
                        introLen: intro ? intro[1] - intro[0] : 0, duration: 0, words: [], timelines: {} }
        if (segs && segs.length) {
            // play order: teaser first, then the kept pieces (same as clipper.map_words)
            const pieces = (intro ? [[intro[0], intro[1], 1]] : []).concat(segs)
            cache.duration = pySum(pieces.map(p => p[1] - p[0])) / speed
            // only words that overlap the pieces' span (clipper.map_words: a zero-length word on its edge is dropped)
            let low = Infinity, high = -Infinity
            for (const p of pieces) { low = Math.min(low, p[0]); high = Math.max(high, p[1]) }
            const nearby = words.filter(w => w.e > low && w.s < high)
            const hide = edit.muteCaptions && mutes.length > 0
            let offset = 0
            for (const p of pieces) {
                const a = p[0], b = p[1]
                for (const w of nearby) {
                    if (w.e <= a - 1 || w.s >= b + 1) continue
                    const mid = wordMid(w)
                    if (mid < a || mid > b) continue
                    const s = (offset + Math.max(w.s, a) - a) / speed, e = (offset + Math.min(w.e, b) - a) / speed
                    const hidden = hide && mutes.some(m => mid >= m[0] && mid <= m[1])
                    // build_ass -> caption_words: cleaned like clean_word, none at or past the clip's edges
                    const text = (hidden ? censor(w.w) : w.w).replace(/[{}\\]/g, "").trim()
                    if (!text || Math.max(s, e) <= 0 || s >= cache.duration) continue
                    cache.words.push({ w: text, s: Math.max(0, s), e: Math.min(cache.duration, Math.max(s, e)) })
                }
                offset += b - a
            }
        }
        memo.edit = cache
        return cache
    }

    // where source time t is on the finished clip's timeline (teaser + edits + speed), or null outside it
    function clipTime(t, ed) {
        if (inIntro && ed.intro && t >= ed.intro[0] - 0.05 && t <= ed.intro[1] + 0.05)
            return clamp(t - ed.intro[0], 0, ed.introLen) / ed.speed
        if (!ed.segs || !ed.segs.length || t < inT - 0.01 || t > outT + 0.01) return null
        return ed.introLen / ed.speed + outputTime(t, ed.segs, ed.speed)
    }

    // the saved edit fields – same names as the web edition's editFields() / clipper_app.clean_edits
    function editFields() {
        const ed = edit
        return {
            cuts: cuts, remove_pauses: ed.removePauses, pause_min: ed.pauseMin, zoom: ed.zoom, zoom_amount: ed.zoomAmount,
            speed: ed.speed, progress: ed.progress, progress_color: ed.progressColor, music: ed.music,
            music_volume: ed.musicVolume, watermark: ed.watermark, watermark_pos: ed.watermarkPos,
            intro_start: ed.intro ? round(ed.intro[0], 3) : null, intro_end: ed.intro ? round(ed.intro[1], 3) : null,
            intro_flash: ed.introFlash, mutes: mutes, mute_mode: ed.muteSound, mute_captions: ed.muteCaptions,
            mute_sfx: ed.muteSfx, mute_sfx_volume: ed.muteSfxVolume, drops: drops, splits: splitsInRange()
        }
    }

    // a saved clip's edit settings into the editor (web: editFromClip)
    function editFromClip(c) {
        const has = v => v !== null && v !== undefined
        edit = {
            removePauses: !!c.remove_pauses, pauseMin: c.pause_min || 0.5, zoom: !!c.zoom,
            zoomAmount: c.zoom_amount || 1.15, speed: c.speed || 1, progress: !!c.progress,
            progressColor: c.progress_color || "#00E5FF", music: c.music || "",
            musicVolume: has(c.music_volume) ? c.music_volume : 0.15,
            watermark: c.watermark || "", watermarkPos: c.watermark_pos || "tr",
            intro: has(c.intro_start) && has(c.intro_end) ? [c.intro_start, c.intro_end] : null,
            introFlash: c.intro_flash !== false, muteSound: c.mute_mode || "silence",
            muteCaptions: c.mute_captions !== false, muteSfx: c.mute_sfx || "",
            muteSfxVolume: has(c.mute_sfx_volume) ? c.mute_sfx_volume : 0.8
        }
        cuts = normaliseCuts(rangeList(c.cuts))
        mutes = normaliseCuts(rangeList(c.mutes))
        drops = normaliseCuts(rangeList(c.drops))
        splits = savedList(c.splits).map(savedNumber).filter(t => isFinite(t) && t > 0).sort((x, y) => x - y)
        selectedPart = -1
    }

    // clips.json can be edited by hand: a list from it as a plain array, else [] (the engine's lists arrive as
    // array-like sequences, which Array.isArray does not count)
    function savedList(v) {
        return v !== null && typeof v === "object" && typeof v.length === "number" ? Array.prototype.slice.call(v) : []
    }

    // ... a number (or a number as text), else NaN – like clean_edits
    function savedNumber(v) {
        return typeof v === "number" || (typeof v === "string" && v.trim() !== "") ? Number(v) : NaN
    }

    // ... and [[a, b]], with anything that isn't two finite numbers left out
    function rangeList(items) {
        return savedList(items).map(savedList).filter(r => r.length >= 2).map(r => [savedNumber(r[0]), savedNumber(r[1])])
            .filter(r => isFinite(r[0]) && isFinite(r[1]))
    }

    // the length box (Clip tab) and the final-length box (Edit tab) – web: updateLength()
    // level: "none" (no range), "bad" (end before start), "warn" (< 10 s or > 90 s), "ok"
    function lengthInfo() {
        if (inT === null || outT === null)
            return { text: "—", level: "none", clipHint: "Click a transcript line or press I / O", editHint: "Pick a clip range first" }
        const raw = outT - inT
        if (raw <= 0) {
            const why = "The end must be after the start"
            return { text: "END " + String.fromCharCode(0x2264) + " START", level: "bad", clipHint: why, editHint: why }
        }
        const d = editState().duration
        const edited = Math.abs(d - raw) > 0.05
        const len = edited ? d : raw
        const advice = len < 10 ? "Short – most campaigns want 15 s+" : len > 90 ? "Long – 20–60 s performs best" : "Best length: 20–60 s"
        return {
            text: `${len.toFixed(1)}s`, level: len < 10 || len > 90 ? "warn" : "ok",
            clipHint: edited ? `after edits (raw ${raw.toFixed(1)}s)` : advice,
            editHint: edited ? `from ${raw.toFixed(1)}s raw · ${advice}` : `No edits yet · ${advice}`
        }
    }

    // "Apply to all clips" on the Edit tab: every setting except the cuts, mutes and teaser (web: #btn-edit-all)
    function applyEditToAll() {
        if (!clips.length) { toast("The queue is empty.", "info"); return }
        const f = editFields()
        delete f.cuts; delete f.mutes; delete f.intro_start; delete f.intro_end; delete f.splits; delete f.drops
        const n = clips.length
        if (saveClips(clips.map(c => Object.assign(stripStatus(c), f))))
            toast(`Edit settings applied to ${n} clip${n === 1 ? "" : "s"} (cuts stay per clip).`, "ok")
    }

    // ------------------------------------------------------------ razor: split lines on the timeline (CapCut style)
    // splits = source seconds; the parts are the pieces of the clip between them. A deleted part goes to `drops`,
    // which the render removes like cuts (the lines themselves are only for the editor). The word cuts stay as
    // they are, so Restore brings a part back exactly as it was.
    property var splits: []
    property int selectedPart: -1        // the part picked on the waveform (-1 = none)
    readonly property var parts: computeParts(inT, outT, splits, drops)

    // the edges of the deleted parts are lines too: after a trim (or a load) a deleted stretch is still a whole
    // part that shows as deleted and can be restored – never half of a kept part, never hidden
    function computeParts(a, b, list, dropList) {
        if (a === null || b === null || b <= a) return []
        const marks = list.slice()
        for (const r of dropList || []) marks.push(r[0], r[1])
        const edges = [a]
        for (const t of marks.filter(t => t > a + 0.05 && t < b - 0.05).sort((x, y) => x - y))
            if (t - edges[edges.length - 1] > 0.005) edges.push(t)   // a line and a drop edge at the same spot: one line
        edges.push(b)
        const out = []
        for (let i = 0; i + 1 < edges.length; i++) out.push([edges[i], edges[i + 1]])
        return out
    }

    // the lines the editor shows, deleted parts' edges included (lines left outside the clip after a trim are not
    // saved; they stay while editing, so widening the clip again brings them back)
    function splitsInRange() { return parts.slice(1).map(p => p[0]) }

    // the part holding source time t (-1 outside the clip)
    function partAt(t) {
        const n = parts.length
        for (let i = 0; i < n; i++)
            if (t >= parts[i][0] && (t < parts[i][1] || (i === n - 1 && t <= parts[i][1]))) return i
        return -1
    }

    // a part is deleted when one drop covers all of it (drops are merged, so one is enough). A drop edge within
    // 0.05 s of In / Out makes no line (computeParts): the sliver it leaves there – too short to be kept – doesn't count
    function partRemoved(i) {
        const p = parts[i]
        if (!p) return false
        const a = p[0] + (i === 0 ? 0.051 : 0.002), b = p[1] - (i === parts.length - 1 ? 0.051 : 0.002)
        return drops.some(r => r[0] <= a && r[1] >= b)
    }

    // is every part deleted (a trim past the last kept part can do that)
    function allPartsRemoved() { return parts.length > 0 && parts.every((p, i) => partRemoved(i)) }

    // seconds of part i still in the clip after every edit (cuts, removed pauses); segs = editState().segs
    function partKept(i, segs) {
        const p = parts[i]
        if (!p || !segs) return 0
        let s = 0
        for (const sg of segs) s += Math.max(0, Math.min(sg[1], p[1]) - Math.max(sg[0], p[0]))
        return s
    }

    // S / "Split": a line at the playhead; the part after it gets picked
    function addSplit() {
        if (inT === null || outT === null || outT <= inT) { toast("Pick a clip first: click a transcript line or press I / O.", "info"); return }
        const t = round(playhead, 2)
        if (t <= inT + 0.1 || t >= outT - 0.1) { toast("Move the playhead inside the clip to split it.", "info"); return }
        if (splitsInRange().some(s => Math.abs(s - t) < 0.1)) { toast("There is already a split here.", "info"); return }
        // a line a trim left outside the clip gives way when it is this close (nobody can see it)
        splits = splits.filter(s => Math.abs(s - t) >= 0.1).concat([t]).sort((x, y) => x - y)
        selectedPart = parts.findIndex(p => p[0] === t)
    }

    // can the line at t go? Not between a deleted part and a kept one – the joined part would be half deleted.
    function splitRemovable(t) {
        const left = parts.findIndex(p => Math.abs(p[1] - t) < 0.001), right = left + 1
        return left < 0 || right >= parts.length || partRemoved(left) === partRemoved(right)
    }

    // double-click / right-click on a line: the two parts become one again
    function removeSplit(t) {
        if (!splitRemovable(t)) {
            toast("Restore the deleted part next to this line first.", "info")
            return
        }
        splits = splits.filter(s => Math.abs(s - t) > 0.001)
        selectedPart = -1
    }

    // a click on the waveform picks the part under it: once the clip has been split, or when its only part is
    // deleted (a trim can leave just that), so it can be restored
    function selectPart(i) { selectedPart = i >= 0 && i < parts.length && (parts.length > 1 || partRemoved(i)) ? i : -1 }

    // the ranges in list without source range [a, b]
    function cutsWithout(list, a, b) {
        const out = []
        for (const r of list) {
            if (r[1] <= a || r[0] >= b) { out.push([r[0], r[1]]); continue }
            if (r[0] < a) out.push([r[0], a])
            if (r[1] > b) out.push([b, r[1]])
        }
        return normaliseCuts(out)
    }

    // Delete / "Delete": the picked part leaves the clip; on a deleted part it comes back ("Restore")
    function deletePart() {
        const i = selectedPart, p = parts[i], n = parts.length
        if (!p) { toast("Click a part of the clip on the waveform first.", "info"); return }
        // the part's lines stay where they are either way (an edge of a deleted part is only a line while it is deleted)
        const edges = [i > 0 ? p[0] : null, i < n - 1 ? p[1] : null]
            .filter(t => t !== null && !splits.some(s => Math.abs(s - t) < 0.001))
        const keepLines = () => { if (edges.length) splits = splits.concat(edges).sort((x, y) => x - y) }
        if (partRemoved(i)) {
            // at In / Out the rest of that deleted stretch, left outside the clip by a trim, comes back too
            let a = p[0], b = p[1]
            for (const r of drops) {
                if (i === 0 && r[0] < a && r[1] > a) a = r[0]
                if (i === n - 1 && r[0] < b && r[1] > b) b = r[1]
            }
            keepLines()
            drops = cutsWithout(drops, a, b)
            if (n === 1) selectedPart = -1   // a lone part is picked only while it is deleted (selectPart)
            return
        }
        const next = normaliseCuts(drops.concat([[p[0], p[1]]]))
        const segs = editSegments(next)
        if (!segs || !segs.length) { toast("That is the last part – a clip needs at least one.", "info"); return }
        keepLines()
        drops = next
        // the teaser is played before the clip, so it can come from anywhere – also from a deleted part
        const intro = edit.intro
        if (intro && intro[0] >= p[0] - 0.01 && intro[1] <= p[1] + 0.01)
            toast("The teaser comes from this part, so it still plays at the start. Turn it off on the Edit tab if you like.", "info")
    }

    // "To clips": which parts become clips and their names – {names, parts, short, teaser} or {error}.
    // short = kept parts left out for having under 0.3 s left; teaser = the clip (index) that gets the teaser, or -1
    function splitPlan() {
        const base = safeName(clipName).slice(0, 52)
        if (!base) return { error: "Give the clip a name first." }
        if (parts.length < 2) return { error: "Split the clip first: move the playhead and press S." }
        if (allPartsRemoved()) return { error: "Every part is deleted – pick one and restore it first." }
        const segs = editState().segs || []
        const kept = parts.filter((p, i) => !partRemoved(i))
        const keep = parts.filter((p, i) => !partRemoved(i) && partKept(i, segs) >= 0.3)
        if (!keep.length) return { error: "Everything left in the clip is cut out – there is nothing to split." }
        if (keep.length < 2) return { error: "Only one part is left – there is nothing to split." }
        // the teaser goes with the part it comes from; one from anywhere else (outside the clip, a deleted part,
        // across a line) still plays before the clip's start, so part 1 gets it
        const intro = edit.intro
        const teaser = !intro ? -1 : Math.max(0, keep.findIndex(p => intro[0] >= p[0] - 0.01 && intro[1] <= p[1] + 0.01))
        const own = editing || safeName(clipName)   // this clip is replaced, so its own name is free
        const taken = new Set(clips.map(c => c.name).filter(n => n !== own))
        const names = []
        let n = 1
        for (let k = 0; k < keep.length; k++) {
            while (taken.has(`${base}_p${n}`)) n++
            names.push(`${base}_p${n}`)
            taken.add(`${base}_p${n}`)
        }
        return { names: names, parts: keep, short: kept.length - keep.length, teaser: teaser }
    }

    // every part that is not deleted becomes its own clip, in this clip's place in the queue. Each keeps all the
    // settings; cuts, mutes, switches and pop-ups go to the part they are in, the teaser as splitPlan says.
    // Part 1 opens.
    function splitIntoClips() {
        const plan = splitPlan()
        if (plan.error) { toast(plan.error, "info"); return }
        const base = clipFields()
        const segs = editState().segs
        const made = plan.parts.map((p, k) => {
            const a = p[0], b = p[1]
            const inside = r => r[1] > a && r[0] < b
            const trim = r => [Math.max(r[0], a), Math.min(r[1], b)]
            // a line inside a pause the clip removes: the part starts / ends where the clip goes on, so its own pause
            // rule can't give that silence back (cut words and deleted parts go with the part, so they need nothing).
            // 0.01 s steps (the saved times), outwards: a sliver that small is never kept (pieces under 0.12 s are dropped)
            const inPause = t => !segs.some(sg => t >= sg[0] && t <= sg[1]) && !cuts.concat(drops).some(r => t > r[0] && t < r[1])
            const kept = segs.filter(sg => sg[1] > a && sg[0] < b)
            const start = a !== inT && inPause(a) ? Math.max(a, Math.floor(kept[0][0] * 100 + 1e-6) / 100) : a
            const end = b !== outT && inPause(b) ? Math.min(b, Math.ceil(kept[kept.length - 1][1] * 100 - 1e-6) / 100) : b
            const pos = framePos(start)   // the speaker framed at the part's start becomes its own position
            return Object.assign({}, base, {
                name: plan.names[k], start: start, end: end, crop_x: pos.x, frame_y: pos.y,
                cuts: normaliseCuts(cuts.filter(inside).map(trim)),
                drops: normaliseCuts(drops.filter(inside).map(trim)),
                mutes: normaliseCuts(mutes.filter(inside).map(trim)),
                keyframes: base.keyframes.filter(f => f.t > a && f.t < b),
                popups: base.popups.filter(q => q.at >= a && q.at < b),
                intro_start: k === plan.teaser ? base.intro_start : null, intro_end: k === plan.teaser ? base.intro_end : null,
                splits: []
            })
        })
        const list = clips.map(stripStatus)
        const idx = list.findIndex(c => c.name === (editing || base.name))
        if (idx === -1) list.push(...made)
        else list.splice(idx, 1, ...made)
        if (!saveClips(list)) return
        applyClip(clips.find(c => c.name === plan.names[0]) || made[0])
        toast(`Made ${made.length} clips: ${plan.names.join(", ")}`, "ok")
    }

    // ------------------------------------------------------------ teaser: a highlight played before the clip
    // ported from app.js 1270-1394. edit.intro = [a, b] source seconds or null; inIntro is in the edit model.
    property string teaserPick: ""      // web S.teaserPick: "" (= null) | "start" | "end"
    property int teaserStartWord: -1    // web S.teaserStartWord: the first word clicked while picking
    // = edit.intro, but from introKey: what only shows the teaser is not redone when another edit setting changes
    readonly property var teaserSpan: introKey ? introKey.split(",").map(Number) : null

    // order the ends, 2 decimals, at most 15 s; under 0.3 s = no teaser (web: setTeaser)
    function setTeaser(range) {
        if (range) {
            let a = range[0], b = range[1]
            if (b < a) { const x = a; a = b; b = x }
            range = [round(Math.max(0, a), 2), round(Math.min(b, a + 15), 2)]
            if (range[1] - range[0] < 0.3) range = null
        }
        setEdit({ intro: range })
    }

    // only one word tool at a time: picking turns the cut and mute tools off (web: setTeaserPick)
    function setTeaserPick(mode) {
        teaserPick = mode || ""
        if (mode === "start") {
            if (cutMode) setCutMode(false)
            if (muteMode) setMuteMode(false)
            toast("Teaser: click the FIRST word of the highlight in the transcript.", "info")
        } else if (mode === "end") {
            toast("Now click the LAST word of the highlight.", "info")
        }
    }

    function toggleTeaserPick() { setTeaserPick(teaserPick ? null : "start") }

    // edges around words first..last: a little air, never into the neighbouring words
    function teaserBounds(first, last) {
        const prev = words[first - 1], next = words[last + 1]
        const a = Math.max(words[first].s - 0.05, prev ? prev.e : 0)
        const b = next ? Math.min(words[last].e + 0.12, next.s + 0.02) : words[last].e + 0.12
        return [Math.max(0, a), b]
    }

    // a transcript word clicked while picking: the first one, then the last one
    function clickTeaserWord(i) {
        if (teaserPick === "start") {
            teaserStartWord = i
            setTeaserPick("end")
            return
        }
        const first = Math.min(teaserStartWord, i), last = Math.max(teaserStartWord, i)
        setTeaser(teaserBounds(first, last))
        setTeaserPick(null)
        // under 0.3 s leaves no teaser; the web's toast line then throws, so no toast either
        if (edit.intro) toast(`Teaser set: ${(edit.intro[1] - edit.intro[0]).toFixed(1)}s`, "ok")
    }

    // the most energetic 2.5–5.5 s run of words inside the clip (loud speech, ending on . ! ?) – web: autoTeaser
    function autoTeaser() {
        if (inT === null || outT === null) { toast("Pick the clip range first.", "info"); return null }
        const firstIdx = words.findIndex(w => w.s >= inT)
        const inside = words.filter(w => w.s >= inT && w.e <= outT)
        if (firstIdx < 0 || inside.length < 3) { toast("Not enough speech in this clip to pick a teaser.", "info"); return null }
        const pk = peaks, rate = peakRate
        const energy = (a, b) => {
            if (!pk) return 0
            let sum = 0, n = 0
            for (let k = Math.floor(a * rate); k < Math.ceil(b * rate) && k < pk.length; k++) { sum += pk[k]; n++ }
            return n ? sum / n / 255 : 0
        }
        const clipLen = outT - inT
        let best = null
        for (let i = 0; i < inside.length; i++) {
            // start on a sentence start (after . ! ? , or the first word)
            const starts = i === 0 || /[.!?,]$/.test(inside[i - 1].w)
            for (let j = i; j < inside.length; j++) {
                const len = inside[j].e - inside[i].s
                if (len > 5.5) break
                if (len < 2.5) continue
                const ends = /[.!?]$/.test(inside[j].w)
                const midway = (inside[i].s - inT) / clipLen   // later moments make better teasers
                const score = energy(inside[i].s, inside[j].e) + (ends ? 0.25 : 0) + (starts ? 0.15 : 0)
                    + (/[!?]$/.test(inside[j].w) ? 0.1 : 0) + midway * 0.2 - Math.abs(len - 4) * 0.03
                if (!best || score > best.score) best = { score: score, i: i, j: j }
            }
        }
        if (!best) { toast("Couldn’t find a 3–5 s highlight in this clip.", "info"); return null }
        return teaserBounds(firstIdx + best.i, firstIdx + best.j)
    }

    // the "Teaser at the start" switch: on = auto pick (the switch reads !!edit.intro again afterwards)
    function teaserSwitch(on) {
        if (!on) { setTeaser(null); return }
        const picked = autoTeaser()
        if (picked) { setTeaser(picked); toast("Teaser auto-picked – change it with Pick words or the times.", "ok") }
    }

    function teaserAutoPick() { const picked = autoTeaser(); if (picked) setTeaser(picked) }

    // I: the teaser starts at the playhead; keeps the end if it is 0.3 s+ later, else 4 s
    function teaserMarkStart() {
        const t = playhead, intro = edit.intro
        setTeaser([t, intro && intro[1] > t + 0.3 ? intro[1] : t + 4])
    }

    // O: the teaser ends at the playhead; keeps the start if it is 0.3 s+ earlier, else 4 s before
    function teaserMarkEnd() {
        const t = playhead, intro = edit.intro
        setTeaser([intro && intro[0] < t - 0.3 ? intro[0] : Math.max(0, t - 4), t])
    }

    // a typed from (which 0) / to (which 1) time; false = not a time (the box turns red)
    function teaserTyped(which, text) {
        const t = parseTime(text)
        if (t === null) return false
        const range = edit.intro ? edit.intro.slice() : [t, t + 4]
        range[which] = t
        if (which === 0 && !edit.intro) range[1] = t + 4
        setTeaser(range)
        return true
    }

    // is word i in the teaser – the raw edit.intro, both ends included (web: paintTeaser)
    function isTeaserWord(i) {
        const intro = teaserSpan, w = words[i]
        return !!intro && !!w && wordMid(w) >= intro[0] && wordMid(w) <= intro[1]
    }

    // the line under the teaser buttons: "4.2s · “what was said…”", and the whole text for the tooltip
    function teaserInfo() {
        const intro = teaserSpan
        if (!intro) return { text: "No teaser picked", said: "" }
        const said = words.filter(w => wordMid(w) >= intro[0] && wordMid(w) <= intro[1]).map(w => w.w).join(" ")
        const quote = said ? ` · “${said.length > 48 ? said.slice(0, 48) + "…" : said}”` : ""
        return { text: `${(intro[1] - intro[0]).toFixed(1)}s${quote}`, said: said }
    }

    // "Play" on the teaser row: play just the teaser, then the clip (web: playTeaser)
    function playTeaser() {
        const intro = editState().intro
        if (!intro) { toast("Pick a teaser first.", "info"); return }
        inIntro = true
        jumpRequested(intro[0])
        playRequested()
    }

    // ------------------------------------------------------------ word tools: cut (remove) and mute (silence)
    // ported from app.js 488-583. A word is "in" a list when its middle is strictly inside one of the ranges.
    property bool cutMode: false
    property bool muteMode: false
    property var toolAnchor: ({ cuts: -1, mutes: -1 })    // web TOOL_ANCHOR: word of the last plain click (-1 = none)
    property var toolState: ({ cuts: true, mutes: true })  // web TOOL_STATE: what that click did (true = added)

    // web inList(list, i), with the ranges passed in (a Shift run works on a local copy)
    function inRanges(ranges, i) {
        if (i < 0 || i >= words.length) return false
        const mid = wordMid(words[i])
        return ranges.some(r => mid > r[0] && mid < r[1])
    }
    function isCut(i) { return inRanges(cuts, i) }
    function isMuted(i) { return inRanges(mutes, i) }

    // web setWordIn as a pure function: the ranges with word i added (on) or taken out (!on)
    function rangesWithWord(ranges, i, on) {
        const w = words[i]
        if (on) {
            // join up with marked neighbours so the gap between them is covered too
            const a = inRanges(ranges, i - 1) ? words[i - 1].e : w.s - 0.02
            const b = inRanges(ranges, i + 1) ? words[i + 1].s : w.e + 0.02
            return normaliseCuts(ranges.concat([[a, b]]))
        }
        const a = inRanges(ranges, i - 1) ? words[i - 1].e + 0.02 : w.s - 0.05
        const b = inRanges(ranges, i + 1) ? words[i + 1].s - 0.02 : w.e + 0.05
        const pieces = []
        for (const r of ranges) {
            const s = r[0], e = r[1]
            if (e <= a || s >= b) { pieces.push([s, e]); continue }
            if (s < a) pieces.push([s, a])
            if (e > b) pieces.push([b, e])
        }
        return normaliseCuts(pieces)
    }

    // click = toggle one word; shift+click = give the whole run from the last click the same state
    // list: "cuts" or "mutes"
    function clickToolWord(list, i, shift) {
        const w = words[i]
        if (!w) return
        const verb = list === "cuts" ? "cut" : "mute"
        if (inT === null || outT === null) { toast(`Pick the clip range first, then ${verb} words inside it.`, "info"); return }
        const inTeaser = list === "mutes" && isTeaserWord(i)
        if ((w.e <= inT || w.s >= outT) && !inTeaser) { toast("That word is outside the clip.", "info"); return }
        // a word in a part deleted with the razor already shows as cut: a cut there could not be seen, and it would
        // stay when the part is restored
        const dropped = k => list === "cuts" && inRanges(drops, k)
        let ranges = store[list]
        const anchor = toolAnchor[list]
        if (shift && anchor >= 0) {
            const on = toolState[list]
            const last = Math.min(Math.max(anchor, i), words.length - 1)
            for (let k = Math.min(anchor, i); k <= last; k++) {
                if (inRanges(ranges, k) !== on && !dropped(k)) ranges = rangesWithWord(ranges, k, on)
            }
        } else {
            if (dropped(i)) { toast("This word is in a deleted part. Restore the part first.", "info"); return }
            const on = !inRanges(ranges, i)
            ranges = rangesWithWord(ranges, i, on)
            toolAnchor = Object.assign({}, toolAnchor, { [list]: i })
            toolState = Object.assign({}, toolState, { [list]: on })
        }
        store[list] = ranges   // one assignment: the transcript, strip and edit state update once
    }

    function clearCuts() { cuts = [] }
    function clearMutes() { mutes = [] }

    // only one word tool at a time: cut, mute, or picking the teaser
    function setCutMode(on) {
        if (on) { if (teaserPick) setTeaserPick(null); if (muteMode) setMuteMode(false) }
        cutMode = on
        if (on) toast("Cut tool on: click words to remove them. Press X to turn it off.", "info")
    }

    function setMuteMode(on) {
        if (on) { if (teaserPick) setTeaserPick(null); if (cutMode) setCutMode(false) }
        muteMode = on
        if (on) toast("Mute tool on: click words to silence them. Press M to turn it off.", "info")
    }

    // how each transcript word looks – the classes the web edition puts on span.w:
    // 1 cut, 2 muted (paintCuts), 4 in the teaser (paintTeaser), 8 search match (applySearch)
    readonly property string introKey: edit.intro ? `${edit.intro[0]},${edit.intro[1]}` : ""
    readonly property var wordFlags: computeWordFlags(words, lines, lineWords, cuts, mutes, introKey, search, drops)

    // bits: 1 cut, 2 muted, 4 teaser, 8 search match, 16 in a part deleted with the razor
    function computeWordFlags(ws, ls, lw, cutList, muteList, intro, query, dropList) {
        const n = ws.length
        const flags = new Array(n).fill(0)
        const teaser = intro ? intro.split(",").map(Number) : null
        // the ranges are sorted and apart (normaliseCuts), the words sorted by time: walk both lists together.
        // Only the first range ending after a word's middle can hold it.
        const mark = (list, bit) => {
            let k = 0, last = -Infinity
            for (let i = 0; i < n; i++) {
                const mid = (ws[i].s + ws[i].e) / 2
                if (mid < last) k = 0   // a word that starts before the one before it ends: look again from the top
                last = mid
                while (k < list.length && list[k][1] <= mid) k++
                if (k < list.length && mid > list[k][0]) flags[i] |= bit
            }
        }
        if (cutList.length) mark(cutList, 1)
        if (muteList.length) mark(muteList, 2)
        if (dropList && dropList.length) mark(dropList, 16)
        if (teaser) {
            for (let i = 0; i < n; i++) {
                const mid = (ws[i].s + ws[i].e) / 2
                if (mid >= teaser[0] && mid <= teaser[1]) flags[i] |= 4
            }
        }
        const q = String(query || "").trim().toLowerCase()
        if (q) {
            // in a line that contains the query, the words that contain one of its words
            const tokens = q.split(/\s+/).map(bare).filter(Boolean)
            if (memo.bareOf !== ws) { memo.bareOf = ws; memo.bareWords = ws.map(w => bare(w.w)) }   // once per transcript
            const bw = memo.bareWords
            for (let li = 0; li < ls.length && li < lw.length; li++) {
                if (!ls[li].text.toLowerCase().includes(q)) continue
                for (let k = lw[li][0]; k < lw[li][1]; k++) {
                    const word = bw[k]
                    if (word && tokens.some(t => word.includes(t))) flags[k] |= 8
                }
            }
        }
        return flags
    }

    // web applySearch's bare(): lower case, letters, digits and ' only. V4 accepts \p{L} but it matches nothing,
    // so the letters and digits are listed as code point ranges (Latin, Greek, Cyrillic, Arabic, CJK, fullwidth)
    readonly property var bareJunk: (function () {
        const c = String.fromCharCode
        const keep = [[0x27, 0x27], [0x30, 0x39], [0x61, 0x7A], [0xAA, 0xAA], [0xB2, 0xB3], [0xB5, 0xB5], [0xB9, 0xBA],
                      [0xBC, 0xBE], [0xC0, 0xD6], [0xD8, 0xF6], [0xF8, 0x60B], [0x620, 0x669], [0x66E, 0x6D3],
                      [0x6D5, 0x963], [0x966, 0x1FFF], [0x2C00, 0x2FFF], [0x3040, 0xD7FF], [0xF900, 0xFE0F],
                      [0xFE70, 0xFEFE], [0xFF10, 0xFF19], [0xFF21, 0xFF3A], [0xFF41, 0xFF5A], [0xFF66, 0xFFEF]]
        return new RegExp("[^" + keep.map(r => c(r[0]) + (r[1] > r[0] ? "-" + c(r[1]) : "")).join("") + "]", "g")
    })()
    function bare(text) { return String(text).toLowerCase().replace(bareJunk, "") }

    // words of the clip that are cut (bit 1) / muted (bit 2) – web paintCuts counts
    function toolCount(bit) {
        if (inT === null || outT === null) return 0
        const ws = words, fl = wordFlags, a = inT, b = outT
        let n = 0
        for (let i = 0; i < ws.length; i++) if ((fl[i] & bit) && ws[i].e > a && ws[i].s < b) n++
        return n
    }
    readonly property int cutCount: toolCount(1)
    readonly property int muteCount: toolCount(2)
    readonly property string cutLabel: cutCount ? `${cutCount} word${cutCount === 1 ? "" : "s"} cut` : "No words cut"
    readonly property string muteLabel: muteCount ? `${muteCount} word${muteCount === 1 ? "" : "s"} muted` : "No words muted"

    // a line in a right-to-left script (Hebrew / Arabic): its words flow from the right
    readonly property var rtlChars: new RegExp("[" + String.fromCharCode(0x0590) + "-" + String.fromCharCode(0x08FF)
                                               + String.fromCharCode(0xFB1D) + "-" + String.fromCharCode(0xFDFF)
                                               + String.fromCharCode(0xFE70) + "-" + String.fromCharCode(0xFEFF) + "]")
    function isRtl(text) { return rtlChars.test(String(text)) }

    // ------------------------------------------------------------ sounds: muted words and background music
    // ported from app.js 1244-1268 and 1406-1414; the stage's PreviewAudio plays them

    // the chosen muted-word sound once (web: playMuteSound's check); pulse = its tile pulses
    function previewMuteSound(toneSeconds, pulse) {
        const s = muteSounds[edit.muteSound]
        if (!s || s.kind === "none") return
        previewSound(toneSeconds, pulse ? edit.muteSound : "")
    }

    // a sound tile: choose it and hear it; Custom without a file asks for one first
    function chooseMuteSound(key) {
        if (key === "custom" && !edit.muteSfx) { pickAudioRequested("sfx-tile"); return }
        setEdit({ muteSound: key })
        previewMuteSound(1.0, true)
    }

    function pickCustomSound() { pickAudioRequested("sfx") }
    function pickMusic() { pickAudioRequested("music") }
    function clearMusic() { setEdit({ music: "" }) }

    // a file chosen in the audio dialog; anything but an audio file the engine takes is ignored, like the web
    function audioPicked(kind, url) {
        const res = backend.checkAudio(url)
        if (!res.path) return
        if (kind === "music") {
            setEdit({ music: res.path })
            toast(`Music: ${res.name}`, "ok")
            return
        }
        setEdit({ muteSfx: res.path, muteSound: "custom" })
        toast(`Muted-word sound: ${res.name}`, "ok")
        previewMuteSound(1.0, kind === "sfx-tile")
    }

    // ------------------------------------------------------------ pop-ups: a picture, GIF or video on top for a moment
    // ported from pro.js 562-667. [{id, at, dur, path, pos, size}]: `at` in source seconds, `dur` in seconds of the
    // finished clip, `pos` top / center / bottom, `size` = width as a share of the frame. Per clip (saved as
    // clip.popups), never copied by "Apply to all"; the stage's PopupLayer shows them.
    property var popups: []
    // path -> {path, name, url, kind: picture|gif|video, exists, plus error (the render can't use it: no url),
    // gif {delays, plays} (its frame times in the render), orient (a PNG / WebP's EXIF orientation), w / h (a video's
    // upright size)} (backend.popupInfo)
    property var popupMedia: ({})
    property var popupSuffixes: []     // clipper.POPUP_SUFFIXES, pictures first (backend.popupTypes)
    property var videoSuffixes: []     // clipper.VIDEO_SUFFIXES
    readonly property string popupFilter: `Pictures and videos (${popupSuffixes.map(s => "*" + s).join(" ")})`
    // false: timed like the web preview, (t - at) / speed from the moment; true: like the render
    // (clipper.popup_occurrences on the finished timeline). They differ only when a cut, a removed pause, the
    // teaser's end or the In point falls inside a pop-up's time.
    property bool popupEngineTiming: true   // the preview shows pop-ups exactly when the render does

    function loadPopupTypes() {
        const d = backend.popupTypes()
        popupSuffixes = d.popup
        videoSuffixes = d.video
    }

    // web isVideoFile, plus GIFs (they animate)
    function popupKind(path) {
        const m = /\.[A-Za-z0-9]+$/.exec(String(path || ""))
        const ext = m ? m[0].toLowerCase() : ""
        return videoSuffixes.indexOf(ext) >= 0 ? "video" : ext === ".gif" ? "gif" : "picture"
    }

    function popupName(path) { return String(path || "").split(/[\\/]/).pop() }

    // the file URL, kind and existence of each pop-up's file (asked again on every load: a file can go missing)
    function lookupPopupMedia(list) {
        const cache = Object.assign({}, popupMedia)
        for (const p of list) {
            const info = backend.popupInfo(String(p.path || ""))
            cache[p.path] = info.path ? info
                : { path: p.path, name: popupName(p.path), url: "", kind: popupKind(p.path), exists: false }
        }
        popupMedia = cache
    }

    // "Add at playhead": the moment is taken before the file is picked; null = not inside the clip
    function popupAddTime() {
        const at = round(playhead, 2)
        if (inT === null || outT === null || at < inT || at > outT) {
            toast("Move the playhead inside the clip first.", "info")
            return null
        }
        return at
    }

    // the picked file (a file: URL or a path) becomes a pop-up at `at`; other file types are ignored, like the web
    function addPopupFile(file, at) {
        const info = backend.popupInfo(String(file))
        if (!info.path) return
        if (info.error) {   // e.g. an animated WebP: ffmpeg can't decode it, so the render would refuse the clip
            toast(info.error, "error")
            return
        }
        popupMedia = Object.assign({}, popupMedia, { [info.path]: info })
        const list = popups.concat([{ id: Math.random().toString(36).slice(2, 10), at: at, dur: 1.5, path: info.path,
                                      pos: "center", size: 0.8 }])
        // by time; equal times keep their order (V4's sort is not guaranteed to be stable)
        popups = list.map((p, i) => [p, i]).sort((a, b) => a[0].at - b[0].at || a[1] - b[1]).map(x => x[0])
    }

    function setPopup(i, changes) {
        if (i < 0 || i >= popups.length) return
        const list = popups.slice()
        list[i] = Object.assign({}, list[i], changes)
        popups = list
    }

    function removePopup(i) {
        if (i < 0 || i >= popups.length) return
        const list = popups.slice()
        list.splice(i, 1)
        popups = list
    }

    // seconds since pop-up p appeared, with the playhead at source time t (< 0 or > p.dur: not on screen).
    // ed = editState(), out = clipTime(t, ed), not null. Web rule (pro.js drawPopups): (t - at) / speed.
    function popupLocal(p, t, ed, out) {
        if (!popupEngineTiming) return (t - p.at) / ed.speed
        // clipper.popup_occurrences: it starts on the finished timeline (teaser first, cuts gone, speed applied),
        // once per piece holding `at` – twice when it is inside the teaser
        const pieces = (ed.intro ? [[ed.intro[0], ed.intro[1], 1]] : []).concat(ed.segs || [])
        let start = -1, offset = 0
        for (const piece of pieces) {
            if (piece[0] <= p.at && p.at < piece[1]) {
                const s = (offset + p.at - piece[0]) / ed.speed
                if (s <= out + 0.000001) start = s
            }
            offset += piece[1] - piece[0]
        }
        return start < 0 ? -1 : out - start
    }

    // 0.15 s fade in and out (web drawPopups, edit_graph fade=t=in / t=out)
    function popupAlpha(p, local) {
        return clamp(Math.min(local / 0.15, (p.dur - local) / 0.15), 0, 1)
    }

    // where pop-up p sits in a w x h (9:16) preview; iw x ih = the file's own size. Centred, size x the frame wide,
    // its top 330 output px down / centred / its bottom 700 px up – same as clipper.edit_graph
    function popupBox(p, iw, ih, w, h) {
        const k = w / 1080
        const bw = w * p.size, bh = iw ? bw * ih / iw : 0
        const y = p.pos === "top" ? 330 * k : p.pos === "bottom" ? h - bh - 700 * k : (h - bh) / 2
        return { x: (w - bw) / 2, y: y, w: bw, h: bh }
    }

    // ------------------------------------------------------------ campaigns (web pro.js): Whop rules for each clip
    property var campaigns: []
    readonly property string campaignId: video && video.campaign ? video.campaign : ""
    readonly property var currentCampaign: campaignId ? campaigns.find(c => c.id === campaignId) || null : null

    function loadCampaigns() { campaigns = backend.campaigns() }

    // ask first, then run action() on yes (Main.qml shows the question)
    function ask(title, text, okText, action) { askRequested(title, text, okText, action) }

    // the same rules as library.check_clip, live on the clip being edited (web pro.js checkClip)
    function checkClip(clip, camp, duration) {
        if (!camp) return []
        const out = []
        if (camp.min_len && duration < camp.min_len - 0.05)
            out.push({ level: "error", text: `Too short: ${duration.toFixed(1)}s – needs ${camp.min_len}s+` })
        if (camp.max_len && duration > camp.max_len + 0.05)
            out.push({ level: "error", text: `Too long: ${duration.toFixed(1)}s – max ${camp.max_len}s` })
        const tags = (camp.tags || "").split(/[\s,]+/).filter(Boolean)
        const post = (clip.post_caption || "").toLowerCase()
        const missing = tags.filter(t => !post.includes(t.toLowerCase()))
        if (missing.length) out.push({ level: "warn", text: `Post caption is missing ${missing.join(" ")}` })
        if (camp.watermark && !(clip.watermark || "").toLowerCase().includes(camp.watermark.toLowerCase()))
            out.push({ level: "error", text: `Watermark must include “${camp.watermark}”` })
        if (camp.no_hook && (clip.hook || "").trim()) out.push({ level: "error", text: "Hook text on top is not allowed" })
        if (camp.need_captions && clip.captions === false) out.push({ level: "error", text: "Captions are required" })
        if (camp.max_speed && (clip.speed || 1) > camp.max_speed + 0.001)
            out.push({ level: "error", text: `Speed above ${camp.max_speed}×` })
        return out
    }

    // the rule problems of the clip being edited, or null (no campaign / no range)
    function liveChecks() {
        const camp = currentCampaign
        if (!camp || inT === null || outT === null || outT <= inT) return null
        return checkClip(clipFields(), camp, editState().duration)
    }

    function saveCampaign(data) {
        const res = backend.saveCampaign(JSON.stringify(data))
        if (res.error) { toast(res.error, "error"); return null }
        loadCampaigns()
        poll()   // the cards' rule checks
        toast(`Saved “${res.campaign.name}”`, "ok")
        return res.campaign
    }

    function deleteCampaign(id) {
        const res = backend.deleteCampaign(id)
        if (res.error) { toast(res.error, "error"); return false }
        loadCampaigns()
        poll()
        return true
    }

    // "Use for this video" ("" = no campaign)
    function useCampaign(id) {
        const res = backend.setProjectCampaign(id)
        if (res.error) { toast(res.error, "error"); return }
        poll()
        const camp = campaigns.find(c => c.id === id)
        toast(camp ? `This video now uses “${camp.name}” – every clip is checked against its rules.`
                   : "Campaign removed from this video.", "ok")
    }

    // Render all / a card's render button: warn first when a clip breaks the campaign's rules
    function renderSome(list) {
        const bad = list.filter(c => (c.checks || []).some(x => x.level === "error"))
        const go = () => renderClips(list.map(c => c.name))
        if (!bad.length) { go(); return }
        ask("Break the campaign rules?",
            list.length === 1 ? `${bad[0].name} breaks the campaign rules:\n• ${bad[0].checks.filter(x => x.level === "error").map(x => x.text).join("\n• ")}\n\nRender it anyway?`
                              : `${bad.length} clip${bad.length === 1 ? "" : "s"} break the campaign rules (${bad.map(c => c.name).join(", ")}).\n\nRender all anyway?`,
            "Render anyway", go)
    }

    // ------------------------------------------------------------ earnings tracker (web pro.js)
    property var trackerEntries: []
    property var postTarget: null       // the clip "Mark as posted" is for

    function loadTracker() {
        const data = backend.tracker()
        trackerEntries = data.entries
        campaigns = data.campaigns
    }

    // a post's earnings: what was typed in, else views x the campaign's pay per 1,000 views
    function earned(entry) {
        if (entry.earned !== null && entry.earned !== undefined) return entry.earned
        const camp = campaigns.find(c => c.id === entry.campaign)
        return camp ? entry.views / 1000 * camp.cpm : 0
    }

    // 12345.6 -> "12,345.60" (money) or "12,346" (count)
    function grouped(value, decimals) {
        const fixed = Math.abs(value || 0).toFixed(decimals)
        const parts = fixed.split(".")
        let whole = parts[0], out = ""
        while (whole.length > 3) { out = "," + whole.slice(-3) + out; whole = whole.slice(0, -3) }
        return (value < 0 ? "-" : "") + whole + out + (parts.length > 1 ? "." + parts[1] : "")
    }
    function money(value) { return "$" + grouped(value, 2) }
    function count(value) { return grouped(Math.round(value || 0), 0) }

    // the queue card's ✓ button
    function askPosted(clip) { postTarget = clip; dialogRequested("posted") }

    function postClip(clip, platform, url, views) {
        const st = clip.status || {}
        const length = typeof st.length === "number" ? st.length : clip.end - clip.start   // the finished length
        const res = backend.saveEntry(JSON.stringify({
            campaign: campaignId || null, project: videoKey, clip: clip.name, platform: platform, url: url.trim(),
            posted: Qt.formatDate(new Date(), "yyyy-MM-dd"), views: views, style: clip.caption_style || "classic",
            layout: clip.layout, length: round(length, 1), hook: clip.hook || "",
            teaser: clip.intro_start !== null && clip.intro_start !== undefined
        }))
        if (res.error) { toast(res.error, "error"); return false }
        toast(`${clip.name} added to the earnings tracker.`, "ok")
        return true
    }

    function setViews(entry, views) {
        const res = backend.saveEntry(JSON.stringify(Object.assign({}, entry, { views: Math.max(0, Math.round(views || 0)) })))
        if (res.error) toast(res.error, "error")
        loadTracker()
    }

    function deleteEntry(id) {
        const res = backend.deleteEntry(id)
        if (res.error) toast(res.error, "error")
        loadTracker()
    }

    // ------------------------------------------------------------ export pack (web pro.js)
    // every rendered clip with a clear name + captions.txt (post captions with the campaign's tags) in
    // clipper/exports/ – a folder, or one ZIP; the folder opens when it is done
    function exportPack(zip) {
        const res = backend.exportPack(zip)
        if (res.error) { toast(res.error, "error"); return }
        toast(`Exported to ${res.path.split(/[\\/]/).slice(-2).join(" / ")}`, "ok")
    }

    // ------------------------------------------------------------ viral moments (web pro.js): free and AI picks
    readonly property string momentsHelp: "Free picks score every sentence-to-sentence stretch for a strong opening line, "
                                          + "keywords, energy and a punchy ending."
    property var moments: []
    property var momentsAdded: ({})     // index -> true once that moment is in the queue
    property string momentsNote: momentsHelp
    property bool aiBusy: false
    property int momentsSeq: 0          // an older, slower search must not overwrite a newer one

    function findMoments(count, minLen, maxLen) {
        momentsSeq++
        aiBusy = false
        const res = backend.moments(count, minLen, maxLen)
        if (res.error) { toast(res.error, "error"); return }
        moments = res.moments
        momentsAdded = ({})
        momentsNote = "Free picks: ranked by opening line, keywords, energy, pace and ending."
    }

    function aiMoments(count, minLen, maxLen) {
        if (!backend.settings().has_key) {
            toast("Add your Anthropic API key in Settings first.", "info")
            dialogRequested("settings")
            return
        }
        const seq = ++momentsSeq
        const res = backend.aiMoments(count, minLen, maxLen)
        if (res.error) { toast(res.error, "error"); return }
        memo.aiSeq = seq
        aiBusy = true
        moments = []
        momentsAdded = ({})
        momentsNote = "Claude is reading the transcript… (about a minute)"
    }

    // backend.aiMomentsDone: the AI picks came back (or failed)
    function aiMomentsDone(res) {
        if (memo.aiSeq !== momentsSeq) return
        aiBusy = false
        if (res.error) { toast(res.error, "error"); momentsNote = "The AI picks failed – free picks still work."; return }
        moments = res.moments
        momentsAdded = ({})
        momentsNote = `AI picks by Claude · this request cost about $${Number(res.cost).toFixed(2)}.`
    }

    // Preview: the moment becomes the clip being edited (not saved) and plays
    function previewMoment(m) {
        newClip(false)
        setRange(m.start, m.end)
        hookText = m.hook || ""
        postText = m.post_caption || ""
        seekRequested(m.start)
        playRequested()
    }

    // Add / Add all: each moment becomes a queued clip with its hook and post caption (the editor's other
    // settings, like the web edition). indexes: which rows to mark as added
    function addMoments(list, indexes) {
        if (!list.length) return
        const taken = new Set(clips.map(c => c.name))
        const made = list.map(m => {
            newClip(false)
            setRange(m.start, m.end)
            hookText = m.hook || ""
            postText = m.post_caption || ""
            let n = 1
            while (taken.has(`clip_${String(n).padStart(2, "0")}`)) n++
            clipName = `clip_${String(n).padStart(2, "0")}`
            taken.add(clipName)
            return clipFields()
        })
        const ok = saveClips(clips.map(stripStatus).concat(made))
        newClip(true)
        if (!ok) return
        const added = Object.assign({}, momentsAdded)
        for (const i of indexes) added[i] = true
        momentsAdded = added
        toast(made.length === 1 ? `Added ${made[0].name} to the queue` : `Added ${made.length} clips to the queue – check them, then Render all.`, "ok")
    }

    // ------------------------------------------------------------ undo / redo (web pro.js): editor snapshots
    property var history: ({ undo: [], redo: [], current: null, pending: null, stable: 0, restoring: false })
    property int undoCount: 0
    property int redoCount: 0

    function editorSnapshot() { return video ? JSON.stringify({ editing: editing, clip: clipFields() }) : null }

    // every 250 ms (Main.qml): once the editor has stayed the same for a moment, that state becomes an undo
    // step – so dragging a slider makes one step, not hundreds
    function historyTick() {
        const h = history
        if (h.restoring || !video) return
        const snap = editorSnapshot()
        if (snap !== h.pending) { h.pending = snap; h.stable = 0; return }
        if (++h.stable === 1 && snap !== h.current) {
            if (h.current) { h.undo.push(h.current); if (h.undo.length > 150) h.undo.shift() }
            h.current = snap
            h.redo = []
            historyCounts()
        }
    }

    function historyCounts() { undoCount = history.undo.length; redoCount = history.redo.length }

    function restoreSnapshot(snap) {
        const h = history
        h.restoring = true
        const s = JSON.parse(snap)
        applyClip(s.clip, true)
        editing = s.editing
        h.current = h.pending = snap
        h.restoring = false
        historyCounts()
    }

    function undo() {
        const h = history
        if (!h.undo.length) return
        h.redo.push(h.current)
        restoreSnapshot(h.undo.pop())
    }

    function redo() {
        const h = history
        if (!h.redo.length) return
        h.undo.push(h.current)
        restoreSnapshot(h.redo.pop())
    }

    function resetHistory() {
        history = { undo: [], redo: [], current: null, pending: null, stable: 0, restoring: false }
        historyCounts()
    }

    // ------------------------------------------------------------ queue
    function nextName() {
        const taken = new Set(clips.map(c => c.name))
        let n = 1
        while (taken.has(`clip_${String(n).padStart(2, "0")}`)) n++
        return `clip_${String(n).padStart(2, "0")}`
    }

    function newClip(clearRange) {
        editing = ""
        clipName = nextName()
        hookText = ""
        postText = ""
        extra = ({})
        keyframes = []
        popups = []
        cuts = []
        mutes = []
        drops = []
        splits = []
        selectedPart = -1
        toolAnchor = ({ cuts: -1, mutes: -1 })
        setEdit({ intro: null })  // the other edit settings stay for the next clip, like the web edition
        if (clearRange) setRange(null, null)
    }

    function clipFields() {
        return Object.assign({}, extra, {
            name: safeName(clipName), start: inT, end: outT, layout: layout, crop_x: round(cropX, 3),
            frame_y: round(frameY, 3), frame_zoom: frameZoom, hook: hookText.trim(), post_caption: postText.trim(),
            captions: captionsOn, caption_style: cap.style, caption_color: cap.color, caption_size: cap.size,
            caption_pos: cap.pos, kw_highlight: kw.on, kw_color: kw.color, emojis: kw.emojis,
            hook_style: hook.style, hook_size: hook.size, hook_pos: hook.pos, hook_duration: hook.duration,
            keyframes: keyframes.map(k => ({ t: k.t, x: k.x, y: k.y })),
            popups: popups.map(p => ({ id: p.id, at: p.at, dur: p.dur, path: p.path, pos: p.pos, size: p.size }))
        }, editFields())
    }

    readonly property var editedKeys: ["name", "start", "end", "layout", "crop_x", "frame_y", "frame_zoom", "hook",
        "post_caption", "captions", "caption_style", "caption_color", "caption_size", "caption_pos", "kw_highlight",
        "kw_color", "emojis", "hook_style", "hook_size", "hook_pos", "hook_duration", "status", "checks", "keyframes",
        "popups", "cuts", "remove_pauses", "pause_min", "zoom", "zoom_amount", "speed", "progress", "progress_color", "music",
        "music_volume", "watermark", "watermark_pos", "intro_start", "intro_end", "intro_flash", "mutes", "mute_mode",
        "mute_captions", "mute_sfx", "mute_sfx_volume", "drops", "splits"]

    // quiet: undo / redo – no seek, no transcript scroll
    function applyClip(clip, quiet) {
        editing = clip.name
        clipName = clip.name
        setRange(clip.start, clip.end)
        layout = clip.layout || "crop"
        cropX = clip.crop_x !== undefined ? clip.crop_x : 0.5
        frameY = clip.frame_y !== undefined ? clip.frame_y : 0.5
        keyframes = savedList(clip.keyframes).filter(k => k && typeof k === "object")
            .map(k => ({ t: k.t, x: k.x, y: k.y })).sort((a, b) => a.t - b.t)
        setFrameZoom(clip.frame_zoom || 1)
        hookText = clip.hook || ""
        postText = clip.post_caption || ""
        captionsOn = clip.captions !== false
        cap = { style: clip.caption_style || defaultStyle, color: clip.caption_color || null,
                size: clip.caption_size || 100, pos: clip.caption_pos !== undefined ? clip.caption_pos : null }
        kw = { on: !!clip.kw_highlight, color: clip.kw_color || "#39FF14", emojis: !!clip.emojis }
        editFromClip(clip)
        hook = { style: clip.hook_style || defaultHook, size: clip.hook_size || 100,
                 pos: clip.hook_pos !== undefined ? clip.hook_pos : null, duration: clip.hook_duration || 0 }
        const pops = savedList(clip.popups).filter(p => p && typeof p === "object")
            .map(p => ({ id: p.id, at: p.at, dur: p.dur, path: p.path, pos: p.pos, size: p.size }))
        lookupPopupMedia(pops)   // before the list, so the preview finds the files on its first pass
        popups = pops
        const rest = {}
        for (const key in clip) if (editedKeys.indexOf(key) < 0) rest[key] = clip[key]
        extra = rest
        if (quiet) return
        seekRequested(clip.start)
        const first = lines.findIndex(l => l.e > clip.start)
        if (first >= 0) showLine(first)
    }

    function setClips(list) {
        const sig = JSON.stringify(list)
        if (sig === clipsSig) return
        clipsSig = sig
        clips = list
    }

    // (a row of the old list can ask once more while another video's lines come in)
    function lineSelected(i) {
        const line = lines[i]
        return !!line && inT !== null && outT !== null && Math.min(line.e, outT) - Math.max(line.s, inT) > 0.3
    }

    function lineText(i) {
        const range = lineWords[i]
        if (!range || range[0] === range[1]) return lines[i].text
        return words.slice(range[0], range[1]).map(w => w.w).join(" ")
    }

    function lineQueued(i) {
        const line = lines[i]
        return !!line && clips.some(c => line.e > c.start && line.s < c.end)
    }

    function stripStatus(clip) {
        const copy = Object.assign({}, clip)
        delete copy.status
        delete copy.checks
        return copy
    }

    function saveClips(list) {
        const res = backend.saveClips(JSON.stringify(list.map(stripStatus)))
        if (res.error) { toast(res.error, "error"); return false }
        setClips(res.clips)
        return true
    }

    // Add to queue / Render clip; a render that breaks the campaign's rules asks first
    function addClip(andRender) {
        const errors = andRender ? (liveChecks() || []).filter(c => c.level === "error") : []
        if (!errors.length) { addClipNow(andRender); return }
        ask("Break the campaign rules?", `This clip breaks the campaign rules:\n• ${errors.map(c => c.text).join("\n• ")}\n\nRender it anyway?`,
            "Render anyway", () => addClipNow(true))
    }

    function addClipNow(andRender) {
        const name = safeName(clipName)
        if (!name) { toast("Give the clip a name", "error"); return }
        if (inT === null || outT === null) { toast("Pick a start and an end first", "error"); return }
        if (outT <= inT) { toast("The end must be after the start", "error"); return }
        const segs = editState().segs
        if (!segs || !segs.length) { toast("Everything in this clip has been cut out", "error"); return }
        const clip = clipFields()
        const list = clips.map(stripStatus)
        const key = editing || name
        const dupe = list.findIndex(c => c.name === name && c.name !== key)
        if (dupe !== -1) list.splice(dupe, 1)
        const idx = list.findIndex(c => c.name === key)
        if (idx === -1) list.push(clip); else list[idx] = clip
        if (!saveClips(list)) return
        if (andRender) {
            editing = name
            renderClips([name])
        } else if (editing) {
            editing = name
            toast(`Saved ${name}`, "ok")
        } else {
            toast(`Added ${name} to the queue`, "ok")
            newClip(true)
        }
    }

    function captionFields() {
        return { captions: captionsOn, caption_style: cap.style, caption_color: cap.color, caption_size: cap.size,
                 caption_pos: cap.pos, kw_highlight: kw.on, kw_color: kw.color, emojis: kw.emojis }
    }

    function hookFields() {
        return { hook_style: hook.style, hook_size: hook.size, hook_pos: hook.pos, hook_duration: hook.duration }
    }

    // copy some settings (not the range or text) onto every queued clip
    function applyToAll(fields, what) {
        if (!clips.length) { toast("The queue is empty.", "info"); return }
        const n = clips.length
        if (saveClips(clips.map(c => Object.assign(stripStatus(c), fields))))
            toast(`${what} applied to ${n} clip${n === 1 ? "" : "s"}. Render them again to update the videos.`, "ok")
    }

    function deleteClip(name) {
        if (editing === name) newClip(false)
        saveClips(clips.filter(c => c.name !== name))
    }

    function renderClips(names) {
        const res = backend.render(JSON.stringify(names))
        if (res.error) toast(res.error, "error")
        else poll()
    }

    // ------------------------------------------------------------ opening / transcribing
    function openVideo(path) {
        const res = backend.openVideo(path)
        if (res.error) toast(res.error, "error")
        else poll()
    }

    function transcribe(lang) {
        const res = backend.transcribe(lang)
        if (res.error) toast(res.error, "error")
        else poll()
    }

    function editLine(index, text) {
        const line = lines[index]
        const res = backend.editLine(line.s, line.e, text)
        if (res.error) { toast(res.error, "error"); return }
        toast(text ? "Caption text fixed" : "Words removed from the captions", "ok")
        poll()
    }

    Component.onCompleted: { loadStyles(); loadPopupTypes(); loadCampaigns(); backend.aiMomentsDone.connect(aiMomentsDone) }
}
