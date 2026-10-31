import QtQuick
import "."

// One transcript word: the web edition's span.w with its classes (ui/app.css 427-457)
//   cut    – red, 2 px line through, 65 % opacity
//   muted  – violet text, violet wavy underline
//   teaser – amber background, light amber text, 2 px amber bottom border
//   mark   – search match: magenta background, white text
//   hot    – hovered while a word tool is on: the tool's tint, white text
Rectangle {
    id: chip
    property int wi: -1
    property string text: ""
    property bool hot: false
    property color hoverTint: "transparent"
    property color base: "#b9c6de"   // the line's own text colour
    readonly property int fl: Store.wordFlags[wi] | 0
    readonly property bool cut: (fl & 17) !== 0   // cut, or in a part deleted with the razor
    readonly property bool muted: (fl & 2) !== 0
    readonly property bool teaser: (fl & 4) !== 0
    readonly property bool mark: (fl & 8) !== 0

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight + 2   // room for the teaser's bottom border
    radius: 3
    opacity: cut ? 0.65 : 1
    color: hot ? hoverTint : mark ? Qt.rgba(1, 43 / 255, 214 / 255, 0.28)
         : teaser ? Qt.rgba(1, 181 / 255, 71 / 255, 0.22) : "transparent"

    Text {
        id: label
        text: chip.text
        font.pixelSize: 14
        color: chip.hot || chip.mark ? "#ffffff" : chip.cut ? Theme.bad : chip.muted ? "#c9b8ff"
             : chip.teaser ? "#ffe2b0" : chip.base
    }

    // decorations: only marked words load them (most words have none)
    Loader {
        anchors.fill: parent
        active: chip.cut || chip.muted || chip.teaser
        sourceComponent: Item {
            FontMetrics { id: fm; font: label.font }
            Rectangle {   // cut: 2 px line through, in the text's colour (white on a search match or under the mouse)
                visible: chip.cut
                width: parent.width
                height: 2
                y: Math.round(label.baselineOffset - fm.strikeOutPosition) - 1
                color: label.color
            }
            Image {       // muted: violet wavy underline; a cut word only shows the line through
                visible: chip.muted && !chip.cut
                width: parent.width
                height: 4
                y: Math.round(label.baselineOffset) + 1
                source: "data:image/svg+xml," + encodeURIComponent(
                    "<svg xmlns='http://www.w3.org/2000/svg' width='6' height='4'>"
                    + "<path d='M0 2 Q1.5 0.2 3 2 T6 2' fill='none' stroke='#8b5cff' stroke-width='1.5'/></svg>")
                sourceSize: Qt.size(6, 4)
                fillMode: Image.TileHorizontally
            }
            Rectangle {   // teaser: 2 px amber bottom border
                visible: chip.teaser
                anchors.bottom: parent.bottom
                width: parent.width
                height: 2
                color: Theme.warn
            }
        }
    }
}
