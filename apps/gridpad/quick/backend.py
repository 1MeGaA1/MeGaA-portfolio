"""Everything behind the Qt Quick window: workbook, selection, undo, find, files — exposed to QML.

QML only draws and routes input; every decision lives here, ported from app/main_window.py
and app/grid.py so both editions behave the same and share app/model.py. File pickers and
confirmations are QML popups: Python asks for them with signals and never blocks.
"""
from __future__ import annotations

import copy
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QAbstractTableModel,
    QByteArray,
    QModelIndex,
    QObject,
    QSettings,
    Qt,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices, QFontMetrics, QGuiApplication

from app import theme
from app.effects import EFFECTS
from app.export import SEPARATORS
from app.grid import COL_WIDTH, MAX_COL_WIDTH, MIN_COL_WIDTH, PAD_COLS, PAD_ROWS
from app.help import KEYS
from app.importer import IMPORT_SEPARATORS
from app.main_window import HINT_EDIT, HINT_NORMAL, HINT_RANGE, NEXT_CHECK
from app.model import (
    COLS,
    FILE_SUFFIX,
    MAX_COLS,
    MAX_ROWS,
    ROWS,
    Cell,
    Match,
    Workbook,
    cell_ref,
    col_name,
    current_region,
    dedupe_rows,
    delete_col,
    delete_row,
    duplicate_counts,
    duplicates_first,
    export_text,
    insert_col,
    insert_row,
    join_block,
    move_col,
    move_row,
    parse_delimited,
    replace_in_sheet,
    sort_rows,
    split_paste,
)
from app.settings import mono_families, ui_families

Box = tuple[int, int, int, int]

# Roles the QML cell delegate binds to (as required properties).
ROLES = ("label", "raw", "filled", "bold", "check", "link", "tags", "dup", "match")
ROLE_IDS = {Qt.ItemDataRole.UserRole + 1 + i: name for i, name in enumerate(ROLES)}
ROLE_OF = {name: role for role, name in ROLE_IDS.items()}
EMPTY_ROLES = {"label": "", "raw": "", "filled": False, "bold": False, "check": "", "link": False, "tags": []}


def _local_path(url_or_path: str) -> str:
    """QML hands file URLs (file:///C:/...); plain paths pass straight through."""
    if url_or_path.startswith("file:"):
        return QUrl(url_or_path).toLocalFile()
    return url_or_path


def _pick_sep(table: list[tuple[str, str | None]], index: int, custom: str) -> str:
    """A separator dropdown's choice; the Custom row uses the typed text (comma if blank)."""
    index = max(0, min(len(table) - 1, index))
    sep = table[index][1]
    return (custom or ",") if sep is None else sep


def _sep_preset(table: list[tuple[str, str | None]], sep: str, default_custom: str) -> dict:
    """Which dropdown row shows `sep`, and what the Custom field holds."""
    for i, (_, value) in enumerate(table):
        if value == sep:
            return {"index": i, "custom": default_custom}
    return {"index": len(table) - 1, "custom": sep}


# --------------------------------------------------------------------------- models
class GridModel(QAbstractTableModel):
    """The visible sheet for QML's TableView; grows with the content, Excel-style."""

    def __init__(self, backend: "Backend") -> None:
        super().__init__(backend)
        self.backend = backend
        self.sheet = backend.sheet
        self._rows, self._cols = self._target_size()
        self.dups = duplicate_counts(self.sheet)
        self._tag_cache: dict[str, list[str]] = {}

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

    def set_sheet(self, sheet) -> None:
        self.beginResetModel()
        self.sheet = sheet
        self._rows, self._cols = self._target_size()
        self.dups = duplicate_counts(sheet)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else self._rows

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else self._cols

    def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802
        return {role: QByteArray(name.encode()) for role, name in ROLE_IDS.items()}

    def _tags(self, cell: Cell) -> list[str]:
        tags = self._tag_cache.get(cell.text)
        if tags is None:
            if len(self._tag_cache) > 4000:
                self._tag_cache.clear()
            tags = self._tag_cache[cell.text] = cell.tags
        return tags

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        name = ROLE_IDS.get(role)
        if name is None or not index.isValid():
            return None
        pos = (index.row(), index.column())
        if name == "match":
            return self.backend.match_kind(pos)
        if name == "dup":
            return self.dups.get(pos, 0)
        cell = self.sheet.cells.get(pos)
        if cell is None:
            return EMPTY_ROLES[name]
        if name == "label":
            return cell.text.replace("\n", "  ")
        if name == "raw":
            return cell.text
        if name == "filled":
            return True
        if name == "bold":
            return cell.bold
        if name == "check":
            return cell.check or ""
        if name == "link":
            return cell.is_link
        return self._tags(cell)

    def cell_changed(self, row: int, col: int) -> None:
        """One cell changed: re-read it, and only the ×N badges elsewhere if those moved."""
        self.sync_size()
        old_dups = self.dups
        self.dups = duplicate_counts(self.sheet)
        idx = self.index(row, col)
        self.dataChanged.emit(idx, idx)
        if self.dups != old_dups:
            self.refresh_roles(["dup"])

    def refresh(self) -> None:
        self.sync_size()
        self.dups = duplicate_counts(self.sheet)
        self.dataChanged.emit(self.index(0, 0), self.index(self._rows - 1, self._cols - 1))

    def refresh_roles(self, names: list[str]) -> None:
        """Every cell, but only these roles — TableView re-reads just those through Python."""
        self.dataChanged.emit(self.index(0, 0), self.index(self._rows - 1, self._cols - 1),
                              [ROLE_OF[name] for name in names])


class FirstRowModel(QAbstractTableModel):
    """Row 1 on its own, for the pinned strip (F8) QML lays over the top of the grid."""

    def __init__(self, source: GridModel) -> None:
        super().__init__(source)
        self.source = source
        source.dataChanged.connect(self._on_data)
        source.columnsAboutToBeInserted.connect(
            lambda _parent, first, last: self.beginInsertColumns(QModelIndex(), first, last))
        source.columnsInserted.connect(lambda *_args: self.endInsertColumns())
        source.modelAboutToBeReset.connect(self.beginResetModel)
        source.modelReset.connect(self.endResetModel)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else 1

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else self.source.columnCount()

    def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802
        return self.source.roleNames()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        return self.source.data(self.source.index(0, index.column()), role)

    def _on_data(self, top_left: QModelIndex, bottom_right: QModelIndex, roles=()) -> None:
        if top_left.row() <= 0 <= bottom_right.row():
            self.dataChanged.emit(self.index(0, top_left.column()), self.index(0, bottom_right.column()),
                                  list(roles))


# --------------------------------------------------------------------------- theme
class Palette(QObject):
    """The active theme's color tokens and fonts; swapped live when Appearance changes."""

    changed = Signal()

    @Property("QVariantMap", notify=changed)
    def c(self) -> dict:
        return dict(theme.THEMES[theme.current_theme()])

    @Property(str, notify=changed)
    def name(self) -> str:
        return theme.current_theme()

    @Property(str, notify=changed)
    def mono(self) -> str:
        return theme.mono_family()

    @Property(str, notify=changed)
    def sans(self) -> str:
        return theme.sans_family()

    @Property(bool, notify=changed)
    def bold(self) -> bool:
        return theme.app_bold()

    @Property(int, notify=changed)
    def wNormal(self) -> int:  # noqa: N802
        """Weight for regular text; bold mode steps everything one weight up (see theme._weight)."""
        return 600 if theme.app_bold() else 400

    @Property(int, notify=changed)
    def wBold(self) -> int:  # noqa: N802
        return 700 if theme.app_bold() else 600

    def refresh(self) -> None:
        self.changed.emit()


