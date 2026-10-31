import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Effects
import QtMultimedia
import "."

// The 9:16 preview (drag to move the video, scroll to zoom), transport and the waveform.
Panel {
    id: stage
    showHeader: false

    property real seekTarget: -1      // the player reports the old position for a moment after a seek
    property real seekUntil: 0
    property real pendingSeek: -1     // a seek asked for before the video was loaded
    property real punch: 1            // zoom punch-in of the piece under the playhead (1 = none)
    property real posBase: 0          // the position the player last reported (s) ...
    property real posWall: 0          // ... when it came (Date.now() ms) ...
    property bool posMoving: false    // ... and whether the video was playing on from there
    property real posFloor: -1        // the last run-on position (it never steps back between two reports)

    // every tick, after the playback rules: t = source seconds, out = seconds on the finished clip (null
    // outside it), ed = Store.editState() – the same values the overlay, pop-ups and sounds get (web: HOOKS.overlay).
    signal ticked(real t, var out, var ed)
    signal seeked()                   // a seek / jump has landed (web: the video's "seeked" event)

    readonly property bool loaded: player.mediaStatus === MediaPlayer.LoadedMedia || player.mediaStatus === MediaPlayer.BufferedMedia
                                   || player.mediaStatus === MediaPlayer.BufferingMedia || player.mediaStatus === MediaPlayer.EndOfMedia

    // a manual seek (transcript, strip, buttons, keys): leaves the teaser – web: seek()
    function seek(t) {
        if (!Store.duration) return
        Store.inIntro = false
        jump(t)
    }

    // move the playhead without touching the teaser state – web: video.currentTime = t
    function jump(t) {
        t = Store.clamp(t, 0, Math.max(0, Store.duration - 0.05))
        Store.playhead = t
        if (!loaded) { pendingSeek = t; return }
        seekTarget = t
        seekUntil = Date.now() + 400
        posFloor = -1
        player.setPosition(Math.round(t * 1000))
    }

    function play() {
        if (Store.mediaUrl) player.play()
    }

    function pause() { player.pause() }

    // the start of the finished clip: the teaser if there is one, else the first kept piece – web: playFromClipStart()
    function playFromClipStart(ed) {
        if (ed.intro) {
            Store.inIntro = true
            jump(ed.intro[0])
        } else {
            Store.inIntro = false
            jump(ed.segs && ed.segs.length ? ed.segs[0][0] : Store.inT)
        }
    }

    // web: togglePlay() – with Loop on, play from outside the clip (or from its start when it has a teaser)
    // starts the finished clip from its beginning
    function togglePlay() {
        if (!Store.mediaUrl) return
        if (player.playbackState === MediaPlayer.PlayingState) { player.pause(); return }
        const t = Store.playhead
        const ed = Store.editState()
        const atStart = Store.inT !== null && Math.abs(t - Store.inT) < 0.05
        const outside = Store.inT !== null && Store.outT !== null && (t < Store.inT - 0.05 || t >= Store.outT - 0.05)
        if (Store.loop && !Store.inIntro && (outside || (atStart && ed.intro))) playFromClipStart(ed)
        player.play()
    }

    // while playing inside the clip: jump over the parts that are cut out, leave the teaser when it ends,
    // loop (or stop) at the end – web: skipCutParts(), same thresholds. seekTarget >= 0 = video.seeking.
    // Without Loop it stops where the finished clip ends – the end of the last kept piece, which is before Out when
    // the last part is deleted (or cut, or a pause there removed) – where the web plays on to Out.
    function skipCutParts(t) {
        if (!Store.playing || seekTarget >= 0 || Store.inT === null || Store.outT === null || Store.outT <= Store.inT) return
        const ed = Store.editState()
        const segs = ed.segs
        if (!segs || !segs.length) return
        if (Store.inIntro) {  // teaser playing: when it ends, the clip starts from the beginning
            if (!ed.intro) { Store.inIntro = false; return }
            if (t >= ed.intro[1] - 0.02 || t < ed.intro[0] - 0.5) {
                Store.inIntro = false
                jump(segs[0][0])
            }
            return
        }
        if (t < Store.inT - 0.05) return
        const lastEnd = segs[segs.length - 1][1]
        if (t >= lastEnd - 0.02) {
            if (Store.loop) playFromClipStart(ed)
            else {
                player.pause()
                if (t < Store.outT) jump(lastEnd)   // after Out (played on from outside the clip) it just stops
            }
            return
        }
        if (!segs.some(sg => t >= sg[0] - 0.03 && t < sg[1])) {
            const next = segs.find(sg => sg[0] > t)
            if (next) jump(next[0])
        }
    }

    // the video ran out before a tick caught the end of a clip (or teaser) that ends with it: Qt stops there, so
    // go on the way skipCutParts would have – the clip after the teaser, or the loop. A jump a tick already made is
    // made again, since the end status can come after it (play() at the end status starts from 0).
    function mediaEnded() {
        if (Store.inT === null || Store.outT === null || Store.outT <= Store.inT) return
        const ed = Store.editState()
        if (!ed.segs || !ed.segs.length) return
        if (seekTarget >= 0) jump(seekTarget)
        else if (Store.inIntro && ed.intro) { Store.inIntro = false; jump(ed.segs[0][0]) }
        else if (Store.loop) playFromClipStart(ed)
        else return
        player.play()
    }

    // where the video is now: Qt reports the position only every ~60 ms while playing, so run on from the
    // last report (at most 0.12 s) – the browser's currentTime is that smooth. Right after a seek the player
    // can stall, and the next report may land a little behind the run-on: hold still instead of stepping back.
    function livePosition() {
        if (!posMoving || player.playbackState !== MediaPlayer.PlayingState) { posFloor = -1; return player.position / 1000 }
        let t = posBase + Math.min(0.12, (Date.now() - posWall) / 1000) * player.playbackRate
        if (t < posFloor && t > posFloor - 0.3) t = posFloor
        posFloor = t
        return t
    }

    // ~33 times a second: playhead, playback rules, live transcript line, zoom punch-in, overlay
    function tick() {
        let t = livePosition()
        if (seekTarget >= 0) {
            if (Math.abs(t - seekTarget) < 0.12 || Date.now() > seekUntil) { seekTarget = -1; seeked() }
            else t = seekTarget
        }
        skipCutParts(t)
        if (seekTarget >= 0) t = seekTarget   // it just jumped: show the new spot straight away
        if (Math.abs(t - Store.playhead) > 0.0005) Store.playhead = t
        if (Store.lines.length) {
            const idx = Store.lastAtOrBefore(Store.lines, t + 0.05, l => l.s)
            if (idx !== Store.liveLine) Store.liveLine = idx
        }
        const ed = Store.editState()
        if (Store.inIntro && !ed.intro) Store.inIntro = false   // the teaser was removed (also while paused)
        const out = Store.clipTime(t, ed)
        // zoom punch-in of the piece under the playhead (never during the teaser) – web: drawPreview()
        const piece = out !== null && !Store.inIntro ? ed.segs.find(sg => t >= sg[0] - 0.01 && t <= sg[1] + 0.01) : null
        const z = piece ? piece[2] : 1
        if (z !== punch) punch = z
        overlay.refresh(t, out, ed)
        popupLayer.refresh(t, out, ed)
        sounds.tick(t, out, ed)
        ticked(t, out, ed)
    }

    onSeeked: if (Store.playing) sounds.syncMusic(Store.playhead)   // web: "seeked" while playing -> syncMusic()

    // muted words, their sounds and the background music
    PreviewAudio { id: sounds }

    Connections {
        target: Store
        function onSeekRequested(t) { stage.seek(t) }
        function onJumpRequested(t) { stage.jump(t) }
        function onPlayRequested() { stage.play() }
        function onPauseRequested() { stage.pause() }
        function onVideoKeyChanged() { player.stop(); stage.pendingSeek = 0; Store.playhead = 0; Store.inIntro = false }
    }

    MediaPlayer {
        id: player
        source: Store.mediaUrl
        videoOutput: videoOut
        audioOutput: AudioOutput { volume: 1.0; muted: sounds.silenceVideo }   // web: video.muted on muted words
        playbackRate: Store.edit.speed          // web: video.playbackRate = S.edit.speed
        pitchCompensation: true                 // voices keep their pitch, like the browser and the render (atempo)
        onPositionChanged: {
            stage.posBase = player.position / 1000
            stage.posWall = Date.now()
            stage.posMoving = player.playbackState === MediaPlayer.PlayingState
        }
        onPlaybackStateChanged: {
            Store.playing = player.playbackState === MediaPlayer.PlayingState
            stage.posBase = player.position / 1000
            stage.posWall = Date.now()
            stage.posMoving = false           // wait for the first real step before running on
            if (Store.playing) sounds.syncMusic(Store.playhead)   // web: "play" -> syncMusic(), "pause" -> music.pause()
            else sounds.pauseMusic()
        }
        onMediaStatusChanged: {
            // a stopped player shows nothing: pausing it puts the first frame on screen
            if (mediaStatus === MediaPlayer.LoadedMedia && playbackState === MediaPlayer.StoppedState) pause()
            if (stage.loaded && stage.pendingSeek >= 0) {
                const t = stage.pendingSeek
                stage.pendingSeek = -1
                stage.jump(t)
            }
            if (mediaStatus === MediaPlayer.EndOfMedia) stage.mediaEnded()
        }
        onErrorOccurred: (error, errorString) => Store.toast(`Preview: ${errorString}`, "error")
    }

    Timer { interval: 30; running: true; repeat: true; onTriggered: stage.tick() }

    component Chip: Rectangle {
        id: chip
        property string text: ""
        property bool on: false
        property bool compact: false
        readonly property real wideWidth: chipText.implicitWidth + 22
        signal toggled()
        implicitWidth: chipText.implicitWidth + (compact ? 10 : 22)
        implicitHeight: 28
        radius: 8
        color: on ? Theme.cyanSoft : chipArea.containsMouse ? Qt.rgba(0, 229 / 255, 1, 0.05) : "transparent"
        border.color: on ? Qt.rgba(0, 229 / 255, 1, 0.5) : Theme.line2
        Text {
            id: chipText
            anchors.centerIn: parent
            text: chip.text
            color: chip.on ? Theme.cyan : Theme.muted
            font.family: Theme.display
            font.pixelSize: 11
            font.weight: Font.DemiBold
            font.letterSpacing: 1.2
            font.capitalization: Font.AllUppercase
        }
        MouseArea { id: chipArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: chip.toggled() }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 10

        Item {
            id: view
            Layout.fillWidth: true
            Layout.fillHeight: true

            Rectangle {
                id: phone
                height: Math.min(view.height, view.width * 16 / 9)
                width: height * 9 / 16
                anchors.centerIn: parent
                color: "black"
                clip: true

                readonly property real vw: Store.info ? Store.info.width : 0
                readonly property real vh: Store.info ? Store.info.height : 0
                readonly property bool portrait: vw > 0 && vw / vh <= 9 / 16 + 0.01
                readonly property var g: {
                    if (!vw) return { mode: "none", x: 0, y: 0, w: 0, h: 0 }
                    if (portrait) {
                        const s = Math.min(width / vw, height / vh)
                        return { mode: "portrait", w: vw * s, h: vh * s, x: (width - vw * s) / 2, y: (height - vh * s) / 2 }
                    }
                    return Store.frameGeometry(vw, vh, width, height)
                }

                // no video yet: faint grid
                Canvas {
                    anchors.fill: parent
                    visible: !Store.mediaUrl
                    onWidthChanged: requestPaint()
                    onHeightChanged: requestPaint()
                    onPaint: {
                        const c = getContext("2d")
                        c.reset()
                        c.strokeStyle = "rgba(130,170,255,0.07)"
                        c.lineWidth = 1
                        const step = width / 18
                        for (let x = 0; x <= width; x += step) { c.beginPath(); c.moveTo(x, 0); c.lineTo(x, height); c.stroke() }
                        for (let y = 0; y <= height; y += step) { c.beginPath(); c.moveTo(0, y); c.lineTo(width, y); c.stroke() }
                    }
                }

                // the video, scaled for zoom punch-ins around the centre / upper third like the render
                // (clipper.ZOOM_CENTER_Y = 0.35); captions and the rest stay unscaled on top
                Item {
                    id: punchLayer
                    anchors.fill: parent
                    transform: Scale {
                        origin.x: punchLayer.width / 2
                        origin.y: punchLayer.height * 0.35
                        xScale: stage.punch
                        yScale: stage.punch
                    }

                    // fit + blur: a blurred copy of the video covers the frame behind it, like the render
                    // (clipper.layout_filter: scale to cover 1080x1920, centre crop, boxblur=24:2). It is blurred at a
                    // fixed size – a quarter of the output frame, 270x480 – and then scaled onto the phone, so it looks
                    // the same at every fit zoom and window size. Made only while needed: a live effect whose source is
                    // set to null warns "not assigned a valid texture provider"
                    Loader {
                        active: phone.g.mode === "fit" && stage.loaded
                        sourceComponent: Item {
                            readonly property real s: Math.max(270 / phone.vw, 480 / phone.vh)
                            width: Math.round(phone.vw * s)
                            height: Math.round(phone.vh * s)
                            transformOrigin: Item.TopLeft
                            scale: phone.width / 270
                            x: (phone.width - width * scale) / 2
                            y: (phone.height - height * scale) / 2
                            ShaderEffectSource {
                                id: bgSource
                                anchors.fill: parent
                                sourceItem: videoOut
                                textureSize: Qt.size(width, height)
                                visible: false
                            }
                            MultiEffect {
                                anchors.fill: parent
                                source: bgSource
                                autoPaddingEnabled: false
                                blurEnabled: true
                                blur: 1.0
                                blurMax: 28                // matched to boxblur=24:2 on frames from the render
                            }
                        }
                    }

                    VideoOutput {
                        id: videoOut
                        x: phone.g.x
                        y: phone.g.y
                        width: phone.g.w
                        height: phone.g.h
                        fillMode: VideoOutput.Stretch
                    }
                }

                // pop-ups: above the video (and its punch-in zoom), under the captions – like the render
                PopupLayer {
                    id: popupLayer
                    anchors.fill: parent
                }

                CaptionOverlay {
                    id: overlay
                    anchors.fill: parent
                }

                // drag to move the video, scroll to zoom, click to play / pause
                MouseArea {
                    id: dragArea
                    anchors.fill: parent
                    enabled: !!Store.mediaUrl
                    cursorShape: pressed && moved ? Qt.ClosedHandCursor : phone.portrait ? Qt.PointingHandCursor : Qt.OpenHandCursor
                    property real startX: 0
                    property real startY: 0
                    property real x0: 0
                    property real y0: 0
                    property var g0: null
                    property bool moved: false

                    onPressed: (mouse) => {
                        Store.releaseFocus()
                        startX = mouse.x; startY = mouse.y
                        const p = Store.framePos()      // the position active at the playhead: a switch, else the clip's own
                        x0 = p.x; y0 = p.y
                        g0 = phone.g                    // geometry at that position (phone.g follows Store.posX / posY)
                        moved = false
                    }
                    onPositionChanged: (mouse) => {
                        const dx = mouse.x - startX, dy = mouse.y - startY
                        if (!moved && Math.abs(dx) + Math.abs(dy) < 4) return
                        moved = true
                        if (phone.portrait || !g0) return
                        const W = phone.width, H = phone.height
                        let x = x0, y = y0
                        if (g0.mode === "fit") {
                            if (Math.abs(W - g0.w) > 1) x = x0 + dx / (W - g0.w)
                            if (Math.abs(H - g0.h) > 1) y = y0 + dy / (H - g0.h)
                        } else {
                            if (phone.vw - g0.cw > 1) x = x0 - dx * (g0.cw / W) / (phone.vw - g0.cw)
                            if (phone.vh - g0.ch > 1) y = y0 - dy * (g0.ch / H) / (phone.vh - g0.ch)
                        }
                        Store.setFramePos(x, y)         // edits the active switch, or cropX / frameY
                    }
                    onReleased: if (!moved) stage.togglePlay()
                    onWheel: (wheel) => Store.setFrameZoom(Store.frameZoom * Math.exp(Store.clamp(wheel.angleDelta.y, -360, 360) * 0.00125))
                }

                // HUD
                Rectangle {
                    id: hudTimeBox
                    x: 10; y: 10
                    radius: 6
                    color: Qt.rgba(0, 0, 0, 0.55)
                    implicitWidth: hudTime.implicitWidth + 14
                    implicitHeight: 20
                    visible: !!Store.mediaUrl
                    Text { id: hudTime; anchors.centerIn: parent; text: `T+ ${Store.fmt(Store.playhead)}`; color: Theme.cyan; font.family: Theme.mono; font.pixelSize: 10 }
                }
                Rectangle {
                    anchors.right: parent.right
                    anchors.rightMargin: 10
                    y: phone.width < hudTimeBox.width + width + 26 ? 34 : 10   // a small phone: under the time, not over it
                    radius: 6
                    color: Qt.rgba(0, 0, 0, 0.55)
                    implicitWidth: hudMode.implicitWidth + 14
                    implicitHeight: 20
                    visible: !!Store.mediaUrl
                    Text {
                        id: hudMode
                        anchors.centerIn: parent
                        text: `${Store.layout === "fit" ? "FIT" : "CROP"} · ${Math.round(Store.frameZoom * 100)}%`
                        color: Theme.muted
                        font.family: Theme.mono
                        font.pixelSize: 10
                    }
                }
                Text {
                    anchors.centerIn: parent
                    visible: !!Store.videoKey && !Store.mediaUrl
                    text: Store.prep.state === "working" ? `PREPARING PREVIEW${Store.prep.progress ? ` · ${Store.prep.progress}%` : ""}`
                        : Store.prep.state === "error" ? "PREVIEW UNAVAILABLE" : "NO SIGNAL"
                    color: Qt.rgba(123 / 255, 138 / 255, 169 / 255, 0.7)
                    font.family: Theme.display
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    font.letterSpacing: 2
                }
            }

            // frame + soft glow around the phone
            Rectangle {
                anchors.fill: phone
                anchors.margins: -1
                color: "transparent"
                radius: 3
                border.color: Qt.rgba(0, 229 / 255, 1, 0.35)
            }
        }

        // transport. A panel narrower than the whole row (windows under ~1650 px) gets tighter chips, then loses the
        // total time, so the row – and the strip and overview, which take its width – always fit (web: it squeezes)
        RowLayout {
            id: transport
            Layout.fillWidth: true
            // in whole pixels: the layout rounds each item's width up (fractional at 125 % / 150 % display scaling)
            readonly property real fixed: Math.ceil(backBtn.implicitWidth) + 42 + Math.ceil(fwdBtn.implicitWidth)
                                          + Math.ceil(loopChip.wideWidth) + Math.ceil(safeChip.wideWidth)
            readonly property real timeWidth: Math.ceil(fullTime.advanceWidth) + 1
            readonly property bool narrow: stage.width - 28 < fixed + 6 + timeWidth + 5 * 8
            readonly property bool timeOnly: stage.width - 28 < fixed - 2 * 12 + timeWidth + 5 * 6
            spacing: narrow ? 6 : 8
            IconButton { id: backBtn; glyph: Theme.icBack; ToolTip.text: "Back 5 s (J)"; onClicked: stage.seek(Store.playhead - 5) }
            Rectangle {
                id: playBtn
                Layout.preferredWidth: 42
                Layout.preferredHeight: 42
                radius: 21
                color: playArea.pressed ? Theme.cyan2 : Theme.cyan
                layer.enabled: true
                layer.effect: MultiEffect {
                    shadowEnabled: true; shadowColor: Theme.cyan; shadowBlur: 0.8
                    shadowOpacity: playArea.containsMouse ? 0.85 : 0.5
                    shadowHorizontalOffset: 0; shadowVerticalOffset: 0
                }
                Text {
                    anchors.centerIn: parent
                    anchors.horizontalCenterOffset: Store.playing ? 0 : 1
                    text: Store.playing ? Theme.icPause : Theme.icPlay
                    font.family: Theme.icons
                    font.pixelSize: 16
                    color: "#00141a"
                }
                MouseArea { id: playArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: stage.togglePlay() }
            }
            IconButton { id: fwdBtn; glyph: Theme.icForward; ToolTip.text: "Forward 5 s (L)"; onClicked: stage.seek(Store.playhead + 5) }
            Text {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.leftMargin: transport.narrow ? 0 : 6
                elide: Text.ElideRight
                textFormat: Text.StyledText
                text: transport.timeOnly ? Store.fmt(Store.playhead)
                    : `${Store.fmt(Store.playhead)}<font color="${Theme.dim}"> / ${Store.fmt(Store.duration)}</font>`
                color: Theme.text
                font.family: Theme.mono
                font.pixelSize: 12
                TextMetrics { id: fullTime; font.family: Theme.mono; font.pixelSize: 12; text: `${Store.fmt(Store.duration)} / ${Store.fmt(Store.duration)}` }
            }
            Chip { id: loopChip; text: "Loop"; compact: transport.narrow; on: Store.loop; onToggled: Store.loop = !Store.loop }
            Chip { id: safeChip; text: "Safe zones"; compact: transport.narrow; on: Store.safe; onToggled: Store.safe = !Store.safe }
        }

        RazorBar {
            id: razor
            Layout.fillWidth: true
            Layout.preferredHeight: 26
            hint: strip.hint
            onToClips: {
                const plan = Store.splitPlan()
                if (plan.error) { Store.toast(plan.error, "info"); return }
                splitAsk.plan = plan
                splitAsk.open()
            }
        }
        Strip {
            id: strip
            Layout.fillWidth: true
            // a short window keeps room for the phone: the razor row took some of it
            Layout.preferredHeight: stage.height < 560 ? 62 : 78
            onSeek: (t) => stage.seek(t)
        }
        Overview {
            Layout.fillWidth: true
            Layout.preferredHeight: 16
            view: strip.view
            onSeek: (t) => stage.seek(t)
        }
    }

    // "To clips": say what will happen before the queue changes
    Popup {
        id: splitAsk
        property var plan: ({ names: [], short: 0, teaser: -1 })   // Store.splitPlan()
        readonly property var names: plan.names
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 420
        modal: true
        focus: true
        padding: 22
        background: Rectangle { radius: 16; color: Theme.panelSolid; border.color: Theme.line2 }
        Overlay.modal: Rectangle { color: Qt.rgba(2 / 255, 4 / 255, 8 / 255, 0.6) }
        function accept() { close(); Store.splitIntoClips() }
        contentItem: ColumnLayout {
            spacing: 12
            focus: true
            Keys.onReturnPressed: splitAsk.accept()
            Keys.onEnterPressed: splitAsk.accept()
            Text {
                text: `Split into ${splitAsk.names.length} clips?`
                color: Theme.text
                font.family: Theme.display
                font.pixelSize: 16
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: `"${Store.editing || Store.safeName(Store.clipName)}" becomes ${splitAsk.names.join(", ")} in the queue. `
                      + "Each one keeps the captions, hook and edit settings. "
                      + (splitAsk.plan.short ? "Deleted parts and parts under 0.3 s are left out." : "Deleted parts are left out.")
                      + (splitAsk.plan.teaser >= 0 ? ` The teaser goes to ${splitAsk.names[splitAsk.plan.teaser]}.` : "")
                wrapMode: Text.WordWrap
                color: Theme.muted
                font.pixelSize: 13
                lineHeight: 1.2
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 8
                spacing: 10
                Item { Layout.fillWidth: true }
                NeonButton { text: "Cancel"; onClicked: splitAsk.close() }
                NeonButton { primary: true; text: "Split"; onClicked: splitAsk.accept() }
            }
        }
    }
}
