import QtQuick
import QtQuick.Particles
import QtQuick.Shapes

// The animated background behind the grid: the classic edition's six effects (app/effects.py)
// rebuilt on the GPU scene graph. Nothing here runs per frame in JS or Python:
//   Starfield, Aurora   items moved by declarative NumberAnimations (C++ animation jobs)
//   Snow, Rain, Embers  C++ particle systems (ImageParticle sprites from Qt's built-in images)
//   Fireflies           particle system + Wander (the classic random walk), pulsing ItemParticle glows
// Deliberately no Animators (XAnimator, OpacityAnimator, ...): while any render-thread Animator
// runs, Qt's threaded render loop alternates animator-only frames with GUI sync frames, so every
// GUI-thread animation in the window (the grid's eased scrolling, dialog fades, the particle
// systems) would advance only every other vsync. Measured: 495 -> 242 GUI ticks in 3 s at 165 Hz.
// Only the active effect exists (one Loader; "None" or an unknown name creates nothing) and all
// motion pauses while the window is minimized or hidden. Counts are the classic ones at ~1280x700
// and scale with the area. Colours follow the theme live.
Rectangle {
    id: root

    property string effect: "None"

    color: Theme.c.BG
    clip: true      // particles, wrapped stars and aurora clouds must not paint over the bars

    // False while the window is minimized/hidden: every animation and particle system pauses.
    readonly property bool live: visible && Window.visibility !== Window.Minimized
                                 && Window.visibility !== Window.Hidden

    // The size effects are laid out for: follows the item, but settles ~1/4 s after a resize
    // drag. When it settles the active effect is rebuilt for the new size (as the classic
    // respawns on resize): particle effects pre-warm at the right density at once, and stars
    // and clouds get a fresh layout. During the drag the particle emitters follow live.
    property real fieldW: 0
    property real fieldH: 0
    readonly property real density: Math.max(0.15, Math.min(3.5, fieldW * fieldH / (1280 * 700)))

    function count(base) { return Math.max(1, Math.round(base * root.density)) }

    function _resized() {
        if (root.fieldW <= 0 || root.fieldH <= 0) {     // first real size: lay out at once
            root.fieldW = root.width
            root.fieldH = root.height
        } else {
            settle.restart()
        }
    }
    onWidthChanged: _resized()
    onHeightChanged: _resized()
    Component.onCompleted: _resized()

    Timer {
        id: settle
        interval: 220
        onTriggered: {
            if (root.fieldW === root.width && root.fieldH === root.height)
                return      // dragged back to the size it already has
            // Drop the old scene first: its layout bindings must not re-run for the new size
            // (the Loader clears its context, so they don't) — it is rebuilt fresh instead.
            root._reload()
            root.fieldW = root.width
            root.fieldH = root.height
        }
    }

    // ImageParticle blends premultiplied but takes `color` as given (and its `alpha` property is
    // stored inside `color`), so sprite colours are premultiplied here.
    function sprite(color, a) {
        const k = Qt.darker(color, 1.0)
        return Qt.rgba(k.r * a, k.g * a, k.b * a, a)
    }

    // Rebuild the active effect (unload now, load again on the next event-loop pass).
    property bool _reloading: false
    function _reload() {
        if (stage.item) {
            root._reloading = true
            Qt.callLater(root._endReload)
        }
    }
    function _endReload() { root._reloading = false }

    // Particle sprites bake their colour in at birth, so a theme change rebuilds those effects
    // (they pre-warm, so the swap is instant). Item-based effects rebind live and need nothing.
    readonly property string paletteKey: Theme.c.TEXT + Theme.c.ACCENT + Theme.c.TAG + Theme.c.RED
    onPaletteKeyChanged: if (stage.item && stage.item.bakedColours) _reload()

    // A switch, not an object lookup: names such as "toString" or "constructor" must be
    // unknown (= None) too, not Object.prototype members.
    readonly property Component _scene: {
        switch (root.effect) {
        case "Starfield": return starfield
        case "Snow": return snow
        case "Fireflies": return fireflies
        case "Rain": return rain
        case "Aurora": return aurora
        case "Embers": return embers
        default: return null
        }
    }

    Loader {
        id: stage
        anchors.fill: parent
        active: root._scene !== null && root.fieldW > 0 && root.fieldH > 0 && !root._reloading
        sourceComponent: root._scene
    }

    // Deterministic layout randomness for stars and clouds (the classic seeds its layout with 7
    // too), so a rebuild after a resize keeps the same picture, just fitted to the new size.
    function _rng(seed) {
        let a = seed >>> 0
        return function () {
            a = (a + 0x6D2B79F5) >>> 0
            let t = a
            t = Math.imul(t ^ (t >>> 15), t | 1)
            t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296
        }
    }

    function _starData(w, h) {
        const rnd = root._rng(7), n = root.count(140), out = []
        for (let i = 0; i < n; i++)
            out.push({ i: i, x: rnd() * w, y: rnd() * h, d: 0.25 + 0.75 * rnd(), p: rnd() * 2 * Math.PI })
        return out
    }

    function _cloudData(w, h) {
        const rnd = root._rng(7), out = []
        for (let i = 0; i < 3; i++)
            out.push({ cx: 0.15 + 0.7 * rnd(), cy: 0.1 + 0.5 * rnd(), p: rnd() * 2 * Math.PI, hue: i })
        return out
    }

    // -- reusable declarative animations (C++ jobs; no Animators, see the header) --------------

    // |sin| twinkle of an item's opacity between lo and hi, starting `phase` (0..pi) along the
    // hump; `rise` = ms from lo to hi. Bind the item's opacity to `start` so frame 1 matches.
    component Pulse: SequentialAnimation {
        id: pu
        required property Item item
        property real lo: 0
        property real hi: 1
        property real rise: 1000
        property real phase: 0
        readonly property real _p: ((phase % Math.PI) + Math.PI) % Math.PI
        readonly property bool _up: _p < Math.PI / 2
        readonly property real start: lo + (hi - lo) * Math.sin(_p)

        NumberAnimation {
            target: pu.item
            property: "opacity"
            from: pu.start
            to: pu._up ? pu.hi : pu.lo
            duration: Math.max(1, (pu._up ? Math.PI / 2 - pu._p : Math.PI - pu._p) / (Math.PI / 2) * pu.rise)
            easing.type: pu._up ? Easing.OutSine : Easing.InSine
        }
        SequentialAnimation {
            loops: Animation.Infinite
            NumberAnimation {
                target: pu.item
                property: "opacity"
                from: pu._up ? pu.hi : pu.lo
                to: pu._up ? pu.lo : pu.hi
                duration: pu.rise
                easing.type: pu._up ? Easing.InSine : Easing.OutSine
            }
            NumberAnimation {
                target: pu.item
                property: "opacity"
                from: pu._up ? pu.lo : pu.hi
                to: pu._up ? pu.hi : pu.lo
                duration: pu.rise
                easing.type: pu._up ? Easing.OutSine : Easing.InSine
            }
        }
    }

    // Sine drift of an item's position: x = cx + ax*sin(px + 2*pi*t/tx), same for y.
    // Bind the item's x/y to `start` so frame 1 matches.
    component Orbit: ParallelAnimation {
        id: orb
        required property Item item
        property real cx: 0
        property real cy: 0
        property real ax: 0
        property real ay: 0
        property real tx: 20000
        property real ty: 20000
        property real px: 0
        property real py: 0
        readonly property point start: Qt.point(cx + ax * Math.sin(px), cy + ay * Math.sin(py))
        readonly property bool _xUp: Math.cos(px) >= 0
        readonly property bool _yUp: Math.cos(py) >= 0
        readonly property real _xEnd: _xUp ? cx + ax : cx - ax
        readonly property real _yEnd: _yUp ? cy + ay : cy - ay

        function _lead(phase, up, period) {     // ms from `phase` to the next turning point
            const tau = 2 * Math.PI
            const left = (((up ? 0.5 : 1.5) * Math.PI - phase) % tau + tau) % tau
            return Math.max(1, left / tau * period)
        }

        SequentialAnimation {
            NumberAnimation {
                target: orb.item; property: "x"; from: orb.start.x; to: orb._xEnd
                duration: orb._lead(orb.px, orb._xUp, orb.tx); easing.type: Easing.OutSine
            }
            SequentialAnimation {
                loops: Animation.Infinite
                NumberAnimation {
                    target: orb.item; property: "x"; from: orb._xEnd; to: 2 * orb.cx - orb._xEnd
                    duration: orb.tx / 2; easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: orb.item; property: "x"; from: 2 * orb.cx - orb._xEnd; to: orb._xEnd
                    duration: orb.tx / 2; easing.type: Easing.InOutSine
                }
            }
        }
        SequentialAnimation {
            NumberAnimation {
                target: orb.item; property: "y"; from: orb.start.y; to: orb._yEnd
                duration: orb._lead(orb.py, orb._yUp, orb.ty); easing.type: Easing.OutSine
            }
            SequentialAnimation {
                loops: Animation.Infinite
                NumberAnimation {
                    target: orb.item; property: "y"; from: orb._yEnd; to: 2 * orb.cy - orb._yEnd
                    duration: orb.ty / 2; easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: orb.item; property: "y"; from: 2 * orb.cy - orb._yEnd; to: orb._yEnd
                    duration: orb.ty / 2; easing.type: Easing.InOutSine
                }
            }
        }
    }

    // -- Starfield: twinkling stars at depth, slow parallax drift, occasional shooting stars ----
    Component {
        id: starfield

        Item {
            id: sky
            readonly property real span: root.fieldW + 10      // drift wraps over this width
            property int nextStreak: 0

            function launch() {
                const streak = streaks.itemAt(sky.nextStreak)
                sky.nextStreak = (sky.nextStreak + 1) % streaks.count
                if (streak)
                    streak.fire(Math.random() * sky.width, Math.random() * sky.height * 0.5,
                                20 + 40 * Math.random())
            }

            readonly property var stars: root._starData(root.fieldW, root.fieldH)

            // Parallax drift by depth band: each band is one layer moving right (2*depth px/s,
            // as the classic, at the band's mean depth), so the scene graph moves 3 transforms
            // a frame instead of one per star. Every star has a copy one span to its left: as a
            // band's drift wraps, the copy stands exactly where the star was, so it's seamless.
            //
            // Twinkle by group: each band's stars are dealt into 8 groups scattered over the
            // window, each group pulsing at its own rate and phase. Neighbouring stars are nearly
            // always in different groups, so they still twinkle independently to the eye, at a
            // fraction of the cost of animating every star's opacity. A star's depth sits in
            // its colour's alpha, so the effective alpha is the classic (28 + 130*tw) * z / 255.
            Repeater {
                model: 3    // far, mid, near

                delegate: Item {
                    id: band
                    required property int index
                    readonly property real lo: 0.25 + 0.25 * index
                    readonly property real hi: index === 2 ? 1.01 : lo + 0.25
                    readonly property real mid: lo + 0.125
                    readonly property var members: sky.stars.filter(s => s.d >= band.lo && s.d < band.hi)

                    NumberAnimation {
                        target: band
                        property: "x"
                        from: 0
                        to: sky.span
                        duration: sky.span / (2 * band.mid) * 1000
                        loops: Animation.Infinite
                        running: true
                        paused: !root.live
                    }

                    Repeater {
                        model: 8

                        delegate: Item {
                            id: group
                            required property int index
                            readonly property var members: band.members.filter((s, k) => k % 8 === group.index)
                            readonly property real rate: 0.8 + band.mid + (group.index / 7 - 0.5) * 0.5   // rad/s

                            opacity: twinkle.start

                            Pulse {
                                id: twinkle
                                item: group
                                lo: 28 / 158
                                hi: 1
                                rise: Math.PI / 2 / group.rate * 1000
                                phase: group.members.length ? group.members[0].p : 0
                                running: true
                                paused: !root.live
                            }

                            Repeater {
                                model: group.members

                                delegate: Rectangle {
                                    id: star
                                    required property var modelData
                                    readonly property real r: 0.6 + 1.7 * modelData.d

                                    x: modelData.x - r
                                    y: modelData.y - r
                                    width: 2 * r
                                    height: 2 * r
                                    radius: r
                                    color: Theme.alpha(modelData.i % 7 === 0 ? Theme.c.ACCENT : Theme.c.TEXT,
                                                       158 / 255 * modelData.d)
                                    antialiasing: true

                                    Rectangle {
                                        x: -sky.span
                                        width: star.width
                                        height: star.height
                                        radius: star.radius
                                        color: star.color
                                        antialiasing: true
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Shooting stars: a bright head with a fading tail, down-right at 20-60 degrees.
            Repeater {
                id: streaks
                model: 2

                delegate: Item {
                    id: streak
                    property real sx: 0
                    property real sy: 0
                    property real ex: 0
                    property real ey: 0
                    opacity: 0      // zero-size item: it rotates about its origin, the head

                    function fire(x0, y0, degrees) {
                        const a = degrees * Math.PI / 180, travel = 310     // 350 px/s for ~0.9 s
                        streak.sx = x0
                        streak.sy = y0
                        streak.ex = x0 + Math.cos(a) * travel
                        streak.ey = y0 + Math.sin(a) * travel
                        streak.rotation = degrees
                        fly.restart()
                    }

                    Rectangle {     // soft wide tail
                        x: -70; y: -1.2
                        width: 70; height: 2.4; radius: 1.2
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: Theme.alpha(Theme.c.TEXT, 0) }
                            GradientStop { position: 1.0; color: Theme.alpha(Theme.c.TEXT, 0.22) }
                        }
                    }
                    Rectangle {     // bright core over the front half
                        x: -35; y: -0.6
                        width: 35; height: 1.2; radius: 0.6
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: Theme.alpha(Theme.c.TEXT, 0) }
                            GradientStop { position: 1.0; color: Theme.alpha(Theme.c.TEXT, 0.78) }
                        }
                    }
                    Rectangle {     // head
                        x: -1.4; y: -1.4
                        width: 2.8; height: 2.8; radius: 1.4
                        color: Theme.alpha(Theme.c.TEXT, 0.9)
                        antialiasing: true
                    }

                    ParallelAnimation {
                        id: fly
                        NumberAnimation { target: streak; property: "x"; from: streak.sx; to: streak.ex; duration: 890 }
                        NumberAnimation { target: streak; property: "y"; from: streak.sy; to: streak.ey; duration: 890 }
                        SequentialAnimation {
                            NumberAnimation { target: streak; property: "opacity"; from: 0; to: 1; duration: 70 }
                            NumberAnimation { target: streak; property: "opacity"; from: 1; to: 0; duration: 820 }
                        }
                    }
                }
            }

            Timer {     // the classic's 1.2% per 40 ms tick = one every ~3.3 s on average
                running: root.live
                repeat: true
                interval: 1800
                onTriggered: {
                    sky.launch()
                    interval = Math.round(Math.min(9000, Math.max(700, -Math.log(1 - Math.random()) * 3300)))
                }
            }
        }
    }

    // -- Snow: TEXT flakes at ~24% alpha, falling 12-40 px/s and swaying -----------------------
    Component {
        id: snow

        Item {
            id: field
            readonly property bool bakedColours: true
            // Emitters start once the sprite painter has drawn a frame: particles born before
            // it has picked its render path would miss their colour (and rain its stretch).
            // A disabled emitter still pre-warms (startTime) on its first enabled pass.
            property bool ready: false
            FrameAnimation {
                running: !field.ready && root.live
                onTriggered: if (currentFrame >= 2) field.ready = true
            }

            ParticleSystem {
                anchors.fill: parent
                paused: !root.live

                Emitter {
                    enabled: field.ready     // see `ready`
                    x: -20; y: -14
                    width: field.width + 40; height: 2
                    // the slowest flake must clear the window; rate = count / mean crossing time
                    lifeSpan: (field.height + 40) / 12 * 1000
                    emitRate: root.count(90) / ((field.height + 24) * Math.log(40 / 12) / 28)
                    startTime: lifeSpan
                    size: 5.6
                    sizeVariation: 2.0
                    velocity: AngleDirection { angle: 90; magnitude: 26; magnitudeVariation: 14 }
                }
                Wander {    // sideways sway: a bounded random walk of the x velocity
                    affectedParameter: Wander.Velocity
                    pace: 100
                    xVariance: 11
                    yVariance: 0
                }
                ImageParticle {
                    source: "qrc:///particleresources/fuzzydot.png"
                    color: root.sprite(Theme.c.TEXT, 0.24)
                    entryEffect: ImageParticle.None
                }
            }
        }
    }

    // -- Fireflies: TAG glows wandering at random, each pulsing -------------------------------
    Component {
        id: fireflies

        Item {
            id: field

            ParticleSystem {
                anchors.fill: parent
                paused: !root.live
                // ItemParticle asks for a new frame from every frame it paints, paused or not;
                // hiding it while not live is what really lets the window go idle.
                visible: root.live

                Emitter {
                    anchors.fill: parent
                    lifeSpan: 16000
                    lifeSpanVariation: 5000
                    emitRate: root.count(22) / 16
                    startTime: 21000
                    size: 20
                    velocity: AngleDirection { angleVariation: 180; magnitude: 9; magnitudeVariation: 9 }
                }
                Wander {    // the classic: velocity random walk, clamped to +-22 px/s
                    affectedParameter: Wander.Velocity
                    pace: 150
                    xVariance: 22
                    yVariance: 22
                }
                ItemParticle {
                    fade: true      // fades each firefly in at birth and out at death
                    delegate: Item {
                        width: 20
                        height: 20

                        Item {
                            id: glow
                            anchors.fill: parent
                            opacity: pulse.start

                            Shape {
                                anchors.fill: parent
                                ShapePath {
                                    strokeColor: "transparent"
                                    fillGradient: RadialGradient {
                                        centerX: 10; centerY: 10; centerRadius: 10
                                        focalX: 10; focalY: 10
                                        GradientStop { position: 0.0; color: Theme.alpha(Theme.c.TAG, 0.55) }
                                        GradientStop { position: 1.0; color: Theme.alpha(Theme.c.TAG, 0) }
                                    }
                                    PathAngleArc {
                                        centerX: 10; centerY: 10; radiusX: 10; radiusY: 10
                                        startAngle: 0; sweepAngle: 360
                                    }
                                }
                            }
                            Rectangle {
                                x: 8.4; y: 8.4
                                width: 3.2; height: 3.2; radius: 1.6
                                color: Theme.alpha(Theme.c.TAG, 0.86)
                                antialiasing: true
                            }

                            Pulse {
                                id: pulse
                                item: glow
                                lo: 0.3
                                rise: Math.PI / 2 / 1.4 * 1000
                                phase: Math.random() * Math.PI
                                running: true
                                paused: !root.live
                            }
                        }
                    }
                }
            }
        }
    }

    // -- Rain: thin ACCENT streaks at ~20% alpha, slanting slightly right ---------------------
    Component {
        id: rain

        Item {
            id: field
            readonly property bool bakedColours: true
            // Emitters start once the sprite painter has drawn a frame: particles born before
            // it has picked its render path would miss their colour (and rain its stretch).
            // A disabled emitter still pre-warms (startTime) on its first enabled pass.
            property bool ready: false
            FrameAnimation {
                running: !field.ready && root.live
                onTriggered: if (currentFrame >= 2) field.ready = true
            }
            readonly property real lead: field.height * 0.15 + 10     // slant reaches in from the left

            ParticleSystem {
                anchors.fill: parent
                paused: !root.live

                Emitter {
                    enabled: field.ready     // see `ready`
                    x: -field.lead; y: -30
                    width: field.width + field.lead; height: 2
                    lifeSpan: (field.height + 70) / 150 * 1000
                    emitRate: root.count(110) * (width / Math.max(1, field.width))
                              / ((field.height + 50) * Math.log(275 / 150) / 125)
                    startTime: lifeSpan
                    size: 23         // streak length (the sprite is stretched along yVector)
                    sizeVariation: 7
                    velocity: AngleDirection { angle: 82; magnitude: 212; magnitudeVariation: 62 }
                }
                ImageParticle {     // a dot stretched into a streak along the fall direction
                    source: "qrc:///particleresources/fuzzydot.png"
                    color: root.sprite(Theme.c.ACCENT, 0.2)
                    xVector: PointDirection { x: 0.075 }
                    yVector: PointDirection { x: 0.14; y: 1 }
                    entryEffect: ImageParticle.None
                }
            }
        }
    }

    // -- Aurora: three huge soft colour clouds drifting slowly ---------------------------------
    Component {
        id: aurora

        Item {
            id: sky
            readonly property real radius: root.fieldW * 0.45

            Repeater {
                model: root._cloudData(root.fieldW, root.fieldH)

                delegate: Shape {
                    id: cloud
                    required property var modelData
                    readonly property color hue: modelData.hue === 0 ? Theme.c.ACCENT
                                               : modelData.hue === 1 ? Theme.c.TAG : Theme.c.RED

                    width: 2 * sky.radius
                    height: 2 * sky.radius
                    x: drift.start.x
                    y: drift.start.y

                    ShapePath {
                        strokeColor: "transparent"
                        fillGradient: RadialGradient {
                            centerX: sky.radius; centerY: sky.radius; centerRadius: sky.radius
                            focalX: sky.radius; focalY: sky.radius
                            GradientStop { position: 0.0; color: Theme.alpha(cloud.hue, 0.102) }
                            GradientStop { position: 0.35; color: Theme.alpha(cloud.hue, 0.068) }
                            GradientStop { position: 0.7; color: Theme.alpha(cloud.hue, 0.026) }
                            GradientStop { position: 1.0; color: Theme.alpha(cloud.hue, 0) }
                        }
                        PathAngleArc {
                            centerX: sky.radius; centerY: sky.radius
                            radiusX: sky.radius; radiusY: sky.radius
                            startAngle: 0; sweepAngle: 360
                        }
                    }

                    Orbit {     // the classic's sin(0.25 t) / sin(0.18 t) wander
                        id: drift
                        item: cloud
                        cx: cloud.modelData.cx * root.fieldW - sky.radius
                        cy: cloud.modelData.cy * root.fieldH - sky.radius
                        ax: 0.16 * root.fieldW
                        ay: 0.10 * root.fieldH
                        tx: 2 * Math.PI / 0.25 * 1000
                        ty: 2 * Math.PI / 0.18 * 1000
                        px: cloud.modelData.p
                        py: cloud.modelData.p * 2
                        running: true
                        paused: !root.live
                    }
                }
            }
        }
    }

    // -- Embers: sparks rising and swaying, 40% RED else ACCENT, fading as they rise ----------
    Component {
        id: embers

        Item {
            id: field
            readonly property bool bakedColours: true
            // Emitters start once the sprite painter has drawn a frame: particles born before
            // it has picked its render path would miss their colour (and rain its stretch).
            // A disabled emitter still pre-warms (startTime) on its first enabled pass.
            property bool ready: false
            FrameAnimation {
                running: !field.ready && root.live
                onTriggered: if (currentFrame >= 2) field.ready = true
            }
            readonly property real crossing: (field.height + 30) * Math.log(3) / 30     // mean, s

            ParticleSystem {
                anchors.fill: parent
                paused: !root.live

                Emitter {
                    enabled: field.ready     // see `ready`
                    group: "hot"
                    x: 0; y: field.height + 4
                    width: field.width; height: 40
                    lifeSpan: (field.height + 70) / 15 * 1000
                    emitRate: root.count(60) * 0.4 / field.crossing
                    startTime: lifeSpan
                    size: 5.8
                    sizeVariation: 1.1
                    velocity: AngleDirection { angle: 270; magnitude: 30; magnitudeVariation: 15 }
                }
                Emitter {
                    enabled: field.ready     // see `ready`
                    group: "warm"
                    x: 0; y: field.height + 4
                    width: field.width; height: 40
                    lifeSpan: (field.height + 70) / 15 * 1000
                    emitRate: root.count(60) * 0.6 / field.crossing
                    startTime: lifeSpan
                    size: 5.8
                    sizeVariation: 1.1
                    velocity: AngleDirection { angle: 270; magnitude: 30; magnitudeVariation: 15 }
                }
                Wander {
                    groups: ["hot", "warm"]
                    affectedParameter: Wander.Velocity
                    pace: 120
                    xVariance: 12
                    yVariance: 0
                }
                ImageParticle {
                    groups: ["hot"]
                    source: "qrc:///particleresources/fuzzydot.png"
                    color: root.sprite(Theme.c.RED, 0.71)
                    entryEffect: ImageParticle.None
                }
                ImageParticle {
                    groups: ["warm"]
                    source: "qrc:///particleresources/fuzzydot.png"
                    color: root.sprite(Theme.c.ACCENT, 0.71)
                    entryEffect: ImageParticle.None
                }
            }

            // The fade with height. Over the plain BG, a BG veil of alpha a(y) is exactly the
            // same as each spark's alpha shrinking by (1 - a): this takes the sparks from the
            // classic's 0.71 at the bottom to 0.12 at the top in one gradient quad.
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Theme.alpha(Theme.c.BG, 0.833) }
                    GradientStop { position: 1.0; color: Theme.alpha(Theme.c.BG, 0) }
                }
            }
        }
    }
}
