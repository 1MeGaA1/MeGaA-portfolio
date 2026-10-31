import QtQuick
import QtQuick.Shapes

// One grid cell, drawn the way app/grid.py GridDelegate._paint_cell paints it: grid lines,
// checkbox, elided text, right-aligned tag pills, the ×N duplicate badge and find marks.
// Most cells are empty, so an empty cell is just two lines and an empty Text — every extra
// piece is a Loader or a Repeater that creates nothing until the cell needs it.
// The grid's selection fill and cursor are overlays in the main table; the pinned row-1 strip
// sits above them, so its copies (`pinned`) draw their own selection and cursor.
Item {
    id: cell

    required property int row
    required property int column
    required property string label
    required property string raw
    required property bool filled
    required property bool bold
    required property string check
    required property bool link
    required property var tags
    required property int dup
    required property int match

    // Shared state handed in by Grid.qml (one copy there, not one per cell).
    property string findQuery: ""
    property string filterTag: ""
    property FontMetrics textMetrics: null
    property FontMetrics boldMetrics: null
    property FontMetrics tagMetrics: null

    // Pinned-strip copy: draws the selection fill / cursor itself.
    property bool pinned: false
    property bool selected: false
    property bool current: false

    // Read by Grid.qml for the hover tooltip and link / tag clicks. (Text.truncated stays
    // false for single-line elided text, so compare the natural width with the room.)
    readonly property bool truncated: cell.filled && noteText.implicitWidth > noteText.width + 0.5

    readonly property bool hasTags: cell.filled && !!cell.tags && cell.tags.length > 0
    readonly property bool dimmed: cell.filterTag !== "" && !(cell.hasTags && cell.tags.indexOf(cell.filterTag) >= 0)
    readonly property real cellW: cell.width - 1   // the last pixel column / row is the grid line
    readonly property real cellH: cell.height - 1
    readonly property real tagH: cell.tagMetrics ? Math.ceil(cell.tagMetrics.height) + 2 : 16
    readonly property real tagY: Math.round((cell.cellH - cell.tagH) / 2)
    // (measurements read `.font` so they re-run when the notes font or bold mode changes —
    // advanceWidth() calls alone are not binding dependencies)
    readonly property real badgeW: cell.dup > 0 && cell.tagMetrics && cell.tagMetrics.font
                                   ? Math.ceil(cell.tagMetrics.advanceWidth("×" + cell.dup)) + 10 : 0
    readonly property bool badgeShown: cell.badgeW > 0 && cell.cellW - 8 - cell.badgeW >= 8 + 30
    readonly property real pillsRight: cell.cellW - 8 - (cell.badgeShown ? cell.badgeW + 6 : 0)
    readonly property var pills: cell.hasTags && cell.tagMetrics ? cell.layoutPills() : []
    readonly property real textX: 8 + (cell.filled && cell.check !== "" ? 20 : 0)
    readonly property real textRight: cell.pills.length > 0 ? cell.pills[cell.pills.length - 1].x - 6 : cell.pillsRight
    readonly property real avail: cell.textRight - cell.textX
    readonly property var hit: cell.findQuery !== "" && cell.filled && !cell.dimmed && cell.avail > 10
                               ? cell.findHit() : null

    // Tag pills right to left from the badge; a pill that would come within 30 px of the
    // left padding is dropped, together with every pill left of it (tag_pill_rects).
    function layoutPills() {
        const out = []
        if (!cell.tagMetrics.font)
            return out
        let right = cell.pillsRight
        for (let i = cell.tags.length - 1; i >= 0; --i) {
            const w = Math.ceil(cell.tagMetrics.advanceWidth("#" + cell.tags[i])) + 10
            const left = right - w
            if (left < 8 + 30)
                break
            out.push({ tag: cell.tags[i], x: left, w: w })
            right = left - 6
        }
        return out
    }

    // Where the find query sits in the text — only when the whole match is visible.
    function findHit() {
        const at = cell.label.toLowerCase().indexOf(cell.findQuery.toLowerCase())
        const fm = cell.bold ? cell.boldMetrics : cell.textMetrics
        if (at < 0 || !fm || !fm.font)
            return null
        const pre = fm.advanceWidth(cell.label.substring(0, at))
        const w = fm.advanceWidth(cell.label.substring(at, at + cell.findQuery.length))
        const room = cell.avail - (cell.truncated ? fm.advanceWidth("…") : 0)
        if (pre + w > room)
            return null
        return { x: cell.textX + pre - 1, w: w + 2, h: Math.ceil(fm.height) + 2 }
    }

    // The tag pill under a point in cell coordinates, or "".
    function tagAt(x, y) {
        if (cell.pills.length === 0 || y < cell.tagY || y >= cell.tagY + cell.tagH)
            return ""
        for (const p of cell.pills) {
            if (x >= p.x && x < p.x + p.w)
                return p.tag
        }
        return ""
    }

    // Selection fill of a pinned copy, or the current find match.
    Rectangle {
        anchors.fill: parent
        visible: cell.match === 2 || (cell.pinned && cell.selected)
        color: Theme.c.ACCENT_BG
    }

    // Grid lines: every cell draws its own right and bottom edge.
    Rectangle {
        x: cell.width - 1
        width: 1
        height: cell.height
        color: Theme.c.CELL_BORDER
    }
    Rectangle {
        y: cell.height - 1
        width: cell.width
        height: 1
        color: Theme.c.CELL_BORDER
    }

    // Find-query highlight behind the matched characters.
    Loader {
        active: cell.hit !== null
        sourceComponent: hiComponent
    }

    Loader {
        active: cell.filled && cell.check !== ""
        x: 8
        y: Math.round(cell.cellH / 2) - 7
        sourceComponent: checkComponent
    }

    Text {
        id: noteText
        x: cell.textX
        width: Math.max(0, cell.avail)
        height: cell.cellH
        visible: cell.filled && cell.avail > 10
        text: cell.label
        textFormat: Text.PlainText
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
        font.family: Theme.mono
        font.pixelSize: 13
        font.weight: cell.bold ? Theme.wBold : Theme.wNormal
        font.strikeout: cell.check === "done"
        font.underline: cell.link
        color: cell.dimmed ? Theme.c.DIM
             : cell.link ? Theme.c.ACCENT
             : cell.check === "done" ? Theme.c.MUTED
             : Theme.c.TEXT
    }

    // A count model (not the array itself): when a recycled cell gets the same number of
    // pills, the existing pill items are kept and just rebound instead of rebuilt.
    Repeater {
        model: cell.pills.length
        delegate: Rectangle {
            id: pill
            required property int index
            readonly property var p: cell.pills[pill.index] || { tag: "", x: 0, w: 0 }
            x: pill.p.x
            y: cell.tagY
            width: pill.p.w
            height: cell.tagH
            radius: 3
            color: cell.dimmed ? Theme.c.TAG_BG_DIM : Theme.c.TAG_BG

            Text {
                anchors.centerIn: parent
                text: "#" + pill.p.tag
                textFormat: Text.PlainText
                font.family: Theme.mono
                font.pixelSize: 11
                font.weight: Theme.wNormal
                color: cell.dimmed ? Theme.c.TAG_DIM : Theme.c.TAG
            }
        }
    }

    Loader {
        active: cell.badgeShown
        x: cell.cellW - 8 - cell.badgeW
        y: cell.tagY
        sourceComponent: badgeComponent
    }

    // Another find match on this sheet: dashed outline.
    Loader {
        active: cell.match === 1
        anchors.fill: parent
        sourceComponent: dashComponent
    }

    // Cursor of a pinned copy, or the current find match: solid outline.
    Rectangle {
        anchors.fill: parent
        visible: cell.match === 2 || (cell.pinned && cell.current)
        color: "transparent"
        border.color: Theme.c.ACCENT
        border.width: 1
    }

    Component {
        id: hiComponent
        Rectangle {
            x: cell.hit ? cell.hit.x : 0
            y: cell.hit ? Math.round((cell.cellH - cell.hit.h) / 2) : 0
            width: cell.hit ? cell.hit.w : 0
            height: cell.hit ? cell.hit.h : 0
            color: Theme.c.HI
        }
    }

    Component {
        id: checkComponent
        Item {
            width: 14
            height: 14

            Rectangle {   // to do: an outlined box
                visible: cell.check !== "done"
                x: 1
                y: 1
                width: 12
                height: 12
                radius: 2
                antialiasing: true
                color: "transparent"
                border.width: 1.5
                border.color: cell.dimmed ? Theme.c.DIM_STROKE : Theme.c.MUTED
            }

            Rectangle {   // done: a filled box with a tick
                visible: cell.check === "done"
                anchors.fill: parent
                radius: 2
                antialiasing: true
                color: cell.dimmed ? Theme.c.DIM_STROKE : Theme.c.ACCENT

                // Tick (3,7) → (6,10) → (11,4), drawn as two round-capped strokes.
                Rectangle {
                    x: 4.5 - width / 2
                    y: 8.5 - height / 2
                    width: 4.24 + 1.8
                    height: 1.8
                    radius: 0.9
                    rotation: 45
                    antialiasing: true
                    color: Theme.c.BG
                }
                Rectangle {
                    x: 8.5 - width / 2
                    y: 7 - height / 2
                    width: 7.81 + 1.8
                    height: 1.8
                    radius: 0.9
                    rotation: -50.2
                    antialiasing: true
                    color: Theme.c.BG
                }
            }
        }
    }

    Component {
        id: badgeComponent
        Rectangle {
            width: cell.badgeW
            height: cell.tagH
            radius: 3
            color: Theme.alpha(Theme.c.RED, cell.dimmed ? 0.1 : 0.2)

            Text {
                anchors.centerIn: parent
                text: "×" + cell.dup
                textFormat: Text.PlainText
                font.family: Theme.mono
                font.pixelSize: 11
                font.weight: Theme.wNormal
                color: cell.dimmed ? Theme.c.DIM : Theme.c.RED
            }
        }
    }

    Component {
        id: dashComponent
        Shape {
            ShapePath {
                strokeColor: Theme.c.ACCENT
                strokeWidth: 1
                strokeStyle: ShapePath.DashLine
                dashPattern: [3, 2]
                fillColor: "transparent"
                startX: 1.5
                startY: 1.5
                PathLine { x: cell.cellW - 1.5; y: 1.5 }
                PathLine { x: cell.cellW - 1.5; y: cell.cellH - 1.5 }
                PathLine { x: 1.5; y: cell.cellH - 1.5 }
                PathLine { x: 1.5; y: 1.5 }
            }
        }
    }
}
