"""The spreadsheet grid: model over a Sheet, custom-painted cells and headers."""
from __future__ import annotations

from PySide6.QtCore import (
    QAbstractTableModel,
    QEasingCurve,
    QEvent,
    QItemSelection,
    QItemSelectionModel,
    QModelIndex,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QKeyEvent, QKeySequence, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QPlainTextEdit, QStyle, QStyledItemDelegate, QTableView

from . import theme
from .model import COLS, MAX_COLS, MAX_ROWS, ROWS, Cell, Sheet, col_name, current_region, duplicate_counts

PAD_ROWS = 30  # empty rows kept visible past the last note
PAD_COLS = 4

ROW_HEIGHT = 28
COL_WIDTH = 180
MIN_COL_WIDTH = 110
MAX_COL_WIDTH = 440
ROW_HEADER_WIDTH = 44


class ViewState:
    """What the grid should emphasise right now: the cursor, find matches, a tag filter."""

    def __init__(self) -> None:
        self.current: tuple[int, int] | None = None
        self.query = ""
        self.matches: set[tuple[int, int]] = set()  # matches on the visible sheet
        self.current_match: tuple[int, int] | None = None
        self.filter_tag: str | None = None

    def clear_find(self) -> None:
        self.query = ""
        self.matches.clear()
        self.current_match = None


class GridModel(QAbstractTableModel):
    """Grid over a sheet that grows with the content, Excel-style."""

    def __init__(self, sheet: Sheet, parent=None) -> None:
        super().__init__(parent)
        self.sheet = sheet
        self._rows, self._cols = self._target_size()
        self.dups = duplicate_counts(sheet)

    def _target_size(self) -> tuple[int, int]:
        max_row = max((r for r, _ in self.sheet.cells), default=-1)
        max_col = max((c for _, c in self.sheet.cells), default=-1)
        rows = min(MAX_ROWS, max(ROWS, max_row + 1 + PAD_ROWS))
        cols = min(MAX_COLS, max(COLS, max_col + 1 + PAD_COLS))
        return rows, cols

    def sync_size(self) -> None:
        """Grow the grid when content moved past its edge (shrinking waits for a sheet switch)."""
        rows, cols = self._target_size()
        if rows > self._rows:
            self.beginInsertRows(QModelIndex(), self._rows, rows - 1)
            self._rows = rows
            self.endInsertRows()
        if cols > self._cols:
            self.beginInsertColumns(QModelIndex(), self._cols, cols - 1)
            self._cols = cols
            self.endInsertColumns()

    def set_sheet(self, sheet: Sheet) -> None:
        self.beginResetModel()
        self.sheet = sheet
        self._rows, self._cols = self._target_size()
        self.dups = duplicate_counts(sheet)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else self._rows

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else self._cols

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        cell = self.sheet.get(index.row(), index.column())
        if role == Qt.ItemDataRole.DisplayRole:
            return cell.text if cell else ""
        if role == Qt.ItemDataRole.UserRole:
            return cell
        if role == Qt.ItemDataRole.ToolTipRole:
            if cell and ("\n" in cell.text or len(cell.text) > 24):
                return cell.text
            return None
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if role == Qt.ItemDataRole.DisplayRole:
            return col_name(section) if orientation == Qt.Orientation.Horizontal else str(section + 1)
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def cell_changed(self, row: int, col: int) -> None:
        self.sync_size()
        had_dups = bool(self.dups)
        self.dups = duplicate_counts(self.sheet)
        if had_dups or self.dups:
            self.dataChanged.emit(self.index(0, 0), self.index(self._rows - 1, self._cols - 1))
        else:
            idx = self.index(row, col)
            self.dataChanged.emit(idx, idx)

    def refresh(self) -> None:
        self.sync_size()
        self.dups = duplicate_counts(self.sheet)
        self.dataChanged.emit(self.index(0, 0), self.index(self._rows - 1, self._cols - 1))


class Header(QHeaderView):
    """Row / column headers painted by hand so the selected rows and columns light up."""

    def __init__(self, orientation: Qt.Orientation, parent=None) -> None:
        super().__init__(orientation, parent)
        self.highlighted: set[int] = set()
        self.setSectionsClickable(True)
        self.setHighlightSections(False)
        self.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        if orientation == Qt.Orientation.Horizontal:
            self.setDefaultSectionSize(COL_WIDTH)
            self.setFixedHeight(ROW_HEIGHT)
        else:
            self.setDefaultSectionSize(ROW_HEIGHT)
            self.setFixedWidth(ROW_HEADER_WIDTH)
        self.setFont(theme.mono(11))

    def set_highlighted(self, sections: set[int]) -> None:
        if sections != self.highlighted:
            self.highlighted = set(sections)
            self.viewport().update()

    def paintSection(self, painter: QPainter, rect: QRect, logical_index: int) -> None:  # noqa: N802
        painter.save()
        lit = logical_index in self.highlighted
        painter.fillRect(rect, QColor(theme.ACCENT_BG if lit else theme.PANEL))
        painter.setPen(QPen(QColor(theme.CELL_BORDER)))
        if self.orientation() == Qt.Orientation.Horizontal:
            painter.drawLine(rect.topRight(), rect.bottomRight())
            painter.setPen(QPen(QColor(theme.BORDER)))
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        else:
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
            painter.setPen(QPen(QColor(theme.BORDER)))
            painter.drawLine(rect.topRight(), rect.bottomRight())
        painter.setFont(self.font())
        painter.setPen(QColor(theme.ACCENT if lit else theme.MUTED))
        label = str(self.model().headerData(logical_index, self.orientation(), Qt.ItemDataRole.DisplayRole))
        if self.orientation() == Qt.Orientation.Horizontal:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
        else:
            painter.drawText(rect.adjusted(0, 0, -8, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)
        painter.restore()


def tag_pill_rects(rect: QRect, tags: list[str], fm_tag: QFontMetrics,
                   right_inset: int = 0) -> list[tuple[QRect, str]]:
    """Where each tag pill sits inside a painted cell, right-aligned (same math as the painter)."""
    out: list[tuple[QRect, str]] = []
    right = rect.right() - 8 - right_inset
    x_min = rect.left() + 8 + 30
    mid_y = rect.center().y()
    for tag in reversed(tags):
        label = "#" + tag
        w = fm_tag.horizontalAdvance(label) + 10
        h = fm_tag.height() + 2
        pill = QRect(right - w, mid_y - h // 2, w, h)
        if pill.left() < x_min:
            break
        out.append((pill, tag))
        right = pill.left() - 6
    return out


class GridDelegate(QStyledItemDelegate):
    def __init__(self, state: ViewState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.font_text = theme.mono(13)
        self.font_bold = theme.mono(13, bold=True)
        self.font_tag = theme.mono(11)

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(COL_WIDTH, ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        cell: Cell | None = index.data(Qt.ItemDataRole.UserRole)
        rect: QRect = option.rect
        pos = (index.row(), index.column())
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_current = self.state.current == pos
        is_match = pos in self.state.matches
        is_current_match = self.state.current_match == pos
        dimmed = self.state.filter_tag is not None and not (cell is not None and self.state.filter_tag in cell.tags)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        if selected or is_current_match:
            painter.fillRect(rect, QColor(theme.ACCENT_BG))

        if cell is not None:
            self._paint_cell(painter, rect, cell, dimmed, index.model().dups.get(pos, 0))

        if is_current or is_current_match:
            painter.setPen(QPen(QColor(theme.ACCENT), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
        elif is_match:
            pen = QPen(QColor(theme.ACCENT), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(1, 1, -2, -2))
        painter.restore()

    def _paint_cell(self, painter: QPainter, rect: QRect, cell: Cell, dimmed: bool, dup: int = 0) -> None:
        x = rect.left() + 8
        right = rect.right() - 8
        mid_y = rect.center().y()
        fm_tag = QFontMetrics(self.font_tag)

        # The duplicate counter badge sits rightmost.
        inset = 0
        if dup:
            label = f"×{dup}"
            w = fm_tag.horizontalAdvance(label) + 10
            h = fm_tag.height() + 2
            pill = QRect(right - w, mid_y - h // 2, w, h)
            if pill.left() >= x + 30:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setPen(Qt.PenStyle.NoPen)
                badge_bg = QColor(theme.RED)
                badge_bg.setAlpha(26 if dimmed else 52)
                painter.setBrush(badge_bg)
                painter.drawRoundedRect(pill, 3, 3)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                painter.setPen(QColor(theme.DIM if dimmed else theme.RED))
                painter.setFont(self.font_tag)
                painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, label)
                right = pill.left() - 6
                inset = w + 6

        # Tag pills, right-aligned.
        pills = tag_pill_rects(rect, cell.tags, fm_tag, inset)
        for pill, tag in pills:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(theme.TAG_BG_DIM if dimmed else theme.TAG_BG))
            painter.drawRoundedRect(pill, 3, 3)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            painter.setPen(QColor(theme.TAG_DIM if dimmed else theme.TAG))
            painter.setFont(self.font_tag)
            painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, "#" + tag)
        if pills:
            right = pills[-1][0].left() - 6

        # Checkbox.
        if cell.check is not None:
            box = QRect(x, mid_y - 7, 14, 14)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if cell.check == "done":
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(theme.DIM_STROKE if dimmed else theme.ACCENT))
                painter.drawRoundedRect(box, 2, 2)
                pen = QPen(QColor(theme.BG), 1.8)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPolyline([
                    QPoint(box.left() + 3, box.top() + 7),
                    QPoint(box.left() + 6, box.top() + 10),
                    QPoint(box.left() + 11, box.top() + 4),
                ])
            else:
                painter.setPen(QPen(QColor(theme.DIM_STROKE if dimmed else theme.MUTED), 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(box.adjusted(1, 1, -1, -1), 2, 2)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            x += 14 + 6

        # Text.
        font = QFont(self.font_bold if cell.bold else self.font_text)
        color = QColor(theme.DIM if dimmed else theme.TEXT)
        if cell.check == "done":
            font.setStrikeOut(True)
            color = QColor(theme.DIM if dimmed else theme.MUTED)
        if cell.is_link:
            font.setUnderline(True)
            color = QColor(theme.DIM if dimmed else theme.ACCENT)
        avail = right - x
        if avail <= 10:
            return
        painter.setFont(font)
        fm = QFontMetrics(font)
        text = cell.text.replace("\n", "  ")
        elided = fm.elidedText(text, Qt.TextElideMode.ElideRight, avail)
        text_rect = QRect(x, rect.top(), avail, rect.height())

        query = self.state.query
        if query and not dimmed:
            hit = text.lower().find(query.lower())
            if hit >= 0 and (elided == text or hit + len(query) < len(elided) - 1):
                pre_w = fm.horizontalAdvance(text[:hit])
                match_w = fm.horizontalAdvance(text[hit:hit + len(query)])
                if pre_w + match_w <= avail:
                    hl = QRect(x + pre_w - 1, mid_y - fm.height() // 2 - 1, match_w + 2, fm.height() + 2)
                    painter.fillRect(hl, QColor(theme.HI))
        painter.setPen(color)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)


class CellEditor(QPlainTextEdit):
    """Excel-style in-place editor that floats over the cell being edited."""

    finished = Signal(bool, str, int, int)  # commit?, text, move rows, move cols

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("celleditor")
        self.setFont(theme.mono(13))
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setTabChangesFocus(False)
        self.document().setDocumentMargin(3)
        self._finishing = False
        self.hide()

    def open_at(self, rect: QRect, text: str) -> None:
        self._finishing = False
        self.setGeometry(rect)
        self.setPlainText(text)
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def finish(self, commit: bool, d_row: int, d_col: int) -> None:
        if self._finishing or not self.isVisible():
            return
        self._finishing = True
        text = self.toPlainText()
        self.hide()
        self.finished.emit(commit, text, d_row, d_col)
        self._finishing = False

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        mods = event.modifiers()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if mods & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
                self.insertPlainText("\n")
            else:
                self.finish(True, 1, 0)
            return
        if key == Qt.Key.Key_Tab:
            self.finish(True, 0, 1)
            return
        if key == Qt.Key.Key_Backtab:
            self.finish(True, 0, -1)
            return
        if key == Qt.Key.Key_Escape:
            self.finish(False, 0, 0)
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        if self.isVisible() and not self._finishing:
            self.finish(True, 0, 0)


class GridView(QTableView):
    edit_requested = Signal(object)  # str typed to start with, or None
    edit_committed = Signal(int, int, str, int, int)  # row, col, text, move rows, move cols
    edit_cancelled = Signal()
    clear_requested = Signal()
    escape_pressed = Signal()
    link_activated = Signal(str)
    current_cell_changed = Signal(int, int)
    selection_changed = Signal()
    tag_clicked = Signal(str)
    copy_requested = Signal()
    cut_requested = Signal()
    paste_requested = Signal(bool)  # True = spread across cells, False = paste as one note

    def __init__(self, model: GridModel, state: ViewState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.setModel(model)
        self.setItemDelegate(GridDelegate(state, self))
        self.setHorizontalHeader(Header(Qt.Orientation.Horizontal, self))
        self.setVerticalHeader(Header(Qt.Orientation.Vertical, self))
        self.horizontalHeader().setDefaultSectionSize(COL_WIDTH)
        self.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ContiguousSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setTabKeyNavigation(True)
        self.setShowGrid(True)
        self.setCornerButtonEnabled(True)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCurrentIndex(model.index(0, 0))
        self.selectionModel().currentChanged.connect(self._on_current_changed)
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._on_current_changed(self.currentIndex(), QModelIndex())
        self._on_selection_changed()
        self._edit_cell = (0, 0)
        self.editor = CellEditor(self.viewport())
        self.editor.finished.connect(self._on_editor_finished)
        self.editor.textChanged.connect(self._grow_editor)
        self.verticalScrollBar().valueChanged.connect(self._grow_editor)
        self.horizontalScrollBar().valueChanged.connect(self._grow_editor)
        self._swipe_v = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._swipe_h = QPropertyAnimation(self.horizontalScrollBar(), b"value", self)
        for anim in (self._swipe_v, self._swipe_h):
            anim.setDuration(400)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._freeze_row = False
        self.frozen = QTableView(self)
        self.frozen.setModel(model)
        self.frozen.setSelectionModel(self.selectionModel())
        self.frozen.setItemDelegate(GridDelegate(state, self.frozen))
        self.frozen.setVerticalHeader(Header(Qt.Orientation.Vertical, self.frozen))
        self.frozen.horizontalHeader().hide()
        self.frozen.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.frozen.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.frozen.setAutoScroll(False)
        self.frozen.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frozen.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frozen.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.frozen.setShowGrid(True)
        self.frozen.setStyleSheet(
            f"QTableView {{ background: {theme.BG}; border: none; border-bottom: 2px solid {theme.BORDER}; "
            f"gridline-color: {theme.CELL_BORDER}; }}")
        self.frozen.viewport().installEventFilter(self)
        self.horizontalScrollBar().valueChanged.connect(
            lambda value: self.frozen.horizontalScrollBar().setValue(value))
        self.frozen.hide()

    # -- selection helpers --------------------------------------------------
    def current_cell(self) -> tuple[int, int]:
        idx = self.currentIndex()
        if not idx.isValid():
            return 0, 0
        return idx.row(), idx.column()

    def selected_cells(self) -> list[tuple[int, int]]:
        cells = [(i.row(), i.column()) for i in self.selectionModel().selectedIndexes()]
        return cells or [self.current_cell()]

    def selection_bounds(self) -> tuple[int, int, int, int]:
        """(top, left, bottom, right) of the selected block."""
        cells = self.selected_cells()
        rows = [r for r, _ in cells]
        cols = [c for _, c in cells]
        return min(rows), min(cols), max(rows), max(cols)

    def select_cell(self, row: int, col: int, scroll: bool = True) -> None:
        row = max(0, min(self.model().rowCount() - 1, row))
        col = max(0, min(self.model().columnCount() - 1, col))
        idx = self.model().index(row, col)
        self._set_current(idx)
        self.selectionModel().select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        if scroll:
            self.scrollTo(idx)

    def select_range(self, top: int, left: int, bottom: int, right: int, scroll: bool = True) -> None:
        top, bottom = max(0, min(top, bottom)), min(self.model().rowCount() - 1, max(top, bottom))
        left, right = max(0, min(left, right)), min(self.model().columnCount() - 1, max(left, right))
        model = self.model()
        self._set_current(model.index(top, left))
        selection = QItemSelection(model.index(top, left), model.index(bottom, right))
        self.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        if scroll:
            self.scrollTo(model.index(top, left))

    def move_by(self, d_row: int, d_col: int) -> None:
        row, col = self.current_cell()
        self.select_cell(row + d_row, col + d_col)

    def _select_used_range(self) -> None:
        """Ctrl+A, Excel's ladder: the data island around you → the filled range → the whole grid."""
        sheet = self.model().sheet
        max_r, max_c = sheet.used_extent()
        if max_r < 0:
            self.selectAll()
            return
        used = (0, 0, max_r, max_c)
        row, col = self.current_cell()
        region = current_region(sheet, row, col)

        def area(box: tuple[int, int, int, int]) -> int:
            return (box[2] - box[0] + 1) * (box[3] - box[1] + 1)

        def is_selected(box: tuple[int, int, int, int]) -> bool:
            return self.selection_bounds() == box and len(self.selected_cells()) == area(box)

        region_has_data = not (area(region) == 1 and sheet.get(row, col) is None)
        if region_has_data and region != used and not is_selected(region) and not is_selected(used):
            self.select_range(*region, scroll=False)
            self._swipe_to(region[2], region[3])
        elif not is_selected(used):
            self.select_range(0, 0, max_r, max_c, scroll=False)
            self._swipe_to(max_r, max_c)
        else:
            self.selectAll()

    def _jump_target(self, key: int) -> tuple[int, int]:
        row, col = self.current_cell()
        sheet = self.model().sheet
        max_r, max_c = sheet.used_extent()
        if key == Qt.Key.Key_Down:
            rows = [r for (r, c) in sheet.cells if c == col and r > row]
            return (max(rows) if rows else max(max_r, row), col)
        if key == Qt.Key.Key_Up:
            rows = [r for (r, c) in sheet.cells if c == col and r < row]
            return (min(rows) if rows else 0, col)
        if key == Qt.Key.Key_Right:
            cols = [c for (r, c) in sheet.cells if r == row and c > col]
            return (row, max(cols) if cols else max(max_c, col))
        cols = [c for (r, c) in sheet.cells if r == row and c < col]
        return (row, min(cols) if cols else 0)

    def _jump(self, key: int) -> None:
        """Ctrl+arrow: fly to the edge of the data in that direction."""
        target = self._jump_target(key)
        self.select_cell(*target, scroll=False)
        self._swipe_to(*target)

    def _jump_extend(self, key: int) -> None:
        """Ctrl+Shift+arrow: select from the current selection out to the data edge."""
        target = self._jump_target(key)
        top, left, bottom, right = self.selection_bounds()
        top, left = min(top, target[0]), min(left, target[1])
        bottom, right = max(bottom, target[0]), max(right, target[1])
        model = self.model()
        self._set_current(model.index(*target))
        selection = QItemSelection(model.index(top, left), model.index(bottom, right))
        self.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self._swipe_to(*target)

    def _swipe_to(self, row: int, col: int) -> None:
        """Glide the view to a cell instead of teleporting there."""
        vbar, hbar = self.verticalScrollBar(), self.horizontalScrollBar()
        self._swipe_v.stop()
        self._swipe_h.stop()
        v0, h0 = vbar.value(), hbar.value()
        self.scrollTo(self.model().index(row, col))
        v1, h1 = vbar.value(), hbar.value()
        vbar.setValue(v0)
        hbar.setValue(h0)
        if v1 != v0:
            self._swipe_v.setStartValue(v0)
            self._swipe_v.setEndValue(v1)
            self._swipe_v.start()
        if h1 != h0:
            self._swipe_h.setStartValue(h0)
            self._swipe_h.setEndValue(h1)
            self._swipe_h.start()

    def _set_current(self, idx: QModelIndex) -> None:
        """Move the cursor programmatically, always restarting the selection anchor there.

        Qt decides the selection command for event-less moves from the modifier keys that
        happen to be held (e.g. Ctrl during Ctrl+V); without this, a later Shift+arrow would
        extend from a stale anchor.
        """
        self._programmatic = True
        try:
            self.setCurrentIndex(idx)
        finally:
            self._programmatic = False

    def selectionCommand(self, index: QModelIndex, event=None):  # noqa: N802
        if getattr(self, "_programmatic", False):
            return QItemSelectionModel.SelectionFlag.ClearAndSelect
        return super().selectionCommand(index, event)

    # -- in-cell editing ------------------------------------------------------
    @property
    def editing(self) -> bool:
        return self.editor.isVisible()

    def begin_cell_edit(self, initial: str | None) -> None:
        row, col = self.current_cell()
        self._edit_cell = (row, col)
        if self._freeze_row and row == 0:
            self.frozen.hide()  # the editor lives in the main viewport; don't cover it
        self.scrollTo(self.model().index(row, col))
        cell = self.model().sheet.get(row, col)
        text = initial if initial is not None else (cell.text if cell else "")
        self.editor.open_at(self._editor_rect(), text)
        self._grow_editor()

    def commit_edit(self) -> None:
        if self.editing:
            self.editor.finish(True, 0, 0)

    def cancel_edit(self) -> None:
        if self.editing:
            self.editor.finish(False, 0, 0)

    def insert_text(self, text: str) -> None:
        if not self.editing:
            self.begin_cell_edit(None)
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        current = self.editor.toPlainText()
        if text.startswith("#") and current and not current.endswith((" ", "\n")):
            cursor.insertText(" ")
        cursor.insertText(text)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def toggle_bullet(self) -> None:
        if not self.editing:
            self.begin_cell_edit(None)
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.StartOfLine)
        if cursor.block().text().startswith("- "):
            cursor.movePosition(cursor.MoveOperation.Right, cursor.MoveMode.KeepAnchor, 2)
            cursor.removeSelectedText()
        else:
            cursor.insertText("- ")
        self.editor.setFocus()

    def _editor_rect(self) -> QRect:
        row, col = self._edit_cell
        return self.visualRect(self.model().index(row, col))

    def _grow_editor(self) -> None:
        if not self.editing:
            return
        rect = self._editor_rect()
        doc_lines = max(1, round(self.editor.document().documentLayout().documentSize().height()))
        wanted = doc_lines * self.editor.fontMetrics().lineSpacing() + 10
        max_h = max(ROW_HEIGHT, self.viewport().height() - rect.top())
        self.editor.setGeometry(rect.left(), rect.top(), rect.width(), max(rect.height() + 1, min(wanted, max_h)))

    def _on_editor_finished(self, commit: bool, text: str, d_row: int, d_col: int) -> None:
        if self._freeze_row:
            self.sync_frozen()
        if not commit or d_row or d_col:
            self.setFocus()
        row, col = self._edit_cell
        if commit:
            self.edit_committed.emit(row, col, text, d_row, d_col)
        else:
            self.edit_cancelled.emit()

    def _on_current_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        if not current.isValid():
            return
        self.state.current = (current.row(), current.column())
        if previous.isValid():
            self.update(previous)
        self.update(current)
        self.current_cell_changed.emit(current.row(), current.column())

    def _on_selection_changed(self, *_args) -> None:
        cells = self.selected_cells()
        self.verticalHeader().set_highlighted({r for r, _ in cells})
        self.horizontalHeader().set_highlighted({c for _, c in cells})
        frozen = getattr(self, "frozen", None)
        if frozen is not None:
            frozen.verticalHeader().set_highlighted({r for r, _ in cells})
        self.selection_changed.emit()

    # -- frozen first row -----------------------------------------------------
    def set_frozen(self, on: bool) -> None:
        self._freeze_row = bool(on)
        self.sync_frozen()

    def sync_frozen(self) -> None:
        if not self._freeze_row:
            self.frozen.hide()
            return
        header_h = self.horizontalHeader().height()
        width = self.verticalHeader().width() + self.viewport().width()
        self.frozen.setGeometry(0, header_h, width, ROW_HEIGHT + 2)
        for col in range(self.model().columnCount()):
            if self.frozen.columnWidth(col) != self.columnWidth(col):
                self.frozen.setColumnWidth(col, self.columnWidth(col))
        self.frozen.verticalScrollBar().setValue(0)
        self.frozen.horizontalScrollBar().setValue(self.horizontalScrollBar().value())
        self.frozen.show()
        self.frozen.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.sync_frozen()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        frozen = getattr(self, "frozen", None)
        if frozen is not None and obj is frozen.viewport():
            if event.type() == QEvent.Type.Wheel:
                delta = event.angleDelta()
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
                return True
            if event.type() == QEvent.Type.MouseButtonDblClick:
                idx = self.frozen.indexAt(event.position().toPoint())
                if idx.isValid():
                    self.select_cell(idx.row(), idx.column())
                    self.edit_requested.emit(None)
                    return True
        return super().eventFilter(obj, event)

    # -- input --------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        mods = event.modifiers()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_F2):
            self.edit_requested.emit(None)
            return
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.clear_requested.emit()
            return
        if key == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
            return
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        if event.matches(QKeySequence.StandardKey.SelectAll):
            self._select_used_range()
            return
        if ctrl and shift and key in (Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_Left, Qt.Key.Key_Right):
            self._jump_extend(key)
            return
        if ctrl and not shift and key in (Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_Left, Qt.Key.Key_Right):
            self._jump(key)
            return
        if ctrl and key == Qt.Key.Key_End:
            max_r, max_c = self.model().sheet.used_extent()
            self.select_cell(max(max_r, 0), max(max_c, 0), scroll=False)
            self._swipe_to(max(max_r, 0), max(max_c, 0))
            return
        if ctrl and key == Qt.Key.Key_Home:
            self.select_cell(0, 0)
            return
        if key == Qt.Key.Key_V and ctrl:
            self.paste_requested.emit(not shift)
            return
        if event.matches(QKeySequence.StandardKey.Paste):
            self.paste_requested.emit(True)
            return
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_requested.emit()
            return
        if event.matches(QKeySequence.StandardKey.Cut):
            self.cut_requested.emit()
            return
        text = event.text()
        plain = not (mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier))
        if text and text.isprintable() and plain:
            self.edit_requested.emit(text)
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            idx = self.indexAt(event.position().toPoint())
            cell = idx.data(Qt.ItemDataRole.UserRole) if idx.isValid() else None
            if cell is not None and cell.is_link:
                self.link_activated.emit(cell.text.strip())
                return
        if event.button() == Qt.MouseButton.LeftButton and not event.modifiers():
            pos = event.position().toPoint()
            idx = self.indexAt(pos)
            cell = idx.data(Qt.ItemDataRole.UserRole) if idx.isValid() else None
            if cell is not None and cell.tags:
                fm_tag = QFontMetrics(theme.mono(11))
                dup = self.model().dups.get((idx.row(), idx.column()), 0)
                inset = (fm_tag.horizontalAdvance(f"×{dup}") + 16) if dup else 0
                for pill, tag in tag_pill_rects(self.visualRect(idx), cell.tags, fm_tag, inset):
                    if pill.contains(pos):
                        self.select_cell(idx.row(), idx.column())
                        self.tag_clicked.emit(tag)
                        return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        idx = self.indexAt(event.position().toPoint())
        if idx.isValid():
            self.select_cell(idx.row(), idx.column())
            self.edit_requested.emit(None)
            return
        super().mouseDoubleClickEvent(event)
