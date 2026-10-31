import QtQuick
import QtQuick.Shapes

// Primary button with the signature clipped bottom-right corner + neon glow.
// Filled buttons carry a soft accent halo (brighter on hover); outline buttons
// get a glowing accent border on hover. Glow is built from layered translucent
// clipped Shapes so it survives the offscreen software render; a MultiEffect
// bloom is layered on top for extra GPU sparkle (purely additive).
Item {
    id: root
    property string text: ""
    property color accent: Theme.cyan
    property bool filled: true
    property real hpad: 22   // `enabled` is the built-in Item property
    signal clicked()

    implicitHeight: 44
    implicitWidth: label.implicitWidth + hpad * 2
    opacity: enabled ? 1 : 0.45

    // Glow intensity: filled rests lit, both brighten on hover, dark when disabled.
    property real glowAmt: (enabled ? 1 : 0) * ((filled ? 0.22 : 0.0) + (ma.containsMouse ? 0.36 : 0.0))
    Behavior on glowAmt { NumberAnimation { duration: 150; easing.type: Easing.OutQuad } }

    // Reusable clipped silhouette — same polygon as the face:
    //   0,0  W,0  W,0.70H  0.90W,H  0,H
    component Silhouette: Shape {
        id: sil
        property color fill: "transparent"
        property color stroke: "transparent"
        property real sw: 0
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: sil.fill
            strokeColor: sil.stroke
            strokeWidth: sil.sw
            joinStyle: ShapePath.MiterJoin
            startX: 0
            startY: 0
            PathLine { x: sil.width;        y: 0 }
            PathLine { x: sil.width;        y: sil.height * 0.70 }
            PathLine { x: sil.width * 0.90; y: sil.height }
            PathLine { x: 0;                y: sil.height }
            PathLine { x: 0;                y: 0 }
        }
    }

    // ---- Layered neon glow (offscreen-safe: stacked translucent silhouettes) ----
    Item {
        id: glowStack
        z: -1
        anchors.centerIn: parent
        width: parent.width + 40
        height: parent.height + 40
        opacity: root.glowAmt
        visible: root.glowAmt > 0.001

        Silhouette {
            anchors.centerIn: parent
            width: root.width + 38
            height: root.height + 38
            fill: root.filled ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.05) : "transparent"
            stroke: root.filled ? "transparent" : Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.06)
            sw: root.filled ? 0 : 3
        }
        Silhouette {
            anchors.centerIn: parent
            width: root.width + 24
            height: root.height + 24
            fill: root.filled ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.09) : "transparent"
            stroke: root.filled ? "transparent" : Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.11)
            sw: root.filled ? 0 : 3
        }
        Silhouette {
            anchors.centerIn: parent
            width: root.width + 13
            height: root.height + 13
            fill: root.filled ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.14) : "transparent"
            stroke: root.filled ? "transparent" : Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.22)
            sw: root.filled ? 0 : 2
        }
        Silhouette {
            anchors.centerIn: parent
            width: root.width + 5
            height: root.height + 5
            fill: root.filled ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.20) : "transparent"
            stroke: root.filled ? "transparent" : Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.45)
            sw: root.filled ? 0 : 1.5
        }
    }


    // ---- The button face (signature clipped bottom-right corner) ----
    Shape {
        id: face
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        // Vertical neon sheen for depth; only used when filled.
        LinearGradient {
            id: faceGrad
            x1: 0
            y1: 0
            x2: 0
            y2: face.height
            GradientStop { position: 0.0
                color: ma.containsMouse ? Qt.lighter(root.accent, 1.10) : Qt.lighter(root.accent, 1.03) }
            GradientStop { position: 0.55
                color: root.accent }
            GradientStop { position: 1.0
                color: ma.containsMouse ? Qt.darker(root.accent, 1.06) : Qt.darker(root.accent, 1.22) }
        }

        ShapePath {
            fillColor: "transparent"
            fillGradient: root.filled ? faceGrad : null
            strokeColor: root.filled ? "transparent"
                                     : (ma.containsMouse && root.enabled ? root.accent : Theme.border)
            strokeWidth: root.filled ? 0 : (ma.containsMouse && root.enabled ? 1.6 : 1)
            joinStyle: ShapePath.MiterJoin
            startX: 0
            startY: 0
            PathLine { x: root.width;        y: 0 }
            PathLine { x: root.width;        y: root.height * 0.70 }
            PathLine { x: root.width * 0.90; y: root.height }
            PathLine { x: 0;                 y: root.height }
            PathLine { x: 0;                 y: 0 }
        }
    }

    // Thin inner top highlight adds a glassy edge on filled buttons.
    Rectangle {
        visible: root.filled
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 2
        height: 1
        color: Qt.rgba(1, 1, 1, ma.containsMouse ? 0.26 : 0.14)
    }

    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        color: root.filled ? Theme.bg : (ma.containsMouse ? root.accent : Theme.textPrimary)
        font.family: Theme.fontDisplay
        font.weight: Font.Bold
        font.pixelSize: 14
        font.letterSpacing: 2.5
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: if (root.enabled) root.clicked()
    }
    scale: ma.pressed && enabled ? 0.97 : 1.0
    Behavior on scale { NumberAnimation { duration: 90 } }
}
