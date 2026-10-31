import QtQuick

// The spinning concentric vortex rings + grid used on splash and auth screens.
Item {
    id: root
    anchors.fill: parent
    clip: true

    // faint grid
    Canvas {
        anchors.fill: parent
        opacity: 0.5
        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.strokeStyle = "#141428"
            ctx.lineWidth = 0.5
            var step = 46
            for (var x = 0; x < width; x += step) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke() }
            for (var y = 0; y < height; y += step) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke() }
        }
    }

    Item {
        anchors.centerIn: parent
        Repeater {
            model: [
                { d: 640, c: Theme.cyan,    o: 0.10, dur: 30000, rev: false },
                { d: 480, c: Theme.cyan,    o: 0.16, dur: 40000, rev: true  },
                { d: 340, c: Theme.magenta, o: 0.22, dur: 26000, rev: false },
                { d: 200, c: Theme.magenta, o: 0.30, dur: 20000, rev: true  },
                { d: 110, c: Theme.cyan,    o: 0.40, dur: 16000, rev: false }
            ]
            delegate: Rectangle {
                required property var modelData
                width: modelData.d; height: modelData.d; radius: width / 2
                x: -width / 2; y: -height / 2
                color: "transparent"
                border.color: modelData.c
                border.width: 1
                opacity: modelData.o
                RotationAnimation on rotation {
                    from: modelData.rev ? 360 : 0
                    to:   modelData.rev ? 0 : 360
                    duration: modelData.dur
                    loops: Animation.Infinite
                    running: true
                }
            }
        }
    }
}
