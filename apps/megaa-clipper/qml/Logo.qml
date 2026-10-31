import QtQuick
import QtQuick.Shapes
import "."

// The two offset play triangles (magenta behind cyan), drawn at 40×40 and scaled to fit.
Item {
    id: logo
    implicitWidth: 40
    implicitHeight: 40

    Shape {
        width: 40
        height: 40
        scale: Math.min(logo.width, logo.height) / 40
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeWidth: -1
            fillColor: Theme.magenta
            startX: 12; startY: 7
            PathLine { x: 35; y: 20 }
            PathLine { x: 12; y: 33 }
            PathLine { x: 12; y: 7 }
        }
        ShapePath {
            strokeWidth: -1
            fillColor: Theme.cyan
            startX: 8; startY: 7
            PathLine { x: 31; y: 20 }
            PathLine { x: 8; y: 33 }
            PathLine { x: 8; y: 7 }
        }
    }
}
