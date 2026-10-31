import QtQuick
import QtQuick.Shapes

// A beautiful game/app cover tile: rich per-game gradient cover, a large stylized
// initial-letter watermark, a dark bottom scrim for legibility, the signature
// clipped bottom-right corner, and a layered neon glow on hover (all offscreen-renderable).
Item {
    id: root

    property string name: ""
    property string subtitle: ""
    property color accent: Theme.cyan
    signal activated()

    readonly property string iconSource: (typeof Theme.iconFor === "function") ? Theme.iconFor(name) : ""

    implicitWidth: 150
    implicitHeight: 150

    readonly property bool hovered: ma.containsMouse
    readonly property real cut: 22

    // --- Cover gradient colours ---------------------------------------------
    // Honour the design contract (Theme.coverA/coverB) when present; otherwise
    // derive a rich, deterministic dark gradient from the name so the tile is
    // never flat. Reads root.name so bindings refresh if the name changes.
    function _hash(s) {
        var h = 0
        s = s || ""
        for (var i = 0; i < s.length; i++)
            h = ((h * 31) + s.charCodeAt(i)) >>> 0
        return h
    }
    readonly property color coverA: (typeof Theme.coverA === "function")
        ? Theme.coverA(root.name)
        : Qt.hsla(((_hash(root.name) % 360) / 360), 0.62, 0.17, 1.0)
    readonly property color coverB: (typeof Theme.coverB === "function")
        ? Theme.coverB(root.name)
        : Qt.hsla((((_hash(root.name) + 140) % 360) / 360), 0.55, 0.07, 1.0)

    // --- Interaction: subtle hover lift + press --------------------------------
    Item {
        id: body
        anchors.fill: parent
        transformOrigin: Item.Center
        scale: ma.pressed ? 0.97 : (root.hovered ? 1.03 : 1.0)
        Behavior on scale { NumberAnimation { duration: 110; easing.type: Easing.OutCubic } }

        // ===== NEON GLOW (behind the card) =====================================
        // Layered translucent accent halos — soft neon bloom that renders in an
        // offscreen software grab (no GPU blur required).
        Item {
            id: glow
            anchors.fill: card
            z: 0
            opacity: root.hovered ? 1.0 : 0.0
            Behavior on opacity { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }

            Rectangle {
                anchors.fill: parent
                anchors.margins: -15
                radius: 17
                color: root.accent
                opacity: 0.05
            }
            Rectangle {
                anchors.fill: parent
                anchors.margins: -10
                radius: 13
                color: root.accent
                opacity: 0.08
            }
            Rectangle {
                anchors.fill: parent
                anchors.margins: -6
                radius: 10
                color: root.accent
                opacity: 0.12
            }
            Rectangle {
                anchors.fill: parent
                anchors.margins: -2
                radius: 8
                color: root.accent
                opacity: 0.17
            }
        }

        // ===== CARD ============================================================
        Item {
            id: card
            anchors.fill: parent
            z: 1
            clip: true

            // -- Full-bleed brand cover: the icon IS the whole tile -------------
            Image {
                id: coverImg
                anchors.fill: parent
                source: root.iconSource
                visible: root.iconSource.length > 0 && status === Image.Ready
                fillMode: Image.PreserveAspectCrop
                sourceSize.width: 320
                sourceSize.height: 320
                smooth: true
                cache: true
                opacity: root.hovered ? 1.0 : 0.97
                Behavior on opacity { NumberAnimation { duration: 180 } }
            }

            // -- Fallback cover (no supplied icon): gradient + big initial ------
            Shape {
                id: sh
                anchors.fill: parent
                visible: !coverImg.visible
                antialiasing: true
                ShapePath {
                    strokeWidth: 0
                    strokeColor: "transparent"
                    fillGradient: LinearGradient {
                        x1: 0
                        y1: 0
                        x2: root.width
                        y2: root.height
                        GradientStop { position: 0.0; color: root.coverA }
                        GradientStop { position: 1.0; color: root.coverB }
                    }
                    startX: 0
                    startY: 0
                    PathLine { x: root.width; y: 0 }
                    PathLine { x: root.width; y: root.height - root.cut }
                    PathLine { x: root.width - root.cut; y: root.height }
                    PathLine { x: 0; y: root.height }
                    PathLine { x: 0; y: 0 }
                }
            }
            Rectangle {
                visible: !coverImg.visible
                anchors.centerIn: parent
                anchors.verticalCenterOffset: -14
                width: root.width * 0.74
                height: width
                radius: width / 2
                color: root.accent
                opacity: root.hovered ? 0.11 : 0.0
                Behavior on opacity { NumberAnimation { duration: 220 } }
            }
            Rectangle {
                visible: !coverImg.visible
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: parent.height * 0.5
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.10) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
            Text {
                visible: !coverImg.visible
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: -14
                text: root.name.length ? root.name.charAt(0).toUpperCase() : "?"
                color: "#ffffff"
                opacity: root.hovered ? 0.22 : 0.15
                font.family: Theme.fontDisplay
                font.weight: Font.Bold
                font.pixelSize: Math.round(root.height * 0.62)
                Behavior on opacity { NumberAnimation { duration: 180 } }
            }

            // -- Re-cut the bottom-right chamfer over the full-bleed image ------
            Shape {
                anchors.fill: parent
                visible: coverImg.visible
                antialiasing: true
                ShapePath {
                    strokeWidth: 0
                    strokeColor: "transparent"
                    fillColor: Theme.bg
                    startX: root.width + 1
                    startY: root.height - root.cut
                    PathLine { x: root.width + 1; y: root.height + 1 }
                    PathLine { x: root.width - root.cut; y: root.height + 1 }
                    PathLine { x: root.width + 1; y: root.height - root.cut }
                }
            }

            // -- Bottom scrim for name legibility (chamfered) -------------------
            Shape {
                anchors.fill: parent
                antialiasing: true
                ShapePath {
                    strokeWidth: 0
                    strokeColor: "transparent"
                    fillGradient: LinearGradient {
                        x1: 0
                        y1: root.height * 0.42
                        x2: 0
                        y2: root.height
                        GradientStop { position: 0.0; color: "transparent" }
                        GradientStop { position: 0.55; color: Qt.rgba(0.02, 0.02, 0.05, 0.62) }
                        GradientStop { position: 1.0; color: Qt.rgba(0.01, 0.01, 0.03, 0.94) }
                    }
                    startX: 0
                    startY: root.height * 0.42
                    PathLine { x: root.width; y: root.height * 0.42 }
                    PathLine { x: root.width; y: root.height - root.cut }
                    PathLine { x: root.width - root.cut; y: root.height }
                    PathLine { x: 0; y: root.height }
                    PathLine { x: 0; y: root.height * 0.42 }
                }
            }

            // -- Mono comment-style signature label -----------------------------
            Text {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.leftMargin: 12
                anchors.topMargin: 10
                text: "//"
                color: root.accent
                opacity: root.hovered ? 0.9 : 0.45
                font.family: Theme.fontMono
                font.weight: Font.Medium
                font.pixelSize: 12
                Behavior on opacity { NumberAnimation { duration: 150 } }
            }

            // -- Name block -----------------------------------------------------
            Column {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.leftMargin: 12
                anchors.rightMargin: 14
                anchors.bottomMargin: 11
                spacing: 5

                Rectangle {
                    width: 14
                    height: 2
                    color: root.accent
                    opacity: root.hovered ? 1.0 : 0.8
                    Behavior on opacity { NumberAnimation { duration: 150 } }
                }
                Text {
                    width: parent.width
                    text: root.name
                    color: Theme.textPrimary
                    elide: Text.ElideRight
                    maximumLineCount: 1
                    font.family: Theme.fontDisplay
                    font.weight: Font.DemiBold
                    font.pixelSize: 15
                    font.letterSpacing: 1
                }
                Text {
                    visible: root.subtitle.length > 0
                    width: parent.width
                    text: root.subtitle
                    color: Theme.textMuted
                    elide: Text.ElideRight
                    maximumLineCount: 1
                    font.family: Theme.fontMono
                    font.pixelSize: 9
                    font.letterSpacing: 0.5
                }
            }

            // -- Crisp 1px outline (accent on hover), chamfered -----------------
            Shape {
                anchors.fill: parent
                antialiasing: true
                ShapePath {
                    fillColor: "transparent"
                    strokeColor: root.hovered ? root.accent : Theme.border
                    strokeWidth: 1
                    Behavior on strokeColor { ColorAnimation { duration: 150 } }
                    startX: 0.5
                    startY: 0.5
                    PathLine { x: root.width - 0.5; y: 0.5 }
                    PathLine { x: root.width - 0.5; y: root.height - root.cut }
                    PathLine { x: root.width - root.cut; y: root.height - 0.5 }
                    PathLine { x: 0.5; y: root.height - 0.5 }
                    PathLine { x: 0.5; y: 0.5 }
                }
            }

            // -- Signature accent cut line along the chamfer --------------------
            Shape {
                anchors.fill: parent
                antialiasing: true
                opacity: root.hovered ? 1.0 : 0.7
                Behavior on opacity { NumberAnimation { duration: 150 } }
                ShapePath {
                    fillColor: "transparent"
                    strokeColor: root.accent
                    strokeWidth: 2
                    startX: root.width - 0.5
                    startY: root.height - root.cut
                    PathLine { x: root.width - root.cut; y: root.height - 0.5 }
                }
            }
        }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.activated()
    }
}
