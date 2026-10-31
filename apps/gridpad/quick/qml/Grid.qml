import QtQuick
import QtQuick.Controls

// The spreadsheet grid: a GPU TableView over gridModel with painted headers, the pinned row 1,
// ONE selection fill and ONE gliding cursor (overlays, not per-cell state), eased wheel
// scrolling, smooth scroll-into-view and the in-cell editor. Every decision is the backend's;
// this file draws and routes input. No Python is called per frame: backend state is mirrored
// into plain properties once per change, column positions live in a JS array.
FocusScope {
    id: root

    // ------------------------------------------------------------------ public API (Main.qml)
    readonly property bool editing: root.editorOpen

    function commitEdit() {
        if (!root.editorOpen)
            return
        const hadFocus = editor.activeFocus
        root.finishEdit(true, 0, 0)
        if (hadFocus)
            keys.forceActiveFocus()
    }

    function cancelEdit() {
        if (root.editorOpen)
            root.finishEdit(false, 0, 0)
    }

    function focusGrid() {
        if (root.editorOpen)
            editor.forceActiveFocus()
        else
            keys.forceActiveFocus()
    }

    // Ctrl+L: open the editor if needed, then toggle "- " at the start of the current line.
    function toggleBullet() {
        if (!root.editorOpen)
            root.openEditor(null)
        if (!root.editorOpen)
            return
        const t = editor.text
        const pos = editor.cursorPosition
        const start = pos > 0 ? t.lastIndexOf("\n", pos - 1) + 1 : 0
        if (t.substring(start, start + 2) === "- ")
            editor.remove(start, start + 2)
        else
            editor.insert(start, "- ")
        editor.forceActiveFocus()
    }

    function editorUndo() {
        if (!root.editorOpen)
            return false
        editor.undo()
        return true
    }

    function editorRedo() {
        if (!root.editorOpen)
            return false
        editor.redo()
        return true
    }

    // ------------------------------------------------------------------ mirrored backend state
    readonly property int curRow: backend.curRow
    readonly property int curCol: backend.curCol
    readonly property int selTop: backend.selTop
    readonly property int selLeft: backend.selLeft
    readonly property int selBottom: backend.selBottom
    readonly property int selRight: backend.selRight
    readonly property string query: backend.query
    readonly property string filterTag: backend.filterTag
    readonly property bool freeze: backend.freeze

    // ------------------------------------------------------------------ geometry
    readonly property int rh: Theme.rowHeight
    readonly property int headerH: 28
    readonly property int stripH: root.rh + 2                // pinned row + its 2 px bottom line
    readonly property int cover: root.freeze ? root.stripH : 0   // viewport top hidden by the strip
    readonly property int barSize: 10                         // scroll bars overlay the cells
    readonly property real wheelStepY: 3 * root.rh            // one notch = three rows
    readonly property real wheelStepX: 120

    property var widths: []      // local copy of backend.colWidths (default 180)
    property var colX: [0]       // colX[c] = x of column c from the left edge; colX[n] = total width
    property real totalWidth: 0
    property bool ready: false
    // The model's size, read from its own signals the moment it changes. TableView's rows /
    // columns only catch up at its next polish, so a scroll request that arrives right after
    // the model grew (Enter on the last row, a paste, a sheet switch) would be clamped short.
    property int modelRows: 0
    property int modelCols: 0
    // Where TableView actually put column 0 / row 0 in content coordinates. After a big jump
    // (a glide, a scroll-bar drag) TableView rebuilds around an estimated position, so the
    // table's left edge can sit off 0; everything we position or hit-test goes through these.
    property real offX: 0
    property real offY: 0

    function xOf(c) { return root.colLeft(c) + root.offX }
    function yOf(r) { return r * root.rh + root.offY }
    function colAtX(cx) { return root.colAtContentX(cx - root.offX) }   // content x → column
    function rowAtY(cy) { return root.rowAtContentY(cy - root.offY) }   // content y → row

    // Re-read the offsets from a loaded cell (cheap; runs whenever TableView lays out).
    function syncOffsets() {
        const c = table.leftColumn
        const r = table.topRow
        if (c < 0 || r < 0)
            return
        const it = table.itemAtCell(Qt.point(c, r))
        if (!it)
            return
        const dx = it.x - root.colLeft(c) - root.offX
        const dy = it.y - r * root.rh - root.offY
        if (Math.abs(dx) > 0.01) {
            root.offX += dx
            if (animX.running)
                root.restartAnim(animX, animX.to + dx)
        }
        if (Math.abs(dy) > 0.01) {
            root.offY += dy
            if (animY.running)
                root.restartAnim(animY, animY.to + dy)
        }
    }

    function syncModelSize() {
        const rows = gridModel.rowCount()
        const cols = gridModel.columnCount()
        const colsChanged = cols !== root.modelCols
        root.modelRows = rows
        root.modelCols = cols
        // No forceLayout here: TableView re-lays itself out after any model change anyway.
        if (colsChanged)
            root.reloadWidths(false)
        Qt.callLater(root.clampView)
    }

    function reloadWidths(relayout) {
        const src = backend.colWidths
        const n = root.modelCols > 0 ? root.modelCols : src.length
        const w = new Array(n)
        const x = new Array(n + 1)
        let acc = 0
        for (let i = 0; i < n; ++i) {
            const v = i < src.length ? Number(src[i]) : 0
            w[i] = v > 0 ? v : 180
            x[i] = acc
            acc += w[i]
        }
        x[n] = acc
        root.widths = w
        root.colX = x
        root.totalWidth = acc
        if (root.ready && relayout) {
            table.forceLayout()
            root.clampView()
        }
    }

    function colWidthAt(c) {
        return c >= 0 && c < root.widths.length ? root.widths[c] : 180
    }

    function colLeft(c) {
        const n = root.colX.length - 1
        if (c <= 0)
            return 0
        if (c <= n)
            return root.colX[c]
        return root.colX[n] + (c - n) * 180
    }

    function colAtContentX(x) {
        const n = root.colX.length - 1
        if (n <= 0)
            return 0
        let lo = 0
        let hi = n - 1
        while (lo < hi) {
            const mid = (lo + hi + 1) >> 1
            if (root.colX[mid] <= x)
                lo = mid
            else
                hi = mid - 1
        }
        return lo
    }

    function rowAtContentY(y) {
        return Math.max(0, Math.min(root.modelRows - 1, Math.floor(y / root.rh)))
    }

    function colName(c) {
        let s = ""
        let n = c + 1
        while (n > 0) {
            const m = (n - 1) % 26
            s = String.fromCharCode(65 + m) + s
            n = Math.floor((n - 1) / 26)
        }
        return s
    }

    // ------------------------------------------------------------------ scrolling
    function maxX() { return Math.max(root.offX, root.offX + root.totalWidth - table.width) }
    function maxY() { return Math.max(root.offY, root.offY + root.modelRows * root.rh - table.height) }
    function clampX(x) { return Math.max(root.offX, Math.min(root.maxX(), x)) }
    function clampY(y) { return Math.max(root.offY, Math.min(root.maxY(), y)) }
    function targetX() { return animX.running ? animX.to : table.contentX }
    function targetY() { return animY.running ? animY.to : table.contentY }

    // The table moved under a running glide (rebuild): keep heading for the same cell,
    // in the time the glide had left.
    function restartAnim(anim, to) {
        const left = Math.max(80, anim.duration - (Date.now() - anim.startedAt))
        anim.stop()
        anim.from = anim === animX ? table.contentX : table.contentY
        anim.to = anim === animX ? root.clampX(to) : root.clampY(to)
        anim.duration = left
        anim.startedAt = Date.now()
        anim.start()
    }

    // Eased scroll to `to`, retargeting any glide in progress. A glide longer than a few
    // viewports first hops to 1.5 viewports short of the target: every frame of a long glide
    // would show all-new rows anyway (TableView rebuilding each frame), so this looks the same
    // but costs one rebuild instead of a dozen, and the arrival stays perfectly smooth.
    function glideX(to, ms) {
        to = root.clampX(to)
        if (Math.abs(to - table.contentX) < 0.5) {
            animX.stop()
            table.contentX = to
            return
        }
        if (animX.running && Math.abs(animX.to - to) < 0.5)
            return
        animX.stop()
        const span = Math.max(200, table.width) * 1.5
        if (Math.abs(to - table.contentX) > span * 2)
            table.contentX = to - (to > table.contentX ? span : -span)
        animX.from = table.contentX
        animX.to = to
        animX.duration = ms
        animX.startedAt = Date.now()
        animX.start()
    }

    function glideY(to, ms) {
        to = root.clampY(to)
        if (Math.abs(to - table.contentY) < 0.5) {
            animY.stop()
            table.contentY = to
            return
        }
        if (animY.running && Math.abs(animY.to - to) < 0.5)
            return
        animY.stop()
        const span = Math.max(200, table.height) * 1.5
        if (Math.abs(to - table.contentY) > span * 2)
            table.contentY = to - (to > table.contentY ? span : -span)
        animY.from = table.contentY
        animY.to = to
        animY.duration = ms
        animY.startedAt = Date.now()
        animY.start()
    }

    function stopScroll() {
        animX.stop()
        animY.stop()
    }

    function clampView() {
        if (!root.ready)
            return
        const x = root.clampX(table.contentX)
        const y = root.clampY(table.contentY)
        if (Math.abs(x - table.contentX) > 0.5 || Math.abs(y - table.contentY) > 0.5) {
            root.stopScroll()
            table.contentX = x
            table.contentY = y
        }
    }

    // The least movement that shows the whole cell (below the pinned strip, above the bars).
    // Measured from where a running glide is heading, so quick repeats retarget smoothly.
    function ensureVisible(row, col, ms, vertical) {
        const viewW = table.width - root.barSize
        const x0 = root.xOf(col)
        const x1 = root.xOf(col + 1)
        let tx = root.targetX()
        if (x1 > tx + viewW)
            tx = x1 - viewW
        if (x0 < tx)
            tx = x0
        root.glideX(tx, ms)
        if (!vertical)
            return
        const viewH = table.height - root.barSize
        const top = row === 0 ? 0 : root.cover
        const y0 = root.yOf(row)
        const y1 = y0 + root.rh
        let ty = root.targetY()
        if (y1 > ty + viewH)
            ty = y1 - viewH
        if (y0 < ty + top)
            ty = y0 - top
        root.glideY(ty, ms)
    }

    function wheelScroll(event) {
        root.hideTip()
        const shift = (event.modifiers & Qt.ShiftModifier) !== 0
        let px = event.pixelDelta.x
        let py = event.pixelDelta.y
        if (px !== 0 || py !== 0) {
            // Touchpad: follow the fingers 1:1.
            if (shift && px === 0) {
                px = py
                py = 0
            }
            root.stopScroll()
            table.contentX = root.clampX(table.contentX - px)
            table.contentY = root.clampY(table.contentY - py)
        } else {
            // Wheel notches: eased, and spinning keeps adding to where the glide is heading.
            let ax = event.angleDelta.x
            let ay = event.angleDelta.y
            if (shift && ax === 0) {
                ax = ay
                ay = 0
            }
            if (ay !== 0)
                root.glideY(root.targetY() - ay / 120 * root.wheelStepY, 160)
            if (ax !== 0)
                root.glideX(root.targetX() - ax / 120 * root.wheelStepX, 160)
        }
        event.accepted = true
    }

    function pageRows() {
        return Math.max(1, Math.floor((table.height - root.cover - root.barSize) / root.rh))
    }

    function leftVisibleCol() {
        let c = root.colAtX(table.contentX)
        if (root.xOf(c + 1) - table.contentX < root.colWidthAt(c) / 2 && c < root.modelCols - 1)
            c++
        return c
    }

    function topVisibleRow() {
        if (table.contentY - root.offY < 0.5)
            return 0
        const y = table.contentY + root.cover
        let r = root.rowAtY(y)
        if (root.yOf(r + 1) - y < root.rh / 2 && r < root.modelRows - 1)
            r++
        return r
    }

    // ------------------------------------------------------------------ hit testing
    // px, py are in table (viewport) coordinates.
    function hitCell(px, py) {
        const pinned = root.freeze && py < root.stripH
        const cx = px + table.contentX
        const col = root.colAtX(cx)
        const row = pinned ? 0 : root.rowAtY(py + table.contentY)
        return {
            row: row, col: col, pinned: pinned,
            lx: cx - root.xOf(col),
            ly: pinned ? py : py + table.contentY - root.yOf(row)
        }
    }

    function cellItem(hit) {
        return hit.pinned ? pinnedTable.itemAtCell(Qt.point(hit.col, 0))
                          : table.itemAtCell(Qt.point(hit.col, hit.row))
    }

    function inSelection(row, col) {
        return row >= root.selTop && row <= root.selBottom && col >= root.selLeft && col <= root.selRight
    }

    // ------------------------------------------------------------------ mouse
    property string dragMode: ""      // "cells" | "rows" | "cols" while the button is held
    property int dragAnchor: 0
    property bool dragFromStrip: false
    property real dragX: 0
    property real dragY: 0
    property int lastDragRow: -1
    property int lastDragCol: -1
    property real edgeVX: 0           // edge auto-scroll speed, px/s
    property real edgeVY: 0
    property bool keepRow0: false     // a click on the pinned strip: don't scroll the grid to the top
    property bool forceTop: false     // Ctrl+Home: do scroll to the top even from the strip
    property int seenRow: 0           // cursor row as of the last selection change ...
    property bool rowArrived: false   // ... and whether that change moved it to another row
    property string lastTagKey: ""    // last tag pill pressed, to spot a double-click's second press
    property real lastTagTime: 0

    function clearArrived() {
        root.rowArrived = false
    }

    function prepareMouse() {
        root.hideTip()
        if (root.editorOpen)
            root.commitEdit()
        keys.forceActiveFocus()
    }

    function pressAt(hit, extend) {
        root.keepRow0 = hit.pinned
        backend.pressCell(hit.row, hit.col, extend)
        root.keepRow0 = false
    }

    // Hit-test BEFORE committing an open edit: the commit can re-fit column widths, and the
    // click must land on the cell that was under the pointer when it was pressed.
    function cellPressed(mouse) {
        const hit = root.hitCell(mouse.x, mouse.y)
        const item = root.cellItem(hit)
        const isLink = !!item && item.link
        const tag = item && mouse.modifiers === Qt.NoModifier ? item.tagAt(hit.lx, hit.ly) : ""
        root.prepareMouse()
        if (mouse.button === Qt.RightButton) {
            if (!root.inSelection(hit.row, hit.col))
                root.pressAt(hit, false)
            return
        }
        if ((mouse.modifiers & Qt.ControlModifier) && isLink) {
            backend.openLink(hit.row, hit.col)
            return
        }
        if (tag !== "") {
            // The second press of a double-click on the same pill must not toggle the filter
            // straight back off: like the classic grid, a double-click filters, then edits.
            const tagKey = hit.row + ":" + hit.col + ":" + hit.pinned + ":" + tag
            const now = Date.now()
            const repeat = tagKey === root.lastTagKey && now - root.lastTagTime < Qt.styleHints.mouseDoubleClickInterval
            root.lastTagKey = repeat ? "" : tagKey
            root.lastTagTime = now
            if (repeat)
                return
            root.pressAt(hit, false)
            backend.setFilter(tag)
            return
        }
        root.pressAt(hit, (mouse.modifiers & Qt.ShiftModifier) !== 0)
        root.beginDrag("cells", mouse.x, mouse.y, hit.row, hit.col, hit.pinned)
    }

    function cellDoubleClicked(mouse) {
        if (mouse.button !== Qt.LeftButton)
            return
        const hit = root.hitCell(mouse.x, mouse.y)
        root.endDrag()
        root.prepareMouse()
        root.pressAt(hit, false)
        root.openEditor(null)
    }

    // Shift+click on a header extends from the far end of the current whole-row/column selection.
    function rowAnchor(r, shift) {
        if (!shift)
            return r
        if (root.selLeft === 0 && root.selRight === root.modelCols - 1)
            return root.curRow === root.selTop ? root.selBottom : root.selTop
        return root.curRow
    }

    function colAnchor(c, shift) {
        if (!shift)
            return c
        if (root.selTop === 0 && root.selBottom === root.modelRows - 1)
            return root.curCol === root.selLeft ? root.selRight : root.selLeft
        return root.curCol
    }

    function rowHeaderPressed(mouse) {
        const hit = root.hitCell(0, mouse.y)
        root.prepareMouse()
        if (mouse.button === Qt.RightButton) {
            rowMenu.row = hit.row
            rowMenu.popup(root, mouse.x, table.y + mouse.y)   // at the press (not QCursor::pos)
            return
        }
        const from = root.rowAnchor(hit.row, (mouse.modifiers & Qt.ShiftModifier) !== 0)
        root.dragAnchor = from
        backend.selectRows(from, hit.row, root.leftVisibleCol())
        root.beginDrag("rows", mouse.x - table.x, mouse.y, hit.row, -1, hit.pinned)
    }

    function colHeaderPressed(mouse) {
        const c = root.colAtX(mouse.x + table.contentX)
        root.prepareMouse()
        if (mouse.button === Qt.RightButton) {
            colMenu.col = c
            colMenu.popup(root, table.x + mouse.x, mouse.y)
            return
        }
        const from = root.colAnchor(c, (mouse.modifiers & Qt.ShiftModifier) !== 0)
        root.dragAnchor = from
        backend.selectCols(from, c, root.topVisibleRow())
        root.beginDrag("cols", mouse.x, mouse.y - table.y, -1, c, false)
    }

    function beginDrag(mode, px, py, row, col, fromStrip) {
        root.dragMode = mode
        root.dragFromStrip = fromStrip
        root.dragX = px
        root.dragY = py
        root.lastDragRow = row
        root.lastDragCol = col
        root.edgeVX = 0
        root.edgeVY = 0
    }

    function endDrag() {
        root.dragMode = ""
        root.edgeVX = 0
        root.edgeVY = 0
    }

    // px/s for a pointer `dist` px into the edge zone (10 px inside the edge, then beyond it).
    function edgeSpeed(dist) {
        return Math.min(3000, 160 + dist * 22)
    }

    function dragMoved(px, py) {
        if (root.dragMode === "")
            return
        root.dragX = px
        root.dragY = py
        const m = 10
        let vx = 0
        let vy = 0
        if (root.dragMode !== "rows") {
            if (px < m)
                vx = -root.edgeSpeed(m - px)
            else if (px > table.width - m)
                vx = root.edgeSpeed(px - table.width + m)
        }
        if (root.dragMode !== "cols") {
            // A drag that starts on the pinned strip only scrolls up once it leaves the strip.
            const topEdge = root.dragFromStrip ? 0 : root.cover + m
            if (py < topEdge)
                vy = -root.edgeSpeed(topEdge - py)
            else if (py > table.height - m)
                vy = root.edgeSpeed(py - table.height + m)
        }
        root.edgeVX = vx
        root.edgeVY = vy
        root.applyDrag()
    }

    // The cell the dragging pointer stands for (clamped into the viewport while auto-scrolling).
    function dragCell(px, py) {
        const cx = Math.max(0, Math.min(table.width - 1, px)) + table.contentX
        let row
        if (root.freeze && py < root.stripH)
            row = root.edgeVY < 0 && table.contentY - root.offY > 0.5 ? root.rowAtY(table.contentY + root.cover) : 0
        else
            row = root.rowAtY(Math.max(0, Math.min(table.height - 1, py)) + table.contentY)
        return { row: row, col: root.colAtX(cx) }
    }

    // Only talks to Python when the cell under the pointer changes.
    function applyDrag() {
        const t = root.dragCell(root.dragX, root.dragY)
        if (root.dragMode === "cells") {
            if (t.row !== root.lastDragRow || t.col !== root.lastDragCol) {
                root.lastDragRow = t.row
                root.lastDragCol = t.col
                backend.dragTo(t.row, t.col)
            }
        } else if (root.dragMode === "rows") {
            if (t.row !== root.lastDragRow) {
                root.lastDragRow = t.row
                backend.selectRows(root.dragAnchor, t.row, root.leftVisibleCol())
            }
        } else if (root.dragMode === "cols") {
            if (t.col !== root.lastDragCol) {
                root.lastDragCol = t.col
                backend.selectCols(root.dragAnchor, t.col, root.topVisibleRow())
            }
        }
    }

    // ------------------------------------------------------------------ hover tooltip
    property int hoverRow: -1
    property int hoverCol: -1
    property bool hoverPinned: false

    function hoverAt(px, py) {
        const hit = root.hitCell(px, py)
        const item = root.cellItem(hit)
        cellMouse.cursorShape = item && item.tagAt(hit.lx, hit.ly) !== "" ? Qt.PointingHandCursor : Qt.ArrowCursor
        if (hit.row !== root.hoverRow || hit.col !== root.hoverCol || hit.pinned !== root.hoverPinned) {
            root.hoverRow = hit.row
            root.hoverCol = hit.col
            root.hoverPinned = hit.pinned
            tip.close()
            tipTimer.restart()
        }
    }

    function hideTip() {
        tipTimer.stop()
        tip.close()
        root.hoverRow = -1
        root.hoverCol = -1
    }

    function showTip() {
        if (root.editorOpen || root.dragMode !== "" || root.hoverRow < 0)
            return
        const item = root.cellItem({ row: root.hoverRow, col: root.hoverCol, pinned: root.hoverPinned })
        if (!item || !item.filled || !item.truncated)
            return
        tip.text = item.raw
        tip.x = table.x + root.xOf(root.hoverCol) - table.contentX
        tip.y = table.y + (root.hoverPinned ? root.rh : root.yOf(root.hoverRow + 1) - table.contentY) + 4
        tip.open()
    }

    // ------------------------------------------------------------------ keys
    function isPrintable(t) {
        if (t.length === 0)
            return false
        for (let i = 0; i < t.length; ++i) {
            const c = t.charCodeAt(i)
            if (c < 32 || c === 127 || (c >= 0x80 && c < 0xa0))
                return false
        }
        return true
    }

    // Keys the grid owns; Ctrl+B/K/L/Z/Y/F/S/O/N/E/H/I/T, F1, F8, Ctrl+, … stay Main's shortcuts.
    function isGridKey(e) {
        const k = e.key
        const ctrl = (e.modifiers & Qt.ControlModifier) !== 0
        const alt = (e.modifiers & Qt.AltModifier) !== 0
        const shift = (e.modifiers & Qt.ShiftModifier) !== 0
        if (alt)
            return false
        switch (k) {
        case Qt.Key_Up: case Qt.Key_Down: case Qt.Key_Left: case Qt.Key_Right:
        case Qt.Key_Home: case Qt.Key_End: case Qt.Key_Escape:
            return true
        case Qt.Key_Tab: case Qt.Key_Backtab: case Qt.Key_PageUp: case Qt.Key_PageDown:
        case Qt.Key_Return: case Qt.Key_Enter: case Qt.Key_F2: case Qt.Key_Delete: case Qt.Key_Backspace:
            return !ctrl
        case Qt.Key_A: case Qt.Key_C: case Qt.Key_X:
            return ctrl && !shift
        case Qt.Key_V:
            return ctrl
        case Qt.Key_Insert:
            return ctrl !== shift
        }
        return false
    }

    function gridKey(e) {
        const k = e.key
        const ctrl = (e.modifiers & Qt.ControlModifier) !== 0
        const shift = (e.modifiers & Qt.ShiftModifier) !== 0
        const alt = (e.modifiers & Qt.AltModifier) !== 0
        e.accepted = true
        if (!alt && (k === Qt.Key_Up || k === Qt.Key_Down || k === Qt.Key_Left || k === Qt.Key_Right)) {
            const dir = k === Qt.Key_Up ? "up" : k === Qt.Key_Down ? "down" : k === Qt.Key_Left ? "left" : "right"
            const dr = k === Qt.Key_Up ? -1 : k === Qt.Key_Down ? 1 : 0
            const dc = k === Qt.Key_Left ? -1 : k === Qt.Key_Right ? 1 : 0
            if (ctrl && shift)
                backend.jumpExtend(dir)
            else if (ctrl)
                backend.jump(dir)
            else if (shift)
                backend.extendBy(dr, dc)
            else
                backend.moveBy(dr, dc)
        } else if (!alt && !ctrl && k === Qt.Key_Tab) {
            backend.tabMove(!shift)
        } else if (!alt && !ctrl && k === Qt.Key_Backtab) {
            backend.tabMove(false)
        } else if (!alt && (k === Qt.Key_Home || k === Qt.Key_End)) {
            if (ctrl && k === Qt.Key_Home) {
                root.forceTop = true
                backend.ctrlHome()
                root.forceTop = false
            } else if (ctrl)
                backend.ctrlEnd()
            else
                backend.homeEnd(k === Qt.Key_End, shift)
        } else if (!alt && !ctrl && (k === Qt.Key_PageUp || k === Qt.Key_PageDown)) {
            // The view turns the page too, so the cursor keeps its place on screen (Excel).
            const n = root.pageRows() * (k === Qt.Key_PageUp ? -1 : 1)
            root.glideY(root.targetY() + n * root.rh, 160)
            if (shift)
                backend.extendBy(n, 0)
            else
                backend.moveBy(n, 0)
        } else if (!alt && !ctrl && (k === Qt.Key_Return || k === Qt.Key_Enter || k === Qt.Key_F2)) {
            root.openEditor(null)
        } else if (!alt && !ctrl && (k === Qt.Key_Delete || k === Qt.Key_Backspace)) {
            backend.clearCells()
        } else if (!alt && k === Qt.Key_Escape) {
            backend.escape()
        } else if (ctrl && !alt && !shift && k === Qt.Key_A) {
            backend.selectAllLadder()
        } else if (ctrl && !alt && !shift && (k === Qt.Key_C || k === Qt.Key_Insert)) {
            backend.copy()
        } else if (ctrl && !alt && !shift && k === Qt.Key_X) {
            backend.cut()
        } else if (ctrl && !alt && k === Qt.Key_V) {
            backend.paste(!shift)
        } else if (shift && !ctrl && !alt && k === Qt.Key_Insert) {
            backend.paste(true)
        } else if (root.isPrintable(e.text) && (ctrl === alt)) {
            // Plain typing (or AltGr, which arrives as Ctrl+Alt) starts editing with that character.
            root.openEditor(e.text)
        } else {
            e.accepted = false
        }
    }

    // ------------------------------------------------------------------ in-cell editor
    property bool editorOpen: false
    property int editRow: 0
    property int editCol: 0
    property bool finishing: false
    // Rows other than a pinned row 1 are clipped under the strip as they scroll up.
    readonly property int editCover: root.freeze && root.editRow > 0 ? root.rh : 0
    readonly property int editorPad: Math.max(2, Math.floor((root.rh - 1 - textFm.height) / 2))

    function openEditor(initial) {
        if (root.editorOpen)
            return
        root.hideTip()
        const r = root.curRow
        const c = root.curCol
        root.editRow = r
        root.editCol = c
        // A pinned row 1 is edited in place on the strip; anything else is scrolled into view.
        root.ensureVisible(r, c, 120, !(r === 0 && root.freeze))
        editorBox.contentY = 0
        editor.text = initial === null || initial === undefined ? backend.cellText(r, c) : initial
        editor.cursorPosition = editor.length
        root.editorOpen = true
        backend.setEditing(true)
        editor.forceActiveFocus()
        Qt.callLater(root.keepCaretVisible)
    }

    // Scroll the note inside the editor box so the caret line shows (the box can shrink under
    // a caret it showed before, e.g. while the grid scrolls the cell lower).
    function keepCaretVisible() {
        if (!root.editorOpen)
            return
        const r = editor.cursorRectangle
        const h = editorBox.height
        let cy = editorBox.contentY
        if (r.y + r.height + editor.bottomPadding > cy + h)
            cy = r.y + r.height + editor.bottomPadding - h
        if (r.y - editor.topPadding < cy)
            cy = r.y - editor.topPadding
        editorBox.contentY = Math.max(0, Math.min(cy, editorBox.contentHeight - h))
    }

    // Wheel over an overflowing note: scroll the note; at its end, let the grid scroll instead.
    function editorWheel(event) {
        let dy = event.pixelDelta.y
        if (dy === 0)
            dy = event.angleDelta.y / 120 * 3 * textFm.height
        const maxCy = Math.max(0, editorBox.contentHeight - editorBox.height)
        const cy = Math.max(0, Math.min(maxCy, editorBox.contentY - dy))
        if (dy === 0 || Math.abs(cy - editorBox.contentY) < 0.5) {
            root.wheelScroll(event)
            return
        }
        editorBox.contentY = cy
        event.accepted = true
    }

    function finishEdit(commit, dRow, dCol) {
        if (!root.editorOpen || root.finishing)
            return
        root.finishing = true
        const r = root.editRow
        const c = root.editCol
        const text = editor.text
        root.editorOpen = false
        if (!commit || dRow !== 0 || dCol !== 0)
            keys.forceActiveFocus()
        if (commit)
            backend.commitEdit(r, c, text, dRow, dCol)
        else
            backend.cancelEdit()
        root.finishing = false
    }

    function insertNewline() {
        if (editor.selectionStart !== editor.selectionEnd)
            editor.remove(editor.selectionStart, editor.selectionEnd)
        const p = editor.cursorPosition
        editor.insert(p, "\n")
        editor.cursorPosition = p + 1
    }

    function editorKey(e) {
        const k = e.key
        const ctrl = (e.modifiers & Qt.ControlModifier) !== 0
        const alt = (e.modifiers & Qt.AltModifier) !== 0
        const shift = (e.modifiers & Qt.ShiftModifier) !== 0
        if (k === Qt.Key_Return || k === Qt.Key_Enter) {
            if (shift || alt)
                root.insertNewline()
            else
                root.finishEdit(true, 1, 0)
            e.accepted = true
        } else if (k === Qt.Key_Tab && !ctrl && !alt) {
            root.finishEdit(true, 0, shift ? -1 : 1)
            e.accepted = true
        } else if (k === Qt.Key_Backtab && !ctrl && !alt) {
            root.finishEdit(true, 0, -1)
            e.accepted = true
        } else if (k === Qt.Key_Escape) {
            root.finishEdit(false, 0, 0)
            e.accepted = true
        }
    }

    // Focus left the editor: commit — unless the whole window was deactivated (Alt+Tab),
    // in which case focus comes back to the editor with the window.
    function editorFocusLost() {
        if (!root.editorOpen || root.finishing || editor.activeFocus || !root.Window.active)
            return
        root.finishEdit(true, 0, 0)
    }

    // ------------------------------------------------------------------ backend signals
    Connections {
        target: backend

        // With row 1 pinned, a cursor moving ALONG it (or a click on the strip) needs no
        // vertical scroll — it is always on screen; arriving at it from below (or Ctrl+Home)
        // still glides the grid up to the top.
        function onScrollRequested(row, col, glide) {
            const alongStrip = row === 0 && root.freeze && !root.forceTop && (root.keepRow0 || !root.rowArrived)
            root.ensureVisible(row, col, glide ? 400 : 120, !alongStrip)
        }

        function onSelectionChanged() {
            const r = backend.curRow
            root.rowArrived = r !== root.seenRow
            root.seenRow = r
            if (root.rowArrived)
                Qt.callLater(root.clearArrived)
        }

        function onCommitEditRequested() {
            root.commitEdit()
        }

        function onCancelEditRequested() {
            if (!root.editorOpen)
                return
            root.finishing = true
            const hadFocus = editor.activeFocus
            root.editorOpen = false
            if (hadFocus)
                keys.forceActiveFocus()
            root.finishing = false
            backend.setEditing(false)
        }

        function onFocusGridRequested() {
            root.focusGrid()
        }

        // F8 while editing a row-1 cell on the strip: unpinned, that cell lives at the top of
        // the grid, which may be scrolled far away; bring it (and the editor) into view.
        function onFreezeChanged() {
            if (root.editorOpen && root.editRow === 0 && !backend.freeze)
                root.ensureVisible(0, root.editCol, 120, true)
        }

        function onColWidthsChanged() {
            root.reloadWidths(true)
        }
    }

    Connections {
        target: gridModel
        function onRowsInserted() { root.syncModelSize() }
        function onRowsRemoved() { root.syncModelSize() }
        function onColumnsInserted() { root.syncModelSize() }
        function onColumnsRemoved() { root.syncModelSize() }
        function onModelReset() { root.syncModelSize() }
    }

    Component.onCompleted: {
        root.modelRows = gridModel.rowCount()
        root.modelCols = gridModel.columnCount()
        root.reloadWidths(false)
        root.ready = true
        table.forceLayout()
    }

    onWidthChanged: Qt.callLater(root.clampView)
    onHeightChanged: Qt.callLater(root.clampView)

    // Shared measurements for every cell (pills, badges, find highlight).
    FontMetrics { id: textFm; font.family: Theme.mono; font.pixelSize: 13; font.weight: Theme.wNormal }
    FontMetrics { id: boldFm; font.family: Theme.mono; font.pixelSize: 13; font.weight: Theme.wBold }
    FontMetrics { id: tagFm; font.family: Theme.mono; font.pixelSize: 11; font.weight: Theme.wNormal }

    NumberAnimation {
        id: animX
        property real startedAt: 0
        target: table
        property: "contentX"
        easing.type: Easing.OutCubic
    }
    NumberAnimation {
        id: animY
        property real startedAt: 0
        target: table
        property: "contentY"
        easing.type: Easing.OutCubic
    }

    // Edge auto-scroll while drag-selecting past an edge (frame-synced, no timers).
    FrameAnimation {
        running: root.dragMode !== "" && (root.edgeVX !== 0 || root.edgeVY !== 0)
        onTriggered: {
            const dt = Math.min(frameTime, 0.05)
            root.stopScroll()
            if (root.edgeVX !== 0)
                table.contentX = root.clampX(table.contentX + root.edgeVX * dt)
            if (root.edgeVY !== 0)
                table.contentY = root.clampY(table.contentY + root.edgeVY * dt)
            root.applyDrag()
        }
    }

    // Wheel anywhere over the grid (cells, headers, strip, scroll bars, editor).
    WheelHandler {
        target: null
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: (event) => root.wheelScroll(event)
    }

    // Keyboard focus target while not editing.
    Item {
        id: keys
        focus: true
        Keys.onPressed: (event) => root.gridKey(event)
        Keys.onShortcutOverride: (event) => { event.accepted = root.isGridKey(event) }
    }

    // ------------------------------------------------------------------ header backgrounds
    Rectangle {
        z: 1
        width: root.width
        height: root.headerH
        color: Theme.c.PANEL
        Rectangle { y: parent.height - 1; width: parent.width; height: 1; color: Theme.c.BORDER }
    }
    Rectangle {
        z: 1
        y: root.headerH
        width: Theme.rowHeaderWidth
        height: root.height - root.headerH
        color: Theme.c.PANEL
        Rectangle { x: parent.width - 1; width: 1; height: parent.height; color: Theme.c.BORDER }
    }

    // ------------------------------------------------------------------ the table
    TableView {
        id: table
        x: Theme.rowHeaderWidth
        y: root.headerH
        width: Math.max(0, root.width - x)
        height: Math.max(0, root.height - y)
        clip: true
        interactive: false            // drag selects; scrolling is ours (eased wheel, glides)
        boundsBehavior: Flickable.StopAtBounds
        reuseItems: true
        keyNavigationEnabled: false
        pointerNavigationEnabled: false
        selectionBehavior: TableView.SelectionDisabled
        editTriggers: TableView.NoEditTriggers
        model: gridModel
        // Exact width, so the horizontal bar never changes size mid-scroll. The height is left
        // to TableView: rows are uniform, so its own estimate is exact (an explicit height goes
        // stale for a frame when the model grows and sends a jump to the wrong rows).
        contentWidth: root.totalWidth
        columnWidthProvider: function (column) { return root.colWidthAt(column) }
        rowHeightProvider: function (row) { return root.rh }

        // (model size changes arrive through syncModelSize; forcing a layout from inside
        // TableView's own rows/columns change would warn "re-layout during an ongoing layout")
        onLayoutChanged: root.syncOffsets()

        delegate: CellDelegate {
            findQuery: root.query
            filterTag: root.filterTag
            textMetrics: textFm
            boldMetrics: boldFm
            tagMetrics: tagFm
        }

        // ONE selection fill under the cells (their grid lines stay on top) ...
        // (each overlay sits in a layer at the table's real origin, so a TableView rebuild
        // moves it instantly while its own Behaviors only animate selection changes)
        Item {
            z: -1
            x: root.offX
            y: root.offY

            Rectangle {
                id: selectionFill
                x: root.colLeft(root.selLeft)
                y: root.selTop * root.rh
                width: root.colLeft(root.selRight + 1) - root.colLeft(root.selLeft)
                height: (root.selBottom - root.selTop + 1) * root.rh
                color: Theme.c.ACCENT_BG
                Behavior on x { NumberAnimation { duration: 80; easing.type: Easing.OutCubic } }
                Behavior on y { NumberAnimation { duration: 80; easing.type: Easing.OutCubic } }
                Behavior on width { NumberAnimation { duration: 80; easing.type: Easing.OutCubic } }
                Behavior on height { NumberAnimation { duration: 80; easing.type: Easing.OutCubic } }
            }
        }

        // ... and ONE cursor above them, gliding from cell to cell.
        Item {
            z: 100
            x: root.offX
            y: root.offY

            Rectangle {
                id: cursorBox
                x: root.colLeft(root.curCol)
                y: root.curRow * root.rh
                width: root.colLeft(root.curCol + 1) - root.colLeft(root.curCol)
                height: root.rh
                color: "transparent"
                border.color: Theme.c.ACCENT
                border.width: 1
                Behavior on x { NumberAnimation { duration: 85; easing.type: Easing.OutCubic } }
                Behavior on y { NumberAnimation { duration: 85; easing.type: Easing.OutCubic } }
                Behavior on width { NumberAnimation { duration: 85; easing.type: Easing.OutCubic } }
            }
        }

        ScrollBar.vertical: GridBar {
            parent: root
            z: 30
            x: root.width - width
            y: table.y + root.cover
            width: root.barSize
            height: Math.max(0, table.height - root.cover - root.barSize)
            onPressedChanged: if (pressed) root.stopScroll()
        }
        ScrollBar.horizontal: GridBar {
            parent: root
            z: 30
            x: table.x
            y: root.height - height
            width: Math.max(0, table.width - root.barSize)
            height: root.barSize
            onPressedChanged: if (pressed) root.stopScroll()
        }
    }

    // ------------------------------------------------------------------ headers
    HorizontalHeaderView {
        id: colHeader
        z: 2
        x: table.x
        width: table.width
        height: root.headerH
        syncView: table
        clip: true
        interactive: false
        resizableColumns: false
        textRole: "label"   // unused (custom delegate); must name a role the model has
        delegate: Rectangle {
            id: colCell
            required property int column
            readonly property bool lit: colCell.column >= root.selLeft && colCell.column <= root.selRight
            implicitWidth: 180
            implicitHeight: root.headerH
            color: colCell.lit ? Theme.c.ACCENT_BG : Theme.c.PANEL

            Rectangle { x: parent.width - 1; width: 1; height: parent.height; color: Theme.c.CELL_BORDER }
            Rectangle { y: parent.height - 1; width: parent.width; height: 1; color: Theme.c.BORDER }
            Text {
                anchors.centerIn: parent
                text: root.colName(colCell.column)
                font.family: Theme.mono
                font.pixelSize: 11
                font.weight: Theme.wNormal
                color: colCell.lit ? Theme.c.ACCENT : Theme.c.MUTED
            }
        }
    }

    VerticalHeaderView {
        id: rowHeader
        z: 2
        y: table.y
        width: Theme.rowHeaderWidth
        height: table.height
        syncView: table
        clip: true
        interactive: false
        resizableRows: false
        textRole: "label"
        delegate: RowHeaderCell {
            selTop: root.selTop
            selBottom: root.selBottom
        }
    }

    // Corner: select everything.
    Rectangle {
        z: 3
        width: Theme.rowHeaderWidth
        height: root.headerH
        color: Theme.c.PANEL
        Rectangle { x: parent.width - 1; width: 1; height: parent.height; color: Theme.c.BORDER }
        Rectangle { y: parent.height - 1; width: parent.width; height: 1; color: Theme.c.BORDER }
        MouseArea {
            anchors.fill: parent
            onPressed: {
                root.prepareMouse()
                backend.selectAll()
            }
        }
    }

    // ------------------------------------------------------------------ pinned row 1 (F8)
    Item {
        id: strip
        z: 4
        visible: root.freeze
        y: root.headerH
        width: root.width
        height: root.stripH

        Rectangle {   // opaque, so rows scrolling underneath never show through
            x: Theme.rowHeaderWidth
            width: parent.width - x
            height: root.rh
            color: Theme.c.BG
        }

        TableView {
            id: pinnedTable
            x: Theme.rowHeaderWidth
            width: table.width
            height: root.rh
            model: firstRowModel
            syncView: table
            syncDirection: Qt.Horizontal
            clip: true
            interactive: false
            reuseItems: true
            keyNavigationEnabled: false
            pointerNavigationEnabled: false
            selectionBehavior: TableView.SelectionDisabled
            editTriggers: TableView.NoEditTriggers
            rowHeightProvider: function (row) { return root.rh }
            delegate: CellDelegate {
                pinned: true
                selected: root.selTop === 0 && column >= root.selLeft && column <= root.selRight
                current: root.curRow === 0 && root.curCol === column
                findQuery: root.query
                filterTag: root.filterTag
                textMetrics: textFm
                boldMetrics: boldFm
                tagMetrics: tagFm
            }
        }

        RowHeaderCell {
            row: 0
            selTop: root.selTop
            selBottom: root.selBottom
            width: Theme.rowHeaderWidth
            height: root.rh
        }

        Rectangle {
            y: root.rh
            width: parent.width
            height: 2
            color: Theme.c.BORDER
        }
    }

    // ------------------------------------------------------------------ input areas
    MouseArea {
        id: cellMouse
        z: 6
        x: table.x
        y: table.y
        width: table.width
        height: table.height
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        hoverEnabled: true
        onPressed: (mouse) => root.cellPressed(mouse)
        onPositionChanged: (mouse) => {
            if (pressed)
                root.dragMoved(mouse.x, mouse.y)
            else
                root.hoverAt(mouse.x, mouse.y)
        }
        onReleased: root.endDrag()
        onCanceled: root.endDrag()
        onDoubleClicked: (mouse) => root.cellDoubleClicked(mouse)
        onExited: root.hideTip()
    }

    MouseArea {   // row numbers (and the strip's "1")
        z: 6
        y: table.y
        width: Theme.rowHeaderWidth
        height: table.height
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onPressed: (mouse) => root.rowHeaderPressed(mouse)
        onPositionChanged: (mouse) => { if (pressed) root.dragMoved(mouse.x - table.x, mouse.y) }
        onReleased: root.endDrag()
        onCanceled: root.endDrag()
    }

    MouseArea {   // column letters
        z: 6
        x: table.x
        width: table.width
        height: root.headerH
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onPressed: (mouse) => root.colHeaderPressed(mouse)
        onPositionChanged: (mouse) => { if (pressed) root.dragMoved(mouse.x, mouse.y - table.y) }
        onReleased: root.endDrag()
        onCanceled: root.endDrag()
    }

    // ------------------------------------------------------------------ editor layer
    // Above the strip and the mouse areas (so it takes its own clicks), clipped to the cells.
    // The editor follows its cell in content coordinates through contentX / contentY.
    Item {
        id: editorLayer
        z: 20
        visible: root.editorOpen
        x: table.x
        y: table.y + root.editCover
        width: table.width
        height: Math.max(0, table.height - root.editCover)
        clip: true

        // The box covers the cell and grows with its text down to the bottom of the cells
        // (above the scroll bar). A longer note scrolls inside it, the caret always in view
        // (TextArea.flickable follows the caret; keepCaretVisible covers the box shrinking).
        Flickable {
            id: editorBox
            // Cell top in viewport coordinates; a pinned row 1 is edited on the strip.
            readonly property real viewY: root.editRow === 0 && root.freeze ? 0 : root.yOf(root.editRow) - table.contentY
            readonly property bool overflows: editorBox.contentHeight > editorBox.height + 0.5
            x: root.xOf(root.editCol) - table.contentX
            y: editorBox.viewY - root.editCover
            width: root.colLeft(root.editCol + 1) - root.colLeft(root.editCol)
            height: Math.max(root.rh, Math.min(editor.implicitHeight, table.height - root.barSize - editorBox.viewY))
            interactive: false            // a drag selects text; the wheel is handled below
            boundsBehavior: Flickable.StopAtBounds
            clip: true
            onHeightChanged: if (root.editorOpen) Qt.callLater(root.keepCaretVisible)

            // Wheel over a note that overflows scrolls the note until its end, then the grid
            // (like the classic editor); otherwise it falls through to the grid's handler.
            WheelHandler {
                target: null
                enabled: root.editorOpen && editorBox.overflows
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                onWheel: (event) => root.editorWheel(event)
            }

            TextArea.flickable: TextArea {
                id: editor
                leftPadding: 8
                rightPadding: 6
                topPadding: root.editorPad
                bottomPadding: root.editorPad
                wrapMode: TextEdit.Wrap
                textFormat: TextEdit.PlainText
                selectByMouse: true
                font.family: Theme.mono
                font.pixelSize: 13
                font.weight: Theme.wNormal
                color: Theme.c.TEXT
                selectionColor: Theme.c.HI
                selectedTextColor: Theme.c.HI_TEXT
                background: Rectangle {   // (TextArea.flickable puts it on the box, unscrolled)
                    color: Theme.c.FIELD
                    border.color: Theme.c.ACCENT
                    border.width: 1
                }
                // No built-in context menu: opening it takes focus from the editor, which
                // commits and hides it under the menu and leaves the window with no focus.
                // A right-click inside the editor does nothing (and doesn't reach the grid).
                ContextMenu.menu: null
                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.RightButton
                }
                Keys.onPressed: (event) => root.editorKey(event)
                Keys.onShortcutOverride: (event) => {
                    const k = event.key
                    // Ctrl+Tab / Ctrl+Shift+Tab stay window shortcuts (switch sheet, committing the edit).
                    event.accepted = k === Qt.Key_Escape || k === Qt.Key_Return || k === Qt.Key_Enter
                                     || ((k === Qt.Key_Tab || k === Qt.Key_Backtab)
                                         && !(event.modifiers & Qt.ControlModifier))
                }
                onActiveFocusChanged: if (!activeFocus && root.editorOpen) Qt.callLater(root.editorFocusLost)
            }
        }
    }

    // ------------------------------------------------------------------ popups
    Timer {
        id: tipTimer
        interval: 450
        onTriggered: root.showTip()
    }

    ToolTip {
        id: tip
        delay: 0
        timeout: -1
        margins: 6
        padding: 8
        width: Math.min(tip.implicitWidth, 480)
        contentItem: Text {
            text: tip.text
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            font.family: Theme.mono
            font.pixelSize: 12
            font.weight: Theme.wNormal
            color: Theme.c.TEXT
        }
        background: Rectangle {
            color: Theme.c.MENU_BG
            border.color: Theme.c.MENU_BORDER
            radius: 4
        }
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 120; easing.type: Easing.OutCubic } }
        exit: Transition { NumberAnimation { property: "opacity"; to: 0; duration: 80 } }
    }

    GPMenu {
        id: rowMenu
        property int row: 0
        onClosed: root.focusGrid()
        GPMenuItem { text: "Insert row above"; onTriggered: backend.rowAction("above", rowMenu.row) }
        GPMenuItem { text: "Insert row below"; onTriggered: backend.rowAction("below", rowMenu.row) }
        GPMenuSeparator { }
        GPMenuItem { text: "Move row up"; enabled: rowMenu.row > 0; onTriggered: backend.rowAction("up", rowMenu.row) }
        GPMenuItem { text: "Move row down"; onTriggered: backend.rowAction("down", rowMenu.row) }
        GPMenuSeparator { }
        GPMenuItem { text: "Delete row " + (rowMenu.row + 1); onTriggered: backend.rowAction("delete", rowMenu.row) }
    }

    GPMenu {
        id: colMenu
        property int col: 0
        onClosed: root.focusGrid()
        GPMenuItem { text: "Insert column left"; onTriggered: backend.colAction("left", colMenu.col) }
        GPMenuItem { text: "Insert column right"; onTriggered: backend.colAction("right", colMenu.col) }
        GPMenuSeparator { }
        GPMenuItem { text: "Move column left"; enabled: colMenu.col > 0; onTriggered: backend.colAction("moveLeft", colMenu.col) }
        GPMenuItem { text: "Move column right"; onTriggered: backend.colAction("moveRight", colMenu.col) }
        GPMenuSeparator { }
        GPMenuItem { text: "Delete column " + root.colName(colMenu.col); onTriggered: backend.colAction("delete", colMenu.col) }
    }

    // ------------------------------------------------------------------ inline components
    // A row number cell (vertical header and the strip's "1"); lit while its row is selected.
    component RowHeaderCell: Rectangle {
        id: rowCell
        required property int row
        property int selTop: 0
        property int selBottom: -1
        readonly property bool lit: rowCell.row >= rowCell.selTop && rowCell.row <= rowCell.selBottom
        implicitWidth: Theme.rowHeaderWidth
        implicitHeight: Theme.rowHeight
        color: rowCell.lit ? Theme.c.ACCENT_BG : Theme.c.PANEL

        Rectangle { y: parent.height - 1; width: parent.width; height: 1; color: Theme.c.CELL_BORDER }
        Rectangle { x: parent.width - 1; width: 1; height: parent.height; color: Theme.c.BORDER }
        Text {
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            text: rowCell.row + 1
            font.family: Theme.mono
            font.pixelSize: 11
            font.weight: Theme.wNormal
            color: rowCell.lit ? Theme.c.ACCENT : Theme.c.MUTED
        }
    }

    // Scroll bar: transparent track, rounded SCROLL handle that thickens under the pointer.
    component GridBar: ScrollBar {
        id: bar
        policy: ScrollBar.AlwaysOn
        hoverEnabled: true
        padding: bar.hovered || bar.pressed ? 0 : 2
        minimumSize: 24 / Math.max(24, bar.orientation === Qt.Vertical ? bar.height : bar.width)
        Behavior on padding { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        contentItem: Rectangle {
            implicitWidth: 10
            implicitHeight: 10
            radius: Math.min(width, height) / 2
            color: bar.pressed ? Qt.lighter(Theme.c.SCROLL, 1.6)
                 : bar.hovered ? Qt.lighter(Theme.c.SCROLL, 1.3) : Theme.c.SCROLL
            Behavior on color { ColorAnimation { duration: 120 } }
        }
        background: Item {
            implicitWidth: 10
            implicitHeight: 10
        }
    }
}
