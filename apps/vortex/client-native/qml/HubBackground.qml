import QtQuick
import QtQuick.Shapes

// // ------------------------------------------------------------------
// // HubBackground.qml  ::  atmospheric depth layer (sits behind content)
// // grid + drifting particles + soft off-center vortex glows
// // all layers render in an offscreen software grab (Canvas/QPainter +
// // translucent Rectangles + Gradient) — no GPU-only blur is relied upon.
// // ------------------------------------------------------------------
Item {
    id: root
    clip: true

    // // base ground : deep vertical wash for vertical depth --------------
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Vertical
            GradientStop { position: 0.0; color: Theme.bg }
            GradientStop { position: 0.55; color: "#070712" }
            GradientStop { position: 1.0; color: "#040409" }
        }
    }

    // // radial vortex glows : two big, faint, off-center blobs -----------
    Canvas {
        id: glowCanvas
        anchors.fill: parent
        renderTarget: Canvas.Image
        renderStrategy: Canvas.Immediate

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Component.onCompleted: requestPaint()

        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            var reach = Math.max(width, height)

            // cyan bloom, upper-left of center
            var cx = width * 0.20
            var cy = height * 0.26
            var gA = ctx.createRadialGradient(cx, cy, 0, cx, cy, reach * 0.60)
            gA.addColorStop(0.0, "rgba(0,229,255,0.14)")
            gA.addColorStop(0.42, "rgba(0,229,255,0.05)")
            gA.addColorStop(1.0, "rgba(0,229,255,0.0)")
            ctx.fillStyle = gA
            ctx.fillRect(0, 0, width, height)

            // magenta bloom, lower-right of center
            var mx = width * 0.84
            var my = height * 0.80
            var gB = ctx.createRadialGradient(mx, my, 0, mx, my, reach * 0.52)
            gB.addColorStop(0.0, "rgba(255,61,154,0.11)")
            gB.addColorStop(0.5, "rgba(255,61,154,0.035)")
            gB.addColorStop(1.0, "rgba(255,61,154,0.0)")
            ctx.fillStyle = gB
            ctx.fillRect(0, 0, width, height)
        }

        // slow breathing so atmosphere is alive but never distracting
        SequentialAnimation on opacity {
            loops: Animation.Infinite
            running: true
            NumberAnimation { from: 0.70; to: 1.0; duration: 6500; easing.type: Easing.InOutSine }
            NumberAnimation { from: 1.0; to: 0.70; duration: 6500; easing.type: Easing.InOutSine }
        }
    }

    // // faint tech grid : ~46px cells, near #141428, low opacity ---------
    Canvas {
        id: gridCanvas
        anchors.fill: parent
        renderTarget: Canvas.Image
        renderStrategy: Canvas.Immediate
        opacity: 0.6

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Component.onCompleted: requestPaint()

        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            var step = 46
            ctx.lineWidth = 1
            ctx.strokeStyle = "rgba(30,30,56,0.55)"
            ctx.beginPath()
            for (var gx = 0.5; gx < width; gx += step) {
                ctx.moveTo(gx, 0)
                ctx.lineTo(gx, height)
            }
            for (var gy = 0.5; gy < height; gy += step) {
                ctx.moveTo(0, gy)
                ctx.lineTo(width, gy)
            }
            ctx.stroke()

            // every 5th line a touch of cyan for a subtle blueprint feel
            ctx.strokeStyle = "rgba(0,229,255,0.035)"
            ctx.beginPath()
            for (var bx = 0.5; bx < width; bx += step * 5) {
                ctx.moveTo(bx, 0)
                ctx.lineTo(bx, height)
            }
            for (var by = 0.5; by < height; by += step * 5) {
                ctx.moveTo(0, by)
                ctx.lineTo(width, by)
            }
            ctx.stroke()
        }
    }

    // // drifting particles : capped at 8, tiny cyan/magenta motes --------
    property var particleModel: [
        { fx: 0.12, fy: 0.20, s: 4, c: Theme.cyan,    d: 5200, drift: 18 },
        { fx: 0.28, fy: 0.72, s: 3, c: Theme.magenta, d: 6400, drift: 14 },
        { fx: 0.44, fy: 0.34, s: 3, c: Theme.cyan,    d: 7100, drift: 20 },
        { fx: 0.58, fy: 0.62, s: 5, c: Theme.cyan,    d: 5800, drift: 16 },
        { fx: 0.70, fy: 0.22, s: 3, c: Theme.magenta, d: 6800, drift: 22 },
        { fx: 0.83, fy: 0.48, s: 4, c: Theme.cyan,    d: 6100, drift: 15 },
        { fx: 0.90, fy: 0.82, s: 3, c: Theme.magenta, d: 7400, drift: 18 },
        { fx: 0.36, fy: 0.90, s: 4, c: Theme.cyan,    d: 6600, drift: 17 }
    ]

    Repeater {
        model: root.particleModel
        delegate: Item {
            id: dot
            required property var modelData
            property real bx: modelData.fx * root.width
            property real by: modelData.fy * root.height

            width: 0
            height: 0
            x: bx
            y: by

            // soft outer halo (renders in software as a translucent disc)
            Rectangle {
                anchors.centerIn: parent
                width: dot.modelData.s * 6
                height: width
                radius: width / 2
                color: dot.modelData.c
                opacity: 0.09
            }
            // mid glow ring
            Rectangle {
                anchors.centerIn: parent
                width: dot.modelData.s * 3
                height: width
                radius: width / 2
                color: dot.modelData.c
                opacity: 0.26
            }
            // bright core
            Rectangle {
                anchors.centerIn: parent
                width: dot.modelData.s
                height: width
                radius: width / 2
                color: dot.modelData.c
                opacity: 0.9
            }

            // gentle vertical drift
            SequentialAnimation on y {
                loops: Animation.Infinite
                running: true
                NumberAnimation { to: dot.by - dot.modelData.drift; duration: dot.modelData.d; easing.type: Easing.InOutSine }
                NumberAnimation { to: dot.by + dot.modelData.drift; duration: dot.modelData.d; easing.type: Easing.InOutSine }
            }
            // slower, smaller lateral sway (out of phase)
            SequentialAnimation on x {
                loops: Animation.Infinite
                running: true
                NumberAnimation { to: dot.bx + dot.modelData.drift * 0.6; duration: dot.modelData.d * 1.3; easing.type: Easing.InOutSine }
                NumberAnimation { to: dot.bx - dot.modelData.drift * 0.6; duration: dot.modelData.d * 1.3; easing.type: Easing.InOutSine }
            }
            // faint twinkle
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                running: true
                NumberAnimation { to: 0.4; duration: dot.modelData.d * 0.8; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: dot.modelData.d * 0.8; easing.type: Easing.InOutSine }
            }
        }
    }
}
