import QtQuick
import QtMultimedia
import "."

// Pop-ups (pictures, GIFs, short videos) over the preview – the QML twin of pro.js drawPopups. Each shows for `dur`
// seconds from its moment `at`: centred, `size` x the frame wide, at the top / centre / bottom, fading in and out
// over 0.15 s – the same place and look as the overlays clipper.edit_graph burns in. It sits above the video (and
// its punch-in zoom) and under the captions. The stage calls refresh() every tick; nothing here takes the mouse.
Item {
    id: popLayer

    // t = source seconds, out = seconds on the finished clip (null outside it), ed = Store.editState()
    function refresh(t, out, ed) {
        for (let i = 0; i < rep.count; i++) {
            const d = rep.itemAt(i)
            if (d) d.sync(t, out, ed)
        }
    }

    function itemAt(i) { return rep.itemAt(i) }   // for test scripts

    Repeater {
        id: rep
        // a count, not the array: the delegates (and their video players) survive while a pop-up's length, size or
        // position changes; Store.popups[index] is read live
        model: Store.popups.length

        Item {
            id: pop
            required property int index
            readonly property var p: Store.popups[index] || null
            readonly property var media: p ? Store.popupMedia[p.path] || null : null
            readonly property string kind: media ? media.kind : ""
            readonly property string url: media && media.exists ? media.url : ""
            property real local: -1        // seconds since it appeared (kept while it is on screen)
            property bool showing: false   // inside its 0..dur window, with the playhead on the clip
            readonly property var box: p ? Store.popupBox(p, shown.item ? shown.item.mediaW : 0, shown.item ? shown.item.mediaH : 0,
                                                          popLayer.width, popLayer.height) : null

            x: box ? box.x : 0
            y: box ? box.y : 0
            width: box ? box.w : 1
            height: box && box.h > 0 ? box.h : 1
            z: index                       // later pop-ups on top, like the render's overlay order
            visible: showing && !!shown.item && shown.item.ready && !shown.item.ended
            opacity: p ? Store.popupAlpha(p, local) : 0

            // the file for one kind of media: while another clip's pop-up of another kind takes this slot, the
            // component being replaced is never handed that file (an AnimatedImage can't read a video)
            function fileFor(k) { return media && media.exists && media.kind === k ? media.url : "" }

            function sync(t, out, ed) {
                const l = p && out !== null ? Store.popupLocal(p, t, ed, out) : -1
                const show = !!p && l >= 0 && l <= p.dur
                if (show) local = l
                if (show !== showing) showing = show
                if (shown.item) shown.item.sync(l, show, Store.playing)
            }

            Loader {
                id: shown
                anchors.fill: parent
                active: pop.url !== ""     // a missing file shows nothing (the web preview draws nothing either)
                sourceComponent: pop.kind === "video" ? videoMedia : pop.kind === "gif" ? gifMedia : pictureMedia
            }

            Component {
                id: pictureMedia
                Item {
                    // ffmpeg turns a picture upright by its EXIF orientation (a phone photo): Qt does that for a JPEG
                    // (autoTransform), a PNG / WebP is turned here (backend.popupInfo orient: 2-8 = mirrored / turned)
                    readonly property int orient: pop.media && pop.media.orient > 1 ? pop.media.orient : 1
                    readonly property bool quarter: orient >= 5
                    readonly property real mediaW: quarter ? img.implicitHeight : img.implicitWidth
                    readonly property real mediaH: quarter ? img.implicitWidth : img.implicitHeight
                    readonly property bool ready: img.status === Image.Ready && img.implicitWidth > 0
                    readonly property bool ended: false
                    function sync(local, showing, playing) {}
                    Image {
                        id: img
                        anchors.centerIn: parent
                        width: parent.quarter ? parent.height : parent.width
                        height: parent.quarter ? parent.width : parent.height
                        rotation: [0, 0, 0, 180, 180, 270, 90, 90, 270][parent.orient]
                        mirror: [false, false, true, false, true, true, false, true, false][parent.orient]
                        source: pop.fileFor("picture")
                        asynchronous: true
                        autoTransform: true
                        sourceSize.width: 1080     // never decoded wider than the output (big photos stay light)
                        fillMode: Image.Stretch
                        smooth: true
                        mipmap: true
                    }
                }
            }

            Component {
                id: gifMedia
                AnimatedImage {
                    readonly property real mediaW: implicitWidth
                    readonly property real mediaH: implicitHeight
                    readonly property bool ready: status === Image.Ready && implicitWidth > 0
                    // the render's clock for it (clipper.gif_timing: ffmpeg's frame times and loop count), in 1/100 s
                    readonly property var cs: pop.media && pop.media.gif ? pop.media.gif.delays.map(d => Math.round(d * 100)) : []
                    readonly property int passCs: cs.reduce((a, b) => a + b, 0)
                    // its passes are over: the render (overlay eof_action=pass) shows nothing from then on. A one-frame
                    // GIF is held like a picture; a GIF its Seconds cut shows its frame until the end (edit_graph fps=100)
                    readonly property int endCs: passCs > 0 && cs.length > 1 && pop.media.gif.plays > 0 ? passCs * pop.media.gif.plays : -1
                    property bool ended: false
                    property bool wasShowing: false
                    // the frame the render shows `local` s after the pop-up appeared (-ignore_loop 0 from its first frame),
                    // so it restarts with every appearance, stays put while paused and follows seeks; QMovie never runs
                    // on its own (a finished one would stop for good). Without frame times: restart it on appearing and
                    // run it while the clip plays.
                    function sync(local, showing, clipPlaying) {
                        if (passCs <= 0) {
                            if (showing && !wasShowing) {
                                ended = false
                                if (!playing) playing = true
                                if (frameCount > 1) currentFrame = 0
                            }
                            wasShowing = showing
                            const run = showing && clipPlaying
                            if (paused === run) paused = !run
                            return
                        }
                        wasShowing = showing
                        const t = local * 100 + 0.0001
                        const over = showing && endCs >= 0 && t >= endCs
                        if (over !== ended) ended = over
                        if (!showing || over || frameCount < 1) return
                        if (!playing) playing = true
                        if (!paused) paused = true
                        let f = 0, rest = t % passCs
                        while (f < cs.length - 1 && rest >= cs[f]) rest -= cs[f++]
                        f = Math.min(f, frameCount - 1)
                        if (currentFrame !== f) currentFrame = f
                    }
                    onSourceChanged: ended = false
                    onPlayingChanged: if (!playing && passCs <= 0 && wasShowing) ended = true   // QMovie ran out of loops
                    source: pop.fileFor("gif")
                    playing: true
                    paused: true
                    fillMode: Image.Stretch
                    smooth: true
                    mipmap: true
                }
            }

            Component {
                id: videoMedia
                Item {
                    // the size the render scales: ffmpeg turns a phone video upright by its rotation first (the engine's
                    // probe, backend.popupInfo); until that is known, Qt's decoded size turned by its orientation.
                    // VideoOutput draws the frame turned already, so it fills the upright box
                    readonly property bool sideways: (Number(player.metaData.value(MediaMetaData.Orientation)) || 0) % 180 !== 0
                    readonly property real mediaW: pop.media && pop.media.w > 0 ? pop.media.w
                                                   : sideways ? vout.sourceRect.height : vout.sourceRect.width
                    readonly property real mediaH: pop.media && pop.media.h > 0 ? pop.media.h
                                                   : sideways ? vout.sourceRect.width : vout.sourceRect.height
                    readonly property bool ready: vout.sourceRect.width > 0
                        && [MediaPlayer.LoadedMedia, MediaPlayer.BufferingMedia, MediaPlayer.BufferedMedia,
                            MediaPlayer.EndOfMedia].indexOf(player.mediaStatus) >= 0
                    readonly property real fileLength: player.duration > 0 ? player.duration / 1000 : 0
                    property bool ended: false      // past the end of its file: the render shows nothing there
                    property real seekTarget: -1    // where the player was last asked to go ...
                    property real seekUntil: 0      // ... and until when its reported position may still be the old one

                    // web drawPopups: the pop-up keeps its own clock (put back when it is off by more than 0.3 s, a
                    // frame while paused) and plays / pauses with the clip; off screen it is paused
                    function sync(local, showing, playing) {
                        const over = showing && fileLength > 0 && local >= fileLength - 0.02
                        if (over !== ended) ended = over
                        const isPlaying = player.playbackState === MediaPlayer.PlayingState
                        if (!showing || ended) {
                            if (isPlaying) player.pause()
                            return
                        }
                        const pos = Date.now() < seekUntil ? seekTarget : player.position / 1000
                        if (Math.abs(pos - local) > (playing ? 0.3 : 0.04)) {
                            seekTarget = local
                            seekUntil = Date.now() + 400
                            player.setPosition(Math.round(local * 1000))
                        }
                        if (playing && !isPlaying) player.play()
                        else if (!playing && isPlaying) player.pause()
                    }

                    MediaPlayer {
                        id: player
                        source: pop.fileFor("video")
                        videoOutput: vout
                        // no audio output: pop-ups are silent (web: a muted <video>; the render uses only [n:v])
                        onMediaStatusChanged: {
                            // a stopped player shows nothing: pausing it puts the frame on screen
                            if (mediaStatus === MediaPlayer.LoadedMedia && playbackState === MediaPlayer.StoppedState) pause()
                        }
                        onErrorOccurred: (error, errorString) => Store.toast(`Pop-up: ${errorString}`, "error")
                    }
                    VideoOutput {
                        id: vout
                        anchors.fill: parent
                        fillMode: VideoOutput.Stretch
                    }
                }
            }
        }
    }
}
