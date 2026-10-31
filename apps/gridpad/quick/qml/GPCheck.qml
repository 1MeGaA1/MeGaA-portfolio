import QtQuick
import QtQuick.Controls
import QtQuick.Shapes

// Check box with an accent fill and a drawn tick.
CheckBox {
    id: c

    hoverEnabled: true
    font.family: Theme.sans
    font.pixelSize: 13
    font.weight: Theme.wNormal

    indicator: Rectangle {
        implicitWidth: 16
        implicitHeight: 16
        x: c.leftPadding
        y: (c.height - height) / 2
        radius: 3
        color: c.checked ? Theme.c.ACCENT : "transparent"
        border.width: 1.5
        border.color: c.checked ? Theme.c.ACCENT : (c.hovered ? Theme.c.TEXT : Theme.c.MUTED)
        Behavior on color { ColorAnimation { duration: 100 } }

        Shape {
            anchors.fill: parent
            visible: c.checked
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: Theme.c.BG
                strokeWidth: 1.8
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                startX: 4; startY: 8
                PathLine { x: 7; y: 11 }
                PathLine { x: 12; y: 5 }
            }
        }
    }

    contentItem: Text {
        leftPadding: c.indicator.width + 8
        text: c.text
        font: c.font
        color: Theme.c.TEXT
        verticalAlignment: Text.AlignVCenter
    }
}