# --------------------------------------------------------------------------- backend
class Backend(QObject):
    selectionChanged = Signal()
    statusChanged = Signal()
    sheetsChanged = Signal()
    fileChanged = Signal()
    findChanged = Signal()
    filterChanged = Signal()
    colWidthsChanged = Signal()
    freezeChanged = Signal()
    effectChanged = Signal()
    editingChanged = Signal()

    scrollRequested = Signal(int, int, bool)  # row, col, glide (a long eased swipe vs a quick nudge)
    commitEditRequested = Signal()  # QML: commit the in-cell editor right now (synchronously)
    cancelEditRequested = Signal()
    focusGridRequested = Signal()
    searchCleared = Signal()  # QML: empty the find box
    saveAsRequested = Signal()  # QML: open the Save dialog, then call saveTo(url)
    renameRequested = Signal(int, str)  # sheet index, current name
    importReady = Signal(str, str)  # file name, target cell ref — QML opens the Import dialog
    alert = Signal(str, str)  # title, message

    def __init__(self, workbook: Workbook, settings: QSettings | None = None, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings or QSettings("GridPad", "GridPad")
        self.workbook = workbook
        self.current = 0
        self.query = ""
        self.filter_tag: str | None = None
        self.matches: list[Match] = []
        self.match_index = -1
        self._match_set: set[tuple[int, int]] = set()
        self._current_match: tuple[int, int] | None = None
        self._last_cell: dict[int, tuple[int, int]] = {}
        self._clip: tuple[str, list[list[str]]] | None = None  # last in-app copy: (clipboard text, cells)
        self.copy_sep = str(self.settings.value("copy_sep", "\t"))  # column separator for copied blocks
        self._undo_stack: list[tuple[int, dict, dict]] = []  # (sheet index, cells before, cells after)
        self._redo_stack: list[tuple[int, dict, dict]] = []
        self._cur: tuple[int, int] = (0, 0)
        self._anchor: tuple[int, int] = (0, 0)
        self._box: Box = (0, 0, 0, 0)
        self._editing = False
        self._col_widths: list[int] = []
        self._freeze = str(self.settings.value("freeze", "true")).lower() in ("true", "1")
        self._effect = self._valid_effect(str(self.settings.value("effect", "None")))
        self._status = ("", "", "")
        self._import: tuple[str, str, str] | None = None  # (file name, decoded text, stem) waiting in the dialog
        self._fonts: tuple[list[str], list[str]] | None = None
        self._hint_timer = QTimer(self)
        self._hint_timer.setSingleShot(True)
        self._hint_timer.setInterval(2000)
        self._hint_timer.timeout.connect(self.update_status)
        self.palette = Palette(self)
        self.model = GridModel(self)
        self.first_row = FirstRowModel(self.model)
        self.refresh_all()

    # -- helpers ------------------------------------------------------------------
    @property
    def sheet(self):
        return self.workbook.sheets[self.current]

    @staticmethod
    def _valid_effect(name: str) -> str:
        return name if name in {n for n, _ in EFFECTS} else "None"

    def match_kind(self, pos: tuple[int, int]) -> int:
        """2 = the current find match, 1 = another match on this sheet, 0 = none."""
        if pos == self._current_match:
            return 2
        return 1 if pos in self._match_set else 0

    def refresh_all(self) -> None:
        self.fileChanged.emit()
        self.sheetsChanged.emit()
        self.refresh_tags()
        self.autofit_columns()
        self.update_status()

    def refresh_tags(self) -> None:
        counts = self.workbook.tag_counts()
        if self.filter_tag is not None and self.filter_tag not in counts:
            self.filter_tag = None
            self.filterChanged.emit()

    def _filtered_count(self) -> int:
        tag = self.filter_tag
        if tag is None:
            return self.workbook.total_notes()
        return sum(1 for s in self.workbook.sheets for c in s.cells.values() if tag in c.tags)

    def autofit_columns(self) -> None:
        """Size each column to its longest note (clamped), like a spreadsheet's auto-fit."""
        fm_norm = QFontMetrics(theme.mono(13))
        fm_bold = QFontMetrics(theme.mono(13, bold=True))
        fm_tag = QFontMetrics(theme.mono(11))
        needed: dict[int, int] = {}
        for (_row, col), cell in self.sheet.cells.items():
            fm = fm_bold if cell.bold else fm_norm
            # 8px padding each side, 1px grid line, plus slack so a just-fitting note never elides.
            width = 24 + fm.horizontalAdvance(cell.text.replace("\n", "  "))
            if cell.check is not None:
                width += 20
            for tag in cell.tags:
                width += fm_tag.horizontalAdvance("#" + tag) + 18
            needed[col] = max(needed.get(col, 0), width)
        widths = [max(MIN_COL_WIDTH, min(MAX_COL_WIDTH, needed.get(col, COL_WIDTH)))
                  for col in range(self.model.columnCount())]
        if widths != self._col_widths:
            self._col_widths = widths
            self.colWidthsChanged.emit()

    def update_status(self) -> None:
        total = self.workbook.total_notes()
        dup_cells = len(self.model.dups)
        dup_suffix = f" · {dup_cells} duplicates" if dup_cells else ""
        selected = self._selected_count()
        if self.filter_tag:
            notes = f"{self._filtered_count()} of {total} notes"
            hint = f"Filter: #{self.filter_tag} · Esc clears"
        elif self.query:
            n = len(self.matches)
            pos = self.match_index + 1 if n else 0
            notes = f"{total} notes"
            hint = f"Find: {self.query} · {pos} of {n} · Enter next · Esc closes"
        elif self._editing:
            notes = f"{total} notes"
            hint = HINT_EDIT
        elif selected > 1:
            notes = f"{selected} cells selected"
            hint = HINT_RANGE
        else:
            notes = (f"{total} note" if total == 1 else f"{total} notes") + dup_suffix
            hint = HINT_NORMAL
        if self.workbook.path is None:
            saved = "Unsaved · Ctrl+S" if total else "Unsaved"
        else:
            saved = "Saved" if not self.workbook.dirty else "Saving"
        self._set_status(notes, hint, saved)

    def _set_status(self, notes: str, hint: str, saved: str) -> None:
        if (notes, hint, saved) != self._status:
            self._status = (notes, hint, saved)
            self.statusChanged.emit()

    def after_change(self, row: int | None = None, col: int | None = None) -> None:
        """A cell or sheet changed: repaint, re-run find, autosave, refresh the status."""
        if row is not None and col is not None:
            self.model.cell_changed(row, col)
        else:
            self.model.refresh()
        if self.query:
            self._recompute_matches(keep_position=True)
        self.autosave()
        self.refresh_tags()
        self.autofit_columns()
        self.update_status()

    def flash_hint(self, text: str) -> None:
        notes, _hint, saved = self._status
        self._set_status(notes, text, saved)
        self._hint_timer.start()

    # -- properties: status, file, sheets ----------------------------------------
    @Property(str, notify=statusChanged)
    def statusNotes(self) -> str:  # noqa: N802
        return self._status[0]

    @Property(str, notify=statusChanged)
    def statusHint(self) -> str:  # noqa: N802
        return self._status[1]

    @Property(str, notify=statusChanged)
    def statusSaved(self) -> str:  # noqa: N802
        return self._status[2]

    @Property(str, notify=fileChanged)
    def fileName(self) -> str:  # noqa: N802
        return self.workbook.name

    @Property(str, notify=fileChanged)
    def windowTitle(self) -> str:  # noqa: N802
        return f"{self.workbook.name} — GridPad"

    @Property(bool, notify=fileChanged)
    def hasPath(self) -> bool:  # noqa: N802
        return self.workbook.path is not None

    @Property("QVariantList", notify=sheetsChanged)
    def sheetNames(self) -> list[str]:  # noqa: N802
        return [s.name for s in self.workbook.sheets]

    @Property(int, notify=sheetsChanged)
    def currentSheet(self) -> int:  # noqa: N802
        return self.current

    @Property("QVariantList", notify=colWidthsChanged)
    def colWidths(self) -> list[int]:  # noqa: N802
        return list(self._col_widths)

    # -- properties: selection -----------------------------------------------------
    @Property(int, notify=selectionChanged)
    def curRow(self) -> int:  # noqa: N802
        return self._cur[0]

    @Property(int, notify=selectionChanged)
    def curCol(self) -> int:  # noqa: N802
        return self._cur[1]

    @Property(int, notify=selectionChanged)
    def selTop(self) -> int:  # noqa: N802
        return self._box[0]

    @Property(int, notify=selectionChanged)
    def selLeft(self) -> int:  # noqa: N802
        return self._box[1]

    @Property(int, notify=selectionChanged)
    def selBottom(self) -> int:  # noqa: N802
        return self._box[2]

    @Property(int, notify=selectionChanged)
    def selRight(self) -> int:  # noqa: N802
        return self._box[3]

    @Property(str, notify=selectionChanged)
    def curRef(self) -> str:  # noqa: N802
        return cell_ref(*self._cur)

    # -- properties: find, filter, view toggles ------------------------------------
    @Property(str, notify=findChanged)
    def query(self) -> str:
        return self._query

    @query.setter
    def query(self, value: str) -> None:
        self._query = value

    @Property(str, notify=findChanged)
    def matchLabel(self) -> str:  # noqa: N802
        if not self.query:
            return ""
        return f"{self.match_index + 1} of {len(self.matches)}" if self.matches else "no matches"

    @Property(str, notify=filterChanged)
    def filterTag(self) -> str:  # noqa: N802
        return self.filter_tag or ""

    @Property(bool, notify=freezeChanged)
    def freeze(self) -> bool:
        return self._freeze

    @Property(str, notify=effectChanged)
    def effect(self) -> str:
        return self._effect

    @Property(bool, notify=editingChanged)
    def editing(self) -> bool:
        return self._editing

    # -- selection -----------------------------------------------------------------
    def current_cell(self) -> tuple[int, int]:
        return self._cur

    def selection_bounds(self) -> Box:
        """(top, left, bottom, right) of the selected block."""
        return self._box

    def _selected_count(self) -> int:
        top, left, bottom, right = self._box
        return (bottom - top + 1) * (right - left + 1)

    def _cells_in_box(self, box: Box | None = None) -> list[tuple[int, int]]:
        """Coordinates of the cells that hold something inside the selected block."""
        top, left, bottom, right = box or self._box
        return sorted(rc for rc in self.sheet.cells if top <= rc[0] <= bottom and left <= rc[1] <= right)

    def _clamp(self, row: int, col: int) -> tuple[int, int]:
        return (max(0, min(self.model.rowCount() - 1, row)), max(0, min(self.model.columnCount() - 1, col)))

    def _set_selection(self, cur: tuple[int, int], box: Box, anchor: tuple[int, int] | None = None) -> None:
        anchor = anchor if anchor is not None else self._anchor
        if (cur, box, anchor) == (self._cur, self._box, self._anchor):
            return
        self._cur, self._box, self._anchor = cur, box, anchor
        self._last_cell[self.current] = cur
        self.selectionChanged.emit()
        self.update_status()

    def select_cell(self, row: int, col: int, scroll: bool = True) -> None:
        row, col = self._clamp(row, col)
        self._set_selection((row, col), (row, col, row, col), (row, col))
        if scroll:
            self.scrollRequested.emit(row, col, False)

    def select_range(self, top: int, left: int, bottom: int, right: int, scroll: bool = True) -> None:
        top, left = self._clamp(min(top, bottom), min(left, right))
        bottom, right = self._clamp(max(top, bottom), max(left, right))
        self._set_selection((top, left), (top, left, bottom, right), (top, left))
        if scroll:
            self.scrollRequested.emit(top, left, False)

    def _extend_to(self, row: int, col: int, scroll: bool = True) -> None:
        """Move the cursor and select the block from the anchor to it (Shift+move, drag)."""
        row, col = self._clamp(row, col)
        ar, ac = self._anchor
        self._set_selection((row, col), (min(ar, row), min(ac, col), max(ar, row), max(ac, col)))
        if scroll:
            self.scrollRequested.emit(row, col, False)

    @Slot()
    def selectAll(self) -> None:  # noqa: N802
        self._set_selection(self._cur, (0, 0, self.model.rowCount() - 1, self.model.columnCount() - 1))

    @Slot(int, int)
    def moveBy(self, d_row: int, d_col: int) -> None:  # noqa: N802
        row, col = self._cur
        self.select_cell(row + d_row, col + d_col)

    @Slot(int, int)
    def extendBy(self, d_row: int, d_col: int) -> None:  # noqa: N802
        row, col = self._cur
        self._extend_to(row + d_row, col + d_col)

    @Slot(bool)
    def tabMove(self, forward: bool) -> None:  # noqa: N802
        """Tab / Shift+Tab: next / previous cell in the row; stops at the edges, like Excel."""
        self.moveBy(0, 1 if forward else -1)

    @Slot(bool, bool)
    def homeEnd(self, to_end: bool, extend: bool) -> None:  # noqa: N802
        row = self._cur[0]
        col = self.model.columnCount() - 1 if to_end else 0
        if extend:
            self._extend_to(row, col)
        else:
            self.select_cell(row, col)

    @Slot()
    def ctrlHome(self) -> None:  # noqa: N802
        self.select_cell(0, 0)

    @Slot()
    def ctrlEnd(self) -> None:  # noqa: N802
        max_r, max_c = self.sheet.used_extent()
        self.select_cell(max(max_r, 0), max(max_c, 0), scroll=False)
        self.scrollRequested.emit(max(max_r, 0), max(max_c, 0), True)

    @Slot(int, int, bool)
    def pressCell(self, row: int, col: int, extend: bool) -> None:  # noqa: N802
        if extend:
            self._extend_to(row, col)
        else:
            self.select_cell(row, col)

    @Slot(int, int)
    def dragTo(self, row: int, col: int) -> None:  # noqa: N802
        self._extend_to(row, col, scroll=False)

    @Slot(int, int, int)
    def selectRows(self, from_row: int, to_row: int, col: int) -> None:  # noqa: N802
        """Header click / drag: whole rows, the cursor in `col` (the leftmost visible column)."""
        from_row, col = self._clamp(from_row, col)
        to_row, _ = self._clamp(to_row, col)
        box = (min(from_row, to_row), 0, max(from_row, to_row), self.model.columnCount() - 1)
        self._set_selection((to_row, col), box, (from_row, 0))

    @Slot(int, int, int)
    def selectCols(self, from_col: int, to_col: int, row: int) -> None:  # noqa: N802
        row, from_col = self._clamp(row, from_col)
        _, to_col = self._clamp(row, to_col)
        box = (0, min(from_col, to_col), self.model.rowCount() - 1, max(from_col, to_col))
        self._set_selection((row, to_col), box, (0, from_col))

    @Slot()
    def selectAllLadder(self) -> None:  # noqa: N802
        """Ctrl+A, Excel's ladder: the data island around you → the filled range → the whole grid."""
        sheet = self.sheet
        max_r, max_c = sheet.used_extent()
        if max_r < 0:
            self.selectAll()
            return
        used = (0, 0, max_r, max_c)
        row, col = self._cur
        region = current_region(sheet, row, col)

        def area(box: Box) -> int:
            return (box[2] - box[0] + 1) * (box[3] - box[1] + 1)

        region_has_data = not (area(region) == 1 and sheet.get(row, col) is None)
        if region_has_data and region != used and self._box != region and self._box != used:
            self.select_range(*region, scroll=False)
            self.scrollRequested.emit(region[2], region[3], True)
        elif self._box != used:
            self.select_range(0, 0, max_r, max_c, scroll=False)
            self.scrollRequested.emit(max_r, max_c, True)
        else:
            self.selectAll()

    def _jump_target(self, direction: str) -> tuple[int, int]:
        row, col = self._cur
        sheet = self.sheet
        max_r, max_c = sheet.used_extent()
        if direction == "down":
            rows = [r for (r, c) in sheet.cells if c == col and r > row]
            return (max(rows) if rows else max(max_r, row), col)
        if direction == "up":
            rows = [r for (r, c) in sheet.cells if c == col and r < row]
            return (min(rows) if rows else 0, col)
        if direction == "right":
            cols = [c for (r, c) in sheet.cells if r == row and c > col]
            return (row, max(cols) if cols else max(max_c, col))
        cols = [c for (r, c) in sheet.cells if r == row and c < col]
        return (row, min(cols) if cols else 0)

    @Slot(str)
    def jump(self, direction: str) -> None:
        """Ctrl+arrow: fly to the edge of the data in that direction."""
        target = self._jump_target(direction)
        self.select_cell(*target, scroll=False)
        self.scrollRequested.emit(*self._cur, True)

    @Slot(str)
    def jumpExtend(self, direction: str) -> None:  # noqa: N802
        """Ctrl+Shift+arrow: select from the current selection out to the data edge."""
        target = self._clamp(*self._jump_target(direction))
        top, left, bottom, right = self._box
        box = (min(top, target[0]), min(left, target[1]), max(bottom, target[0]), max(right, target[1]))
        self._set_selection(target, box)
        self.scrollRequested.emit(*target, True)

    # -- in-cell editing -----------------------------------------------------------
    @Slot(int, int, result=str)
    def cellText(self, row: int, col: int) -> str:  # noqa: N802
        cell = self.sheet.get(row, col)
        return cell.text if cell else ""

    @Slot(bool)
    def setEditing(self, on: bool) -> None:  # noqa: N802
        if on != self._editing:
            self._editing = on
            self.editingChanged.emit()
            self.update_status()

    @Slot(int, int, str, int, int)
    def commitEdit(self, row: int, col: int, text: str, d_row: int, d_col: int) -> None:  # noqa: N802
        self.setEditing(False)
        before = self._snapshot({(row, col)})
        self.sheet.set_text(row, col, text)
        self._push_history(before, self._snapshot({(row, col)}))
        self.after_change(row, col)
        if d_row or d_col:
            self.select_cell(row + d_row, col + d_col)  # from the edited cell, wherever the cursor is
        self.update_status()

    @Slot()
    def cancelEdit(self) -> None:  # noqa: N802
        self.setEditing(False)
        self.focusGridRequested.emit()

    @Slot()
    def clearCells(self) -> None:  # noqa: N802
        touched = self._cells_in_box()
        if not touched:
            return
        before = self._snapshot(set(touched))
        for row, col in touched:
            self.sheet.clear(row, col)
        self._push_history(before, self._snapshot(set(touched)))
        if len(touched) == 1:
            self.after_change(*touched[0])
        else:
            self.after_change()

    @Slot()
    def toggleBold(self) -> None:  # noqa: N802
        row, col = self._cur
        current = self.sheet.get(row, col)
        coords = self._cells_in_box()
        targets = [c for c in (self.sheet.get(*rc) for rc in coords) if c is not None and c.text]
        if not targets:
            return
        before = self._snapshot(set(coords))
        new_value = not (current.bold if current is not None and current.text else targets[0].bold)
        for cell in targets:
            cell.bold = new_value
        self._push_history(before, self._snapshot(set(coords)))
        if len(targets) == 1:
            self.after_change(row, col)
        else:
            self.after_change()

    @Slot()
    def toggleCheck(self) -> None:  # noqa: N802
        row, col = self._cur
        if self._selected_count() == 1:
            before = self._snapshot({(row, col)})
            cell = self.sheet.ensure(row, col)
            cell.check = NEXT_CHECK[cell.check]
            self.sheet.prune(row, col)
            self._push_history(before, self._snapshot({(row, col)}))
            self.after_change(row, col)
            return
        current = self.sheet.get(row, col)
        coords = self._cells_in_box()
        targets = [c for c in (self.sheet.get(*rc) for rc in coords) if c is not None and c.text]
        if not targets:
            return
        before = self._snapshot(set(coords))
        new_value = NEXT_CHECK[current.check if current is not None and current.text else targets[0].check]
        for cell in targets:
            cell.check = new_value
        self._push_history(before, self._snapshot(set(coords)))
        self.after_change()

    @Slot()
    def escape(self) -> None:
        if self.filter_tag is not None:
            self.setFilter("")
        elif self.query:
            self.closeFind()

    @Slot(int, int)
    def openLink(self, row: int, col: int) -> None:  # noqa: N802
        cell = self.sheet.get(row, col)
        if cell is not None and cell.is_link:
            QDesktopServices.openUrl(QUrl(cell.text.strip()))

    # -- clipboard -------------------------------------------------------------------
    def _selection_block(self) -> tuple[list[list[str]], int]:
        """The selected cells as rows of text (trimmed to the filled range), plus how many have text."""
        top, left, bottom, right = self._box
        max_r, max_c = self.sheet.used_extent()
        bottom, right = min(bottom, max(max_r, top)), min(right, max(max_c, left))
        block = []
        for r in range(top, bottom + 1):
            row_values = []
            for c in range(left, right + 1):
                cell = self.sheet.get(r, c)
                row_values.append(cell.text if cell else "")
            block.append(row_values)
        filled = sum(1 for row_values in block for v in row_values if v)
        return block, filled

    @Slot()
    def copy(self) -> None:
        block, filled = self._selection_block()
        if not filled:
            return
        single = len(block) == 1 and len(block[0]) == 1
        text = block[0][0] if single else join_block(block, self.copy_sep)
        self._clip = (text, block)
        QGuiApplication.clipboard().setText(text)
        self.flash_hint("Copied" if filled == 1 else f"Copied {filled} cells")

    @Slot()
    def cut(self) -> None:
        _block, filled = self._selection_block()
        if not filled:
            return
        self.copy()
        coords = set(self._cells_in_box())
        before = self._snapshot(coords)
        for row, col in coords:
            self.sheet.clear(row, col)
        self._push_history(before, self._snapshot(coords))
        self.after_change()
        self.flash_hint("Cut" if filled == 1 else f"Cut {filled} cells")

    @Slot(bool)
    def paste(self, spread: bool = True) -> None:
        text = QGuiApplication.clipboard().text()
        if not text.strip():
            return
        if not spread:
            block = [[text.strip("\r\n")]]
        elif self._clip is not None and self._clip[0] == text:
            block = self._clip[1]  # copied inside GridPad: keep the exact cells
        else:
            block = split_paste(text)
        top, left, bottom, right = self._box
        if len(block) == 1 and len(block[0]) == 1 and (bottom > top or right > left):
            # One value pasted into a selected range fills the range.
            block = [[block[0][0]] * (right - left + 1) for _ in range(bottom - top + 1)]
        rows = len(block)
        cols = max((len(r) for r in block), default=1)
        coords = {(top + r, left + c) for r in range(rows) for c in range(cols)
                  if top + r < MAX_ROWS and left + c < MAX_COLS}
        before = self._snapshot(coords)
        written = self.workbook.paste_block(self.current, top, left, block)
        self._push_history(before, self._snapshot(coords))
        self.after_change()
        self.select_range(top, left, top + rows - 1, left + cols - 1)
        if written:
            self.flash_hint(f"Pasted {written} cell" if written == 1 else f"Pasted {written} cells")

    # -- undo / redo -------------------------------------------------------------------
    def _snapshot(self, coords: set[tuple[int, int]]) -> dict[tuple[int, int], Cell | None]:
        return {rc: copy.deepcopy(self.sheet.cells.get(rc)) for rc in coords}

    def _push_history(self, before: dict, after: dict) -> None:
        if before == after:
            return
        self._undo_stack.append((self.current, before, after))
        if len(self._undo_stack) > 200:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _clear_history(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()

    @Slot()
    def undo(self) -> None:
        if not self._undo_stack:
            self.flash_hint("Nothing to undo")
            return
        entry = self._undo_stack.pop()
        self._redo_stack.append(entry)
        self._apply_state(entry[0], entry[1])
        self.flash_hint("Undone")

    @Slot()
    def redo(self) -> None:
        if not self._redo_stack:
            self.flash_hint("Nothing to redo")
            return
        entry = self._redo_stack.pop()
        self._undo_stack.append(entry)
        self._apply_state(entry[0], entry[2])
        self.flash_hint("Redone")

    def _apply_state(self, sheet_index: int, cells_state: dict) -> None:
        if sheet_index >= len(self.workbook.sheets):
            return
        if sheet_index != self.current:
            self.switchSheet(sheet_index)
        sheet = self.workbook.sheets[sheet_index]
        for rc, cell in cells_state.items():
            if cell is None:
                sheet.cells.pop(rc, None)
            else:
                sheet.cells[rc] = copy.deepcopy(cell)
        self.workbook.dirty = True
        self.after_change()
        if cells_state:
            rows = [r for r, _ in cells_state]
            cols = [c for _, c in cells_state]
            self.select_range(min(rows), min(cols), max(rows), max(cols))

    # -- sort and duplicates -----------------------------------------------------------
    def _sheet_op(self, fn):
        """Run a whole-sheet operation with undo support; returns whatever fn returns."""
        before_cells = {rc: copy.deepcopy(cell) for rc, cell in self.sheet.cells.items()}
        result = fn()
        coords = set(before_cells) | set(self.sheet.cells)
        before = {rc: before_cells.get(rc) for rc in coords}
        after = {rc: copy.deepcopy(self.sheet.cells.get(rc)) for rc in coords}
        self._push_history(before, after)
        self.workbook.dirty = True
        self.after_change()
        return result

    def _sort_box(self) -> Box | None:
        """Scope for the sort tools: a selected block if there is one, else the data island
        around the cursor (Excel's current region). None means the whole sheet."""
        if self._selected_count() > 1:
            return self._box
        row, col = self._cur
        region = current_region(self.sheet, row, col)
        max_r, max_c = self.sheet.used_extent()
        if max_r >= 0 and region == (0, 0, max_r, max_c):
            return None
        return region

    def _sort_scope(self) -> tuple[Box | None, bool]:
        box = self._sort_box()
        if box is not None and box[0] == box[2] and box[1] == box[3] and self.sheet.get(box[0], box[1]) is None:
            return box, False
        return box, True

    @staticmethod
    def _box_ref(box: Box) -> str:
        return f"{cell_ref(box[0], box[1])}:{cell_ref(box[2], box[3])}"

    @Slot(result="QVariantMap")
    def sortMenuInfo(self) -> dict:  # noqa: N802
        """Labels for the sort menu, or ok=false (and a hint) when the cursor sits outside any data."""
        self.commitEditRequested.emit()
        box, has_data = self._sort_scope()
        if not has_data:
            self.flash_hint("Click a cell inside your data first")
            return {"ok": False, "letter": "", "scope": ""}
        return {"ok": True, "letter": col_name(self._cur[1]), "scope": f" in {self._box_ref(box)}" if box else ""}

    @Slot(bool)
    def sortRows(self, reverse: bool) -> None:  # noqa: N802
        self.commitEditRequested.emit()
        box, has_data = self._sort_scope()
        if not has_data:
            self.flash_hint("Click a cell inside your data first")
            return
        col = self._cur[1]
        count = self._sheet_op(lambda: sort_rows(self.sheet, col, reverse, box))
        if box:
            self.select_range(*box)
            self.flash_hint(f"Sorted {self._box_ref(box)} by column {col_name(col)} · Ctrl+Z undoes")
        else:
            self.select_cell(0, col)
            self.flash_hint(f"Sorted {count} rows by column {col_name(col)} · Ctrl+Z undoes")

    @Slot()
    def groupDuplicates(self) -> None:  # noqa: N802
        self.commitEditRequested.emit()
        box, has_data = self._sort_scope()
        if not has_data:
            self.flash_hint("Click a cell inside your data first")
            return
        col = self._cur[1]
        dup_values, dup_rows = self._sheet_op(lambda: duplicates_first(self.sheet, col, box))
        top = box[0] if box else 0
        if dup_rows:
            self.select_range(top, col, top + dup_rows - 1, col)
            self.flash_hint(f"{dup_rows} rows share {dup_values} repeated values — moved to the top · Ctrl+Z undoes")
        else:
            self.flash_hint(f"No duplicates in column {col_name(col)}")

    @Slot()
    def dedupe(self) -> None:
        self.commitEditRequested.emit()
        box, has_data = self._sort_scope()
        if not has_data:
            self.flash_hint("Click a cell inside your data first")
            return
        col = self._cur[1]
        removed, values_hit = self._sheet_op(lambda: dedupe_rows(self.sheet, col, box))
        if removed:
            self.flash_hint(f"Deleted {removed} duplicate rows ({values_hit} repeated values) · Ctrl+Z undoes")
        else:
            self.flash_hint(f"No duplicates in column {col_name(col)}")

    # -- rows and columns ----------------------------------------------------------------
    @Slot(str, int)
    def rowAction(self, action: str, row: int) -> None:  # noqa: N802
        """Row header menu: above / below / up / down / delete."""
        self.commitEditRequested.emit()
        col = self._cur[1]
        if action == "above":
            self._sheet_op(lambda: insert_row(self.sheet, row))
            self.select_cell(row, col)
            self.flash_hint("Row inserted · Ctrl+Z undoes")
        elif action == "below":
            self._sheet_op(lambda: insert_row(self.sheet, row + 1))
            self.select_cell(row + 1, col)
            self.flash_hint("Row inserted · Ctrl+Z undoes")
        elif action == "up":
            new_row = self._sheet_op(lambda: move_row(self.sheet, row, -1))
            self.select_cell(new_row, col)
        elif action == "down":
            new_row = self._sheet_op(lambda: move_row(self.sheet, row, 1))
            self.select_cell(new_row, col)
        elif action == "delete":
            self._sheet_op(lambda: delete_row(self.sheet, row))
            self.select_cell(row, col)
            self.flash_hint(f"Row {row + 1} deleted · Ctrl+Z undoes")

    @Slot(str, int)
    def colAction(self, action: str, col: int) -> None:  # noqa: N802
        """Column header menu: left / right / moveLeft / moveRight / delete."""
        self.commitEditRequested.emit()
        row = self._cur[0]
        letter = col_name(col)
        if action == "left":
            self._sheet_op(lambda: insert_col(self.sheet, col))
            self.select_cell(row, col)
            self.flash_hint("Column inserted · Ctrl+Z undoes")
        elif action == "right":
            self._sheet_op(lambda: insert_col(self.sheet, col + 1))
            self.select_cell(row, col + 1)
            self.flash_hint("Column inserted · Ctrl+Z undoes")
        elif action == "moveLeft":
            new_col = self._sheet_op(lambda: move_col(self.sheet, col, -1))
            self.select_cell(row, new_col)
        elif action == "moveRight":
            new_col = self._sheet_op(lambda: move_col(self.sheet, col, 1))
            self.select_cell(row, new_col)
        elif action == "delete":
            self._sheet_op(lambda: delete_col(self.sheet, col))
            self.select_cell(row, col)
            self.flash_hint(f"Column {letter} deleted · Ctrl+Z undoes")

    @Slot(int, result=str)
    def colName(self, col: int) -> str:  # noqa: N802
        return col_name(col)

    # -- import ------------------------------------------------------------------------------
    @Property("QVariantList", constant=True)
    def importSeparators(self) -> list[str]:  # noqa: N802
        return [label for label, _ in IMPORT_SEPARATORS]

    @Slot(str)
    def beginImport(self, url_or_path: str) -> None:  # noqa: N802
        """Read a .csv/.txt file and ask QML to show the Import dialog for it."""
        self.commitEditRequested.emit()
        path = _local_path(url_or_path)
        try:
            raw = Path(path).read_bytes()
        except OSError as exc:
            self.alert.emit("Couldn't import", f"{path} couldn't be read.\n{exc}")
            return
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", errors="replace")
        self._import = (Path(path).name, text, Path(path).stem)
        self.importReady.emit(Path(path).name, cell_ref(*self._cur))

    @Slot(int, str, result="QVariantMap")
    def importPreview(self, sep_index: int, custom: str) -> dict:  # noqa: N802
        if self._import is None:
            return {"summary": "", "preview": "Nothing to import"}
        block = parse_delimited(self._import[1], _pick_sep(IMPORT_SEPARATORS, sep_index, custom))
        rows = len(block)
        cols = max((len(r) for r in block), default=0)
        lines = []
        for row in block[:3]:
            joined = " | ".join(row[:6])
            lines.append(joined if len(joined) <= 58 else joined[:57] + "…")
        return {"summary": f"{rows} rows × {cols} columns detected",
                "preview": "\n".join(lines) if lines else "Nothing to import"}

    @Slot(int, str, bool)
    def finishImport(self, sep_index: int, custom: str, to_new_sheet: bool) -> None:  # noqa: N802
        if self._import is None:
            return
        name, text, stem = self._import
        self._import = None
        block = parse_delimited(text, _pick_sep(IMPORT_SEPARATORS, sep_index, custom))
        if not block:
            self.flash_hint("Nothing to import")
            return
        row, col = self._cur
        if to_new_sheet:
            index = self.workbook.add_sheet(self.workbook.unique_sheet_name(stem or "Imported"))
            self.switchSheet(index)
            row, col = 0, 0
        rows = len(block)
        cols = max((len(r) for r in block), default=1)
        coords = {(row + r, col + c) for r in range(rows) for c in range(cols)
                  if row + r < MAX_ROWS and col + c < MAX_COLS}
        before = self._snapshot(coords)
        written = self.workbook.paste_block(self.current, row, col, block)
        self._push_history(before, self._snapshot(coords))
        self.after_change()
        self.select_range(row, col, row + rows - 1, col + cols - 1)
        self.flash_hint(f"Imported {written} cells from {name}")

    @Slot()
    def cancelImport(self) -> None:  # noqa: N802
        self._import = None
        self.focusGridRequested.emit()

    # -- replace -------------------------------------------------------------------------------
    @Slot(str, str, bool)
    def replaceAll(self, find: str, replacement: str, all_sheets: bool) -> None:  # noqa: N802
        self.commitEditRequested.emit()
        if not find:
            return
        indexes = range(len(self.workbook.sheets)) if all_sheets else [self.current]
        total_matches = 0
        total_cells = 0
        for index in indexes:
            sheet = self.workbook.sheets[index]
            before_cells = {rc: copy.deepcopy(cell) for rc, cell in sheet.cells.items()}
            matches, changed = replace_in_sheet(sheet, find, replacement)
            if not matches:
                continue
            coords = set(before_cells) | set(sheet.cells)
            before = {rc: before_cells.get(rc) for rc in coords}
            after = {rc: copy.deepcopy(sheet.cells.get(rc)) for rc in coords}
            self._undo_stack.append((index, before, after))
            if len(self._undo_stack) > 200:
                self._undo_stack.pop(0)
            total_matches += matches
            total_cells += changed
        if total_matches:
            self._redo_stack.clear()
            self.workbook.dirty = True
            self.after_change()
            self.flash_hint(f"Replaced {total_matches} matches in {total_cells} notes · Ctrl+Z undoes")
        else:
            self.flash_hint(f"“{find}” not found")

    @Slot()
    def toggleFreeze(self) -> None:  # noqa: N802
        self.setFreeze(not self._freeze)
        self.flash_hint("Row 1 pinned while scrolling" if self._freeze else "Row 1 unpinned")

    @Slot(bool)
    def setFreeze(self, on: bool) -> None:  # noqa: N802
        if bool(on) != self._freeze:
            self._freeze = bool(on)
            self.settings.setValue("freeze", self._freeze)
            self.freezeChanged.emit()

    # -- export ----------------------------------------------------------------------------------
    @Property("QVariantList", constant=True)
    def separatorLabels(self) -> list[str]:  # noqa: N802
        return [label for label, _ in SEPARATORS]

    @Property("QVariantList", constant=True)
    def separatorValues(self) -> list[str]:  # noqa: N802
        """What each preset row of separatorLabels stands for (the last row, Custom, has none)."""
        return [sep for _, sep in SEPARATORS if sep is not None]

    @Slot(result="QVariantMap")
    def separatorState(self) -> dict:  # noqa: N802
        """Where the separator dropdowns (Export, Appearance) start: {index, custom}."""
        return _sep_preset(SEPARATORS, self.copy_sep, " ---- ")

    @Slot(int, int, str, result=str)
    def exportPreview(self, sheet_index: int, sep_index: int, custom: str) -> str:  # noqa: N802
        if not (0 <= sheet_index < len(self.workbook.sheets)):
            return ""
        text = export_text(self.workbook.sheets[sheet_index], _pick_sep(SEPARATORS, sep_index, custom))
        lines = text.split("\n")[:3]
        shown = [line if len(line) <= 56 else line[:55] + "…" for line in lines]
        return "\n".join(shown) if any(shown) else "Nothing on this sheet yet"

    @Slot(int, int, str, result="QVariantMap")
    def exportTarget(self, sheet_index: int, sep_index: int, custom: str) -> dict:  # noqa: N802
        """Remember the separator, and tell QML where the Save dialog should start and which filters it offers."""
        self.commitEditRequested.emit()
        self.copy_sep = _pick_sep(SEPARATORS, sep_index, custom)
        self.settings.setValue("copy_sep", self.copy_sep)
        sheet = self.workbook.sheets[max(0, min(len(self.workbook.sheets) - 1, sheet_index))]
        suffix = ".csv" if self.copy_sep == "," else ".txt"
        folder = self.workbook.path.parent if self.workbook.path else Path.home()
        if suffix == ".csv":
            filters = ["CSV file (*.csv)", "Text file (*.txt)"]
        else:
            filters = ["Text file (*.txt)", "CSV file (*.csv)"]
        return {"file": QUrl.fromLocalFile(str(folder / (sheet.name + suffix))).toString(),
                "folder": QUrl.fromLocalFile(str(folder)).toString(), "filters": filters, "suffix": suffix}

    @Slot(int, str)
    def exportTo(self, sheet_index: int, url_or_path: str) -> None:  # noqa: N802
        path = _local_path(url_or_path)
        if not path:
            return
        suffix = ".csv" if self.copy_sep == "," else ".txt"
        if not path.lower().endswith((".csv", ".txt")):
            path += suffix
        sheet = self.workbook.sheets[max(0, min(len(self.workbook.sheets) - 1, sheet_index))]
        try:
            Path(path).write_text(export_text(sheet, self.copy_sep) + "\n", encoding="utf-8")
        except OSError as exc:
            self.alert.emit("Export failed", f"Couldn't write {path}.\n{exc}")
            return
        self.flash_hint(f"Exported {Path(path).name}")

    # -- tags and help ---------------------------------------------------------------------------
    @Slot(result="QVariantList")
    def tagMenu(self) -> list[dict]:  # noqa: N802
        """[{tag, count, checked}] most-used first, for the Ctrl+Shift+T menu."""
        counts = self.workbook.tag_counts()
        return [{"tag": tag, "count": counts[tag], "checked": tag == self.filter_tag}
                for tag in sorted(counts, key=lambda t: (-counts[t], t))]

    @Slot(str)
    def setFilter(self, tag: str) -> None:  # noqa: N802
        """Filter by a tag; the same tag again (or "") clears it."""
        tag = tag or None
        if tag == self.filter_tag:
            tag = None
        self.filter_tag = tag
        self.filterChanged.emit()  # the cells dim themselves from filterTag; no model refresh
        if tag is None:
            self.focusGridRequested.emit()
        self.update_status()

    @Property("QVariantList", constant=True)
    def helpKeys(self) -> list[list[str]]:  # noqa: N802
        return [[key, what] for key, what in KEYS]

    # -- appearance ------------------------------------------------------------------------------
    @Property("QVariantList", constant=True)
    def themeNames(self) -> list[str]:  # noqa: N802
        return list(theme.THEMES)

    @Slot(str, result="QVariantMap")
    def themeColors(self, name: str) -> dict:  # noqa: N802
        return dict(theme.THEMES.get(name, theme.THEMES[theme.DEFAULT_THEME]))

    @Property("QVariantList", constant=True)
    def effectList(self) -> list[list[str]]:  # noqa: N802
        return [[name, desc] for name, desc in EFFECTS]

    def _font_lists(self) -> tuple[list[str], list[str]]:
        if self._fonts is None:
            self._fonts = (mono_families(), ui_families())
        return self._fonts

    @Slot(result="QVariantList")
    def monoFamilies(self) -> list[str]:  # noqa: N802
        families = list(self._font_lists()[0])
        if theme.mono_family() not in families:
            families.insert(0, theme.mono_family())
        return families

    @Slot(result="QVariantList")
    def uiFamilies(self) -> list[str]:  # noqa: N802
        families = list(self._font_lists()[1])
        if theme.sans_family() not in families:
            families.insert(0, theme.sans_family())
        return families

    @Slot(result="QVariantMap")
    def settingsState(self) -> dict:  # noqa: N802
        self.commitEditRequested.emit()
        sep = self.separatorState()
        return {"theme": theme.current_theme(), "mono": theme.mono_family(), "sans": theme.sans_family(),
                "bold": theme.app_bold(), "effect": self._effect,
                "sepIndex": sep["index"], "custom": sep["custom"]}

    @Slot(str, str, str, bool, str, int, str)
    def applySettings(self, theme_name: str, mono: str, sans: str, bold: bool,  # noqa: N802
                      effect: str, sep_index: int, custom: str) -> None:
        """Appearance → Apply: stored in the same QSettings as the classic edition, applied live."""
        s = self.settings
        s.setValue("theme", theme_name)
        s.setValue("font_mono", mono)
        s.setValue("font_sans", sans)
        s.setValue("bold", bool(bold))
        s.setValue("effect", self._valid_effect(effect))
        self.copy_sep = _pick_sep(SEPARATORS, sep_index, custom)
        s.setValue("copy_sep", self.copy_sep)
        theme.load_appearance(s)
        self.palette.refresh()
        self._set_effect(effect)
        self.autofit_columns()
        self.update_status()

    def _set_effect(self, name: str) -> None:
        name = self._valid_effect(name)
        if name != self._effect:
            self._effect = name
            self.effectChanged.emit()

    # -- find --------------------------------------------------------------------------------------
    @Slot(str)
    def setQuery(self, text: str) -> None:  # noqa: N802
        self.query = text.strip()
        if not self.query:
            self.matches = []
            self.match_index = -1
            self._match_set = set()
            self._current_match = None
            self.findChanged.emit()
            self.model.refresh_roles(["match"])
            self.update_status()
            return
        self._recompute_matches(keep_position=False)
        if self.matches:
            self._show_match(select=True)
        else:
            self._sync_find_state()
        self.update_status()

    def _recompute_matches(self, keep_position: bool) -> None:
        previous = self.matches[self.match_index] if 0 <= self.match_index < len(self.matches) else None
        self.matches = self.workbook.find(self.query)
        self.match_index = -1
        if self.matches:
            if keep_position and previous is not None:
                for i, m in enumerate(self.matches):
                    if (m.sheet, m.row, m.col) == (previous.sheet, previous.row, previous.col):
                        self.match_index = i
                        break
            if self.match_index < 0:
                row, col = self._cur
                # first match on the current sheet at or after the cursor, else the first match anywhere
                for i, m in enumerate(self.matches):
                    if m.sheet == self.current and (m.row, m.col) >= (row, col):
                        self.match_index = i
                        break
                else:
                    for i, m in enumerate(self.matches):
                        if m.sheet == self.current:
                            self.match_index = i
                            break
                    else:
                        self.match_index = 0
        self._sync_find_state()

    def _sync_find_state(self) -> None:
        self._match_set = {(m.row, m.col) for m in self.matches if m.sheet == self.current}
        cur = self.matches[self.match_index] if 0 <= self.match_index < len(self.matches) else None
        self._current_match = (cur.row, cur.col) if cur is not None and cur.sheet == self.current else None
        self.model.refresh_roles(["match"])
        self.findChanged.emit()

    def _show_match(self, select: bool) -> None:
        if not (0 <= self.match_index < len(self.matches)):
            return
        m = self.matches[self.match_index]
        if m.sheet != self.current:
            self.switchSheet(m.sheet, True)
        if select:
            self.select_cell(m.row, m.col)
        self._sync_find_state()

    @Slot(int)
    def stepMatch(self, delta: int) -> None:  # noqa: N802
        if not self.matches:
            return
        self.match_index = (self.match_index + delta) % len(self.matches)
        self._show_match(select=True)
        self.update_status()

    @Slot()
    def closeFind(self) -> None:  # noqa: N802
        self.searchCleared.emit()
        self.setQuery("")
        self.focusGridRequested.emit()

    # -- sheets -----------------------------------------------------------------------------------
    @Slot(int)
    @Slot(int, bool)
    def switchSheet(self, index: int, keep_find: bool = False) -> None:  # noqa: N802
        if not (0 <= index < len(self.workbook.sheets)):
            return
        self.commitEditRequested.emit()
        self._last_cell[self.current] = self._cur
        self.current = index
        self.model.set_sheet(self.sheet)
        self.autofit_columns()
        row, col = self._last_cell.get(index, (0, 0))
        self._cur = (-1, -1)  # force a selection signal even when the coordinates repeat
        self.select_cell(row, col)
        self.sheetsChanged.emit()
        if self.query and not keep_find:
            self._sync_find_state()
        self.update_status()

    @Slot(int)
    def stepSheet(self, delta: int) -> None:  # noqa: N802
        self.switchSheet((self.current + delta) % len(self.workbook.sheets))

    @Slot()
    def addSheet(self) -> None:  # noqa: N802
        index = self.workbook.add_sheet()
        self.switchSheet(index)
        self.autosave()
        self.update_status()
        self.renameRequested.emit(index, self.workbook.sheets[index].name)

    @Slot(int)
    def requestRename(self, index: int) -> None:  # noqa: N802
        if 0 <= index < len(self.workbook.sheets):
            self.renameRequested.emit(index, self.workbook.sheets[index].name)

    @Slot(int, str)
    def renameSheet(self, index: int, name: str) -> None:  # noqa: N802
        if not (0 <= index < len(self.workbook.sheets)):
            return
        sheet = self.workbook.sheets[index]
        name = name.strip()
        if name and name != sheet.name:
            sheet.name = self.workbook.unique_sheet_name(name)
            self.workbook.dirty = True
            self.sheetsChanged.emit()
            self.after_change()
        self.focusGridRequested.emit()

    @Slot(int)
    def duplicateSheet(self, index: int) -> None:  # noqa: N802
        self._clear_history()  # sheet order changes would break saved undo positions
        new_index = self.workbook.duplicate_sheet(index)
        self.switchSheet(new_index)
        self.after_change()

    @Slot(int, int)
    def moveSheet(self, index: int, delta: int) -> None:  # noqa: N802
        self._clear_history()
        new_index = self.workbook.move_sheet(index, delta)
        if index == self.current:
            self.current = new_index
        elif new_index == self.current:
            self.current = index
        self.sheetsChanged.emit()
        self.after_change()

    @Slot(int, result=int)
    def sheetNoteCount(self, index: int) -> int:  # noqa: N802
        if 0 <= index < len(self.workbook.sheets):
            return self.workbook.sheets[index].note_count()
        return 0

    @Slot(int)
    def deleteSheet(self, index: int) -> None:  # noqa: N802
        """Delete without asking — QML confirms first when the sheet has notes."""
        if len(self.workbook.sheets) <= 1 or not (0 <= index < len(self.workbook.sheets)):
            return
        self.commitEditRequested.emit()
        self._clear_history()
        self.workbook.remove_sheet(index)
        self._last_cell = {(i if i < index else i - 1): rc for i, rc in self._last_cell.items() if i != index}
        self.current = min(self.current if index > self.current else max(0, self.current - 1),
                           len(self.workbook.sheets) - 1)
        self.model.set_sheet(self.sheet)
        row, col = self._last_cell.get(self.current, (0, 0))
        self._cur = (-1, -1)
        self.select_cell(row, col)
        self.sheetsChanged.emit()
        self.after_change()

    # -- files ------------------------------------------------------------------------------------
    def autosave(self) -> None:
        if self.workbook.path is not None:
            try:
                self.workbook.save()
            except OSError as exc:
                self.alert.emit("Save failed", f"Couldn't save {self.workbook.name}.\n{exc}")
        else:
            self.workbook.dirty = True

    @Slot(result=bool)
    def save(self) -> bool:
        """Ctrl+S. With no file yet it asks QML for the Save dialog and returns False."""
        self.commitEditRequested.emit()
        if self.workbook.path is None:
            self.saveAsRequested.emit()
            return False
        try:
            self.workbook.save()
        except OSError as exc:
            self.alert.emit("Save failed", f"Couldn't save {self.workbook.name}.\n{exc}")
            return False
        self.update_status()
        return True

    @Slot(result=str)
    def suggestedSavePath(self) -> str:  # noqa: N802
        path = self.workbook.path or (Path.home() / ("notes" + FILE_SUFFIX))
        return QUrl.fromLocalFile(str(path)).toString()

    @Slot(result=str)
    def startFolder(self) -> str:  # noqa: N802
        folder = self.workbook.path.parent if self.workbook.path else Path.home()
        return QUrl.fromLocalFile(str(folder)).toString()

    @Slot(str, result=bool)
    def saveTo(self, url_or_path: str) -> bool:  # noqa: N802
        path = _local_path(url_or_path)
        if not path:
            return False
        if not path.endswith(FILE_SUFFIX):
            path += FILE_SUFFIX
        try:
            self.workbook.save(path)
        except OSError as exc:
            self.alert.emit("Save failed", f"Couldn't save to {path}.\n{exc}")
            return False
        self.settings.setValue("last_file", path)
        self.refresh_all()
        return True

    @Slot(result=bool)
    def needsDiscardConfirm(self) -> bool:  # noqa: N802
        """True when dropping the workbook would lose notes (never saved and not empty)."""
        return self.workbook.path is None and self.workbook.total_notes() > 0

    @Slot(str)
    def openPath(self, url_or_path: str) -> None:  # noqa: N802
        """Open a workbook (QML has already confirmed discarding the current one)."""
        path = _local_path(url_or_path)
        if not path:
            return
        try:
            workbook = Workbook.load(path)
        except (OSError, ValueError) as exc:
            self.alert.emit("Couldn't open", f"{path} isn't a readable GridPad file.\n{exc}")
            return
        self.load_workbook(workbook)
        self.settings.setValue("last_file", str(path))

    @Slot()
    def newWorkbook(self) -> None:  # noqa: N802
        self.load_workbook(Workbook())
        self.settings.remove("last_file")

    def load_workbook(self, workbook: Workbook) -> None:
        self.cancelEditRequested.emit()
        self._clear_history()
        self.workbook = workbook
        self.current = 0
        self._last_cell = {}
        self.matches = []
        self.match_index = -1
        self.query = ""
        self._match_set = set()
        self._current_match = None
        self.filter_tag = None
        self.searchCleared.emit()
        self.findChanged.emit()
        self.filterChanged.emit()
        self.model.set_sheet(self.sheet)
        self._cur = (-1, -1)
        self.select_cell(0, 0)
        self.refresh_all()
        self.focusGridRequested.emit()

    @Slot("QVariantList", result="QVariantMap")
    def classifyDrop(self, urls: list) -> dict:  # noqa: N802
        """What a dropped file means: {kind: "open"|"import"|"", path}."""
        for url in urls:
            path = _local_path(url.toString() if isinstance(url, QUrl) else str(url))
            lower = path.lower()
            if lower.endswith(FILE_SUFFIX):
                return {"kind": "open", "path": path}
            if lower.endswith((".csv", ".txt")):
                return {"kind": "import", "path": path}
        return {"kind": "", "path": ""}

    @Slot(result="QVariantList")
    def windowGeometry(self) -> list:  # noqa: N802
        """[x, y, width, height, maximized] from the last run, or [] the first time."""
        value = self.settings.value("qml_geometry")
        if not value:
            return []
        try:
            x, y, w, h, maximized = (int(v) for v in str(value).split(","))
        except ValueError:
            return []
        return [x, y, w, h, bool(maximized)]

    @Slot(int, int, int, int, bool)
    def saveWindowGeometry(self, x: int, y: int, w: int, h: int, maximized: bool) -> None:  # noqa: N802
        self.settings.setValue("qml_geometry", f"{x},{y},{w},{h},{int(maximized)}")

    @Slot()
    def shutdown(self) -> None:
        """The window is closing for good: remember the file for next launch."""
        if self.workbook.path is not None:
            self.settings.setValue("last_file", str(self.workbook.path))
        self.settings.sync()
