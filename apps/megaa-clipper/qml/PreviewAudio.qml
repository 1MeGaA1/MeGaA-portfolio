import QtQuick
import QtMultimedia
import "."

// Everything audible in the preview besides the video's own sound (web: muteTick, playMuteSound and syncMusic in
// ui/app.js): silencing muted words, the bleep tone, one-shot hit sounds and the background music. The stage calls
// tick() every 30 ms, syncMusic() on play and when a seek lands while playing, pauseMusic() on pause, and mutes
// the video while silenceVideo is set.
Item {
    id: fx
    visible: false

    // how much earlier (s) than the web's rule to look for muted ranges, if a mute reached the speakers later than
    // the sound at the player's position. Measured on Windows (FFmpeg backend): it doesn't – a mute set at
    // position p silences the sound from about p on – so the web's 40 ms look-ahead is enough as it is.
    property real latency: 0

    property bool silenceVideo: false   // web: video.muted
    property string hitKey: ""          // web: S.muteHit – the `${range}|${inIntro}` already hit ("" = none)
    property bool toneHit: false        // inside a muted range with a tone chosen
    property bool toneOn: false         // the tone is sounding
    property real toneUntil: 0          // Date.now() until which a tile preview keeps the tone on
    property int nextHit: 0
    property bool musicOn: false        // the music was started for the clip (web: !music.paused)

    readonly property var chosen: Store.muteSounds[Store.edit.muteSound] || null
    readonly property real level: Store.edit.muteSfxVolume

    // the files the players need; these change only when the choice really changes, so the backend (file
    // checks, ffmpeg) is asked once per change
    readonly property string hitSpec: !chosen || chosen.kind !== "hit" ? ""
        : Store.edit.muteSound !== "custom" ? Store.edit.muteSound
        : Store.edit.muteSfx ? "custom:" + Store.edit.muteSfx : ""
    readonly property real toneFreq: chosen && chosen.kind === "tone" ? (chosen.freq || 1000) : 0
    readonly property string musicPath: Store.edit.music
    property string hitUrl: ""
    property string toneUrl: ""
    property string musicUrl: ""

    function loadHit() {
        hitUrl = !hitSpec ? "" : hitSpec.startsWith("custom:") ? backend.customSoundUrl(hitSpec.slice(7)) : backend.sfxUrl(hitSpec)
    }
    function loadTone() {
        if (toneOn) { tone.stop(); toneOn = false }
        toneUrl = toneFreq ? backend.toneUrl(toneFreq) : ""
    }
    function loadMusic() {
        pauseMusic()
        music.stop()   // web: a new or removed src stops the music; the next tick starts it again inside the clip
        musicUrl = musicPath ? backend.musicUrl(musicPath) : ""
    }
    onHitSpecChanged: loadHit()
    onToneFreqChanged: loadTone()
    onMusicPathChanged: loadMusic()
    Component.onCompleted: { loadHit(); loadTone(); loadMusic() }

    // the bleep: a 1 s sine looped for as long as it should sound (web: an oscillator and a gain)
    SoundEffect {
        id: tone
        source: fx.toneUrl
        loops: SoundEffect.Infinite
        volume: Store.clamp(0.12 * fx.level, 0, 1)
    }

    // one-shot hits: a few players, so quick muted words overlap (play() on a playing effect restarts it)
    SoundEffect { id: hit0; source: fx.hitUrl }
    SoundEffect { id: hit1; source: fx.hitUrl }
    SoundEffect { id: hit2; source: fx.hitUrl }
    SoundEffect { id: hit3; source: fx.hitUrl }
    readonly property var hitPool: [hit0, hit1, hit2, hit3]

    // background music (web: <audio loop>, volume = music volume x 0.7)
    MediaPlayer {
        id: music
        source: fx.musicUrl
        loops: MediaPlayer.Infinite
        audioOutput: AudioOutput { volume: Store.clamp(Store.edit.musicVolume * 0.7, 0, 1) }
        onDurationChanged: if (fx.musicOn && duration > 0) fx.syncMusic(Store.playhead)   // started before it loaded
        onErrorOccurred: (error, errorString) => Store.toast(`Music: ${errorString}`, "error")
    }

    Connections {
        target: Store
        function onPreviewSound(toneSeconds, pulseKey) { fx.preview(toneSeconds) }
    }

    function updateTone() {
        const on = toneFreq > 0 && toneUrl !== "" && (toneHit || Date.now() < toneUntil)
        if (on === toneOn) return
        toneOn = on
        if (on) tone.play(); else tone.stop()
    }

    function playHit() {
        if (!hitUrl) return
        let player = hitPool.find(p => !p.playing)
        if (!player) player = hitPool[nextHit++ % hitPool.length]
        player.volume = Store.clamp(0.6 * level, 0, 1)
        player.play()
    }

    // web playMuteSound(toneSeconds): the chosen sound once (a tile click, a custom file just picked).
    // The tile's tone lasts the whole toneSeconds; the web's next tick cuts it after ~30 ms.
    function preview(toneSeconds) {
        if (!chosen || chosen.kind === "none") return
        if (chosen.kind === "tone") {
            toneUntil = Date.now() + toneSeconds * 1000
            updateTone()
            return
        }
        playHit()
    }

    // web muteTick(t): while playing, silence the muted words and play their sound – the tone for as long as the
    // word lasts, a one-shot effect once where each muted range starts (once more in the teaser).
    // Like the render (clipper.edit_graph), only the parts of a range kept in this pass count – the teaser, else
    // the clip's pieces: a muted word that is cut out makes no sound, and a range a cut splits gets one hit.
    // out = the clip time of t (null outside the clip), ed = Store.editState().
    function tick(t, out, ed) {
        const now = t + latency
        const look = now + 0.04   // react a moment early so the start of the word doesn't slip through
        const inClip = Store.inT !== null && (Store.inIntro || (t >= Store.inT - 0.05 && t <= Store.outT + 0.05))
        let idx = -1
        if (Store.playing && inClip) {
            const m = Store.mutes
            const pieces = Store.inIntro ? (ed.intro ? [ed.intro] : []) : (ed.segs || [])
            for (let i = 0; i < m.length && idx < 0; i++) {
                for (const p of pieces) {
                    const a = Math.max(m[i][0], p[0]), b = Math.min(m[i][1], p[1])
                    if (b > a && look >= a && now <= b) { idx = i; break }
                }
            }
        }
        const hit = idx >= 0
        if (silenceVideo !== hit) silenceVideo = hit
        toneHit = hit && chosen !== null && chosen.kind === "tone"
        updateTone()
        const key = `${idx}|${Store.inIntro}`
        if (hit && chosen !== null && chosen.kind === "hit" && hitKey !== key) playHit()
        hitKey = hit ? key : ""
        // not in the web edition: playing into the clip without a seek (Loop off) starts the music, a new file
        // starts at once, and leaving the clip stops it
        if (musicOn !== (Store.playing && out !== null && musicUrl !== "")) syncMusic(t)
    }

    // web syncMusic(): while the clip plays, the music follows the clip's own timeline (and loops)
    function syncMusic(t) {
        const out = Store.clipTime(t, Store.editState())
        if (!Store.playing || out === null || !musicUrl) { pauseMusic(); return }
        if (music.duration > 0) music.setPosition(Math.round(out * 1000) % music.duration)
        music.play()
        musicOn = true
    }

    function pauseMusic() {
        musicOn = false
        if (music.playbackState === MediaPlayer.PlayingState) music.pause()
    }
}
