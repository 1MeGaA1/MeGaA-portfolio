"""Main window: top bar, grid, sheet bar — and the behaviour that ties them together."""
from __future__ import annotations

import copy
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QSettings, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QCursor, QDesktopServices, QFontMetrics, QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedLayout,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import icons, theme
from .effects import EffectCanvas
from .export import ExportDialog
from .grid import COL_WIDTH, MAX_COL_WIDTH, MIN_COL_WIDTH, GridModel, GridView, ViewState
from .help import HelpDialog
from .importer import ImportDialog
from .model import (
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
    duplicates_first,
    insert_col,
    insert_row,
    join_block,
    move_col,
    move_row,
    replace_in_sheet,
    sort_rows,
    split_paste,
)
from .replace import ReplaceDialog
from .settings import SettingsDialog

HINT_NORMAL = "Tab next · Enter edit · Ctrl+F find · F1 keys"
HINT_EDIT = "Enter saves · Shift+Enter new line · Esc cancels"
HINT_RANGE = "Ctrl+C copy · Ctrl+X cut · Delete clears · Ctrl+V pastes at the top-left"
NEXT_CHECK = {None: "todo", "todo": "done", "done": None}


# --------------------------------------------------------------------------- top bar
class SearchInput(QLineEdit):
    next_requested = Signal()
    prev_requested = Signal()
    close_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.prev_requested.emit()
            else:
                self.next_requested.emit()
            return
        if key == Qt.Key.Key_Escape:
            self.close_requested.emit()
            return
        super().keyPressEvent(event)


class SearchBox(QFrame):
    query_changed = Signal(str)
    next_requested = Signal()
    prev_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("searchbox")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(300, 30)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 6, 0)
        lay.setSpacing(6)
        self.icon = QLabel()
        self.icon.setPixmap(icons.pixmap("search", theme.MUTED, 15))
        lay.addWidget(self.icon)
        self.input = SearchInput()
        self.input.setObjectName("searchinput")
        self.input.setFont(theme.chrome(12))
        self.input.setPlaceholderText("Find in all sheets")
        self.input.setFrame(False)
        self.input.textChanged.connect(self._on_text)
        self.input.next_requested.connect(self.next_requested)
        self.input.prev_requested.connect(self.prev_requested)
        self.input.close_requested.connect(self.close_requested)
        self.input.installEventFilter(self)
        lay.addWidget(self.input, 1)
        self.hint = QLabel("Ctrl+F")
        self.hint.setFont(theme.chrome(12))
        self.hint.setStyleSheet(f"color: {theme.MUTED};")
        lay.addWidget(self.hint)
        self.count = QLabel("")
        self.count.setFont(theme.chrome(12))
        self.count.setStyleSheet(f"color: {theme.MUTED};")
        lay.addWidget(self.count)
        self.up = self._button("chevron-up", "Previous match (Shift+Enter)")
        self.down = self._button("chevron-down", "Next match (Enter)")
        self.close = self._button("x", "Close find (Esc)")
        self.up.clicked.connect(self.prev_requested)
        self.down.clicked.connect(self.next_requested)
        self.close.clicked.connect(self.close_requested)
        for btn in (self.up, self.down, self.close):
            lay.addWidget(btn)
        self._show_controls(False)

    def _button(self, name: str, tip: str) -> QToolButton:
        btn = QToolButton()
        btn.setIcon(icons.icon(name, theme.ICON, 14))
        btn.setIconSize(QSize(14, 14))
        btn.setFixedSize(22, 22)
        btn.setToolTip(tip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return btn

    def _show_controls(self, on: bool) -> None:
        self.hint.setVisible(not on)
        for w in (self.count, self.up, self.down, self.close):
            w.setVisible(on)

    def _on_text(self, text: str) -> None:
        self._show_controls(bool(text))
        self._refresh_active()
        self.query_changed.emit(text)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self.input and event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self._refresh_active()
        return super().eventFilter(obj, event)

    def _refresh_active(self) -> None:
        active = "true" if (self.input.hasFocus() or self.input.text()) else "false"
        if self.property("active") != active:
            self.setProperty("active", active)
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()

    # public
    def text(self) -> str:
        return self.input.text()

    def focus(self) -> None:
        self.input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.input.selectAll()

    def clear(self) -> None:
        self.input.clear()

    def set_count(self, current: int, total: int) -> None:
        self.count.setText(f"{current} of {total}" if total else "no matches")


class TopBar(QFrame):
    filter_clear_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("topbar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(44)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(14)
        logo = QLabel()
        logo.setPixmap(icons.pixmap("grid", theme.ACCENT, 18))
        lay.addWidget(logo)
        title = QLabel("GridPad")
        title.setFont(theme.sans(15, bold=True))
        lay.addWidget(title)
        self.file_label = QLabel("untitled" + FILE_SUFFIX)
        self.file_label.setFont(theme.chrome(12))
        self.file_label.setStyleSheet(f"color: {theme.MUTED};")
        lay.addWidget(self.file_label)
        lay.addStretch(1)
        self.filter_chip = QPushButton("Filter: #tag")
        self.filter_chip.setObjectName("chip")
        self.filter_chip.setFont(theme.mono(12))
        self.filter_chip.setIcon(icons.icon("x", theme.TAG, 14))
        self.filter_chip.setIconSize(QSize(14, 14))
        self.filter_chip.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.filter_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_chip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.filter_chip.setToolTip("Clear the tag filter (Esc)")
        self.filter_chip.clicked.connect(self.filter_clear_requested)
        self.filter_chip.hide()
        lay.addWidget(self.filter_chip)
        self.sort_btn = QToolButton()
        self.sort_btn.setIcon(icons.icon("sort", theme.ICON, 16))
        self.sort_btn.setIconSize(QSize(16, 16))
        self.sort_btn.setText("Check duplicates and sort")
        self.sort_btn.setFont(theme.chrome(12))
        self.sort_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.sort_btn.setFixedHeight(28)
        self.sort_btn.setToolTip("Sort rows, or group duplicate values on top (uses the selected column)")
        self.sort_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sort_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lay.addWidget(self.sort_btn)
        self.import_btn = QToolButton()
        self.import_btn.setIcon(icons.icon("upload", theme.ICON, 16))
        self.import_btn.setIconSize(QSize(16, 16))
        self.import_btn.setFixedSize(28, 28)
        self.import_btn.setToolTip("Import CSV or text (Ctrl+I) — or drop a file on the window")
        self.import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lay.addWidget(self.import_btn)
        self.export_btn = QToolButton()
        self.export_btn.setIcon(icons.icon("download", theme.ICON, 16))
        self.export_btn.setIconSize(QSize(16, 16))
        self.export_btn.setFixedSize(28, 28)
        self.export_btn.setToolTip("Export sheet as CSV or text (Ctrl+E)")
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lay.addWidget(self.export_btn)
        self.settings_btn = QToolButton()
        self.settings_btn.setIcon(icons.icon("gear", theme.ICON, 16))
        self.settings_btn.setIconSize(QSize(16, 16))
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setToolTip("Theme and font (Ctrl+,)")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lay.addWidget(self.settings_btn)
        self.search = SearchBox()
        lay.addWidget(self.search)

    def set_file_name(self, name: str) -> None:
        self.file_label.setText(name)

    def set_filter(self, tag: str | None) -> None:
        if tag is None:
            self.filter_chip.hide()
        else:
            self.filter_chip.setText(f"Filter: #{tag}")
            self.filter_chip.show()


# --------------------------------------------------------------------------- sheet bar
class SheetBar(QFrame):
    sheet_selected = Signal(int)
    add_requested = Signal()
    rename_requested = Signal(int)
    duplicate_requested = Signal(int)
    move_requested = Signal(int, int)
    delete_requested = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sheetbar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(32)
        self._buttons: list[QToolButton] = []
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(0)
        self.tabs = QHBoxLayout()
        self.tabs.setContentsMargins(0, 0, 0, 0)
        self.tabs.setSpacing(0)
        lay.addLayout(self.tabs)
        self.add_btn = QToolButton()
        self.add_btn.setIcon(icons.icon("plus", theme.MUTED, 14))
        self.add_btn.setIconSize(QSize(14, 14))
        self.add_btn.setFixedSize(24, 24)
        self.add_btn.setToolTip("New sheet (Ctrl+T)")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.add_btn.clicked.connect(self.add_requested)
        lay.addSpacing(4)
        lay.addWidget(self.add_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addStretch(1)
        self.notes_label = self._status_label()
        self.hint_label = self._status_label()
        self.saved_label = self._status_label()
        lay.addWidget(self.notes_label)
        lay.addSpacing(18)
        lay.addWidget(self.hint_label)
        lay.addSpacing(18)
        lay.addWidget(self.saved_label)

    @staticmethod
    def _status_label() -> QLabel:
        lab = QLabel("")
        lab.setFont(theme.chrome(11))
        lab.setStyleSheet(f"color: {theme.MUTED};")
        return lab

    def set_sheets(self, names: list[str], current: int) -> None:
        while self.tabs.count():
            item = self.tabs.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._buttons = []
        for i, name in enumerate(names):
            btn = QToolButton()
            btn.setObjectName("sheettab")
            btn.setText(name)
            btn.setFont(theme.sans(13, bold=(i == current)))
            btn.setCheckable(True)
            btn.setChecked(i == current)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, i=i, b=btn: self._menu(i, b.mapToGlobal(pos)))
            btn.clicked.connect(lambda _=False, i=i: self.sheet_selected.emit(i))
            btn.installEventFilter(self)
            btn.setProperty("sheet_index", i)
            self.tabs.addWidget(btn)
            self._buttons.append(btn)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.MouseButtonDblClick and isinstance(obj, QToolButton):
            index = obj.property("sheet_index")
            if index is not None:
                self.rename_requested.emit(int(index))
                return True
        return super().eventFilter(obj, event)

    def _menu(self, index: int, global_pos) -> None:
        menu = QMenu(self)
        menu.setFont(theme.sans(13))
        rename = menu.addAction("Rename sheet")
        rename.setShortcut(QKeySequence("F2"))
        duplicate = menu.addAction("Duplicate sheet")
        left = menu.addAction("Move left")
        right = menu.addAction("Move right")
        left.setEnabled(index > 0)
        right.setEnabled(index < len(self._buttons) - 1)
        menu.addSeparator()
        delete = menu.addAction("Delete sheet")
        delete.setEnabled(len(self._buttons) > 1)
        chosen = menu.exec(global_pos)
        if chosen is rename:
            self.rename_requested.emit(index)
        elif chosen is duplicate:
            self.duplicate_requested.emit(index)
        elif chosen is left:
            self.move_requested.emit(index, -1)
        elif chosen is right:
            self.move_requested.emit(index, 1)
        elif chosen is delete:
            self.delete_requested.emit(index)

    def set_status(self, notes: str, hint: str, saved: str) -> None:
        self.notes_label.setText(notes)
        self.hint_label.setText(hint)
        self.saved_label.setText(saved)


# --------------------------------------------------------------------------- main window
class MainWindow(QMainWindow):
    def __init__(self, workbook: Workbook, settings: QSettings | None = None) -> None:
        super().__init__()
        self.settings = settings or QSettings("GridPad", "GridPad")
        self.workbook = workbook
        self.current = 0
        self.state = ViewState()
        self.matches: list[Match] = []
        self.match_index = -1
        self._last_cell: dict[int, tuple[int, int]] = {}
        self._clip: tuple[str, list[list[str]]] | None = None  # last in-app copy: (clipboard text, cells)
        self.copy_sep = str(self.settings.value("copy_sep", "\t"))  # column separator for copied blocks
        self._undo_stack: list[tuple[int, dict, dict]] = []  # (sheet index, cells before, cells after)
        self._redo_stack: list[tuple[int, dict, dict]] = []

        self.setWindowTitle("GridPad")
        self.resize(1280, 800)
        self.setMinimumSize(900, 560)

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.topbar = TopBar()
        outer.addWidget(self.topbar)

        self.model = GridModel(self.sheet)
        self.grid = GridView(self.model, self.state)
        center = QWidget()
        center_stack = QStackedLayout(center)
        center_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        center_stack.addWidget(self.grid)
        self.effects = EffectCanvas()
        center_stack.addWidget(self.effects)
        center_stack.setCurrentWidget(self.grid)
        outer.addWidget(center, 1)
        self.effects.set_effect(str(self.settings.value("effect", "None")))
        self.grid.set_frozen(str(self.settings.value("freeze", "true")).lower() in ("true", "1"))
        self.setAcceptDrops(True)

        self.sheetbar = SheetBar()
        outer.addWidget(self.sheetbar)

        self._connect()
        self._shortcuts()
        self._restore_geometry()
        self.refresh_all()
        self.grid.setFocus()

    # -- wiring -----------------------------------------------------------------
    def _connect(self) -> None:
        self.grid.current_cell_changed.connect(self.on_cell_changed)
        self.grid.edit_requested.connect(self.on_edit_requested)
        self.grid.clear_requested.connect(self.clear_cell)
        self.grid.escape_pressed.connect(self.on_escape)
        self.grid.link_activated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        self.grid.copy_requested.connect(self.copy_cell)
        self.grid.cut_requested.connect(self.cut_cell)
        self.grid.paste_requested.connect(self.paste)
        self.grid.selection_changed.connect(self.update_status)

        self.grid.edit_committed.connect(self.on_commit)
        self.grid.edit_cancelled.connect(self.on_cancel)
        self.grid.tag_clicked.connect(self.set_filter)

        search = self.topbar.search
        search.query_changed.connect(self.on_query_changed)
        search.next_requested.connect(lambda: self.step_match(1))
        search.prev_requested.connect(lambda: self.step_match(-1))
        search.close_requested.connect(self.close_find)
        self.topbar.filter_clear_requested.connect(lambda: self.set_filter(None))
        self.topbar.sort_btn.clicked.connect(self.sort_menu)
        self.topbar.import_btn.clicked.connect(lambda: self.import_file())
        self.topbar.export_btn.clicked.connect(self.export_sheet)
        self.topbar.settings_btn.clicked.connect(self.show_settings)
        row_header = self.grid.verticalHeader()
        row_header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        row_header.customContextMenuRequested.connect(self._row_header_menu)
        col_header = self.grid.horizontalHeader()
        col_header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        col_header.customContextMenuRequested.connect(self._col_header_menu)

        bar = self.sheetbar
        bar.sheet_selected.connect(self.switch_sheet)
        bar.add_requested.connect(self.add_sheet)
        bar.rename_requested.connect(self.rename_sheet)
        bar.duplicate_requested.connect(self.duplicate_sheet)
        bar.move_requested.connect(self.move_sheet)
        bar.delete_requested.connect(self.delete_sheet)

    def _shortcuts(self) -> None:
        def add(seq: str, fn, context=Qt.ShortcutContext.WindowShortcut) -> None:
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(context)
            sc.activated.connect(fn)

        add("Ctrl+F", self.topbar.search.focus)
        add("Ctrl+S", self.save)
        add("Ctrl+Shift+S", self.save_as)
        add("Ctrl+O", self.open_file)
        add("Ctrl+N", self.new_workbook)
        add("Ctrl+B", self.toggle_bold)
        add("Ctrl+K", self.toggle_check)
        add("Ctrl+L", self.grid.toggle_bullet)
        add("Ctrl+E", self.export_sheet)
        add("Ctrl+Shift+T", self.tag_menu)
        add("F1", self.show_help)
        add("Ctrl+,", self.show_settings)
        add("Ctrl+Z", self.undo)
        add("Ctrl+Y", self.redo)
        add("Ctrl+Shift+Z", self.redo)
        add("Ctrl+I", lambda: self.import_file())
        add("Ctrl+H", self.replace_dialog)
        add("F8", self.toggle_freeze)
        add("Ctrl+T", self.add_sheet)
        add("Ctrl+PgDown", lambda: self.switch_sheet((self.current + 1) % len(self.workbook.sheets)))
        add("Ctrl+PgUp", lambda: self.switch_sheet((self.current - 1) % len(self.workbook.sheets)))
        add("Ctrl+Tab", lambda: self.switch_sheet((self.current + 1) % len(self.workbook.sheets)))
        add("Ctrl+Shift+Tab", lambda: self.switch_sheet((self.current - 1) % len(self.workbook.sheets)))

    # -- helpers ----------------------------------------------------------------
    @property
    def sheet(self):
        return self.workbook.sheets[self.current]

    def _restore_geometry(self) -> None:
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)

    def refresh_all(self) -> None:
        self.topbar.set_file_name(self.workbook.name)
        self.setWindowTitle(f"{self.workbook.name} — GridPad")
        self.sheetbar.set_sheets([s.name for s in self.workbook.sheets], self.current)
        self.refresh_tags()
        self.autofit_columns()
        self.update_status()

    def refresh_tags(self) -> None:
        counts = self.workbook.tag_counts()
        tag = self.state.filter_tag
        if tag is not None and tag not in counts:
            self.state.filter_tag = None
            self.topbar.set_filter(None)
            self.model.refresh()

    def _filtered_count(self) -> int:
        tag = self.state.filter_tag
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
        for col in range(self.model.columnCount()):
            target = max(MIN_COL_WIDTH, min(MAX_COL_WIDTH, needed.get(col, COL_WIDTH)))
            if self.grid.columnWidth(col) != target:
                self.grid.setColumnWidth(col, target)
        self.grid.sync_frozen()

    def update_status(self) -> None:
        total = self.workbook.total_notes()
        dup_cells = len(self.model.dups)
        dup_suffix = f" · {dup_cells} duplicates" if dup_cells else ""
        if self.state.filter_tag:
            notes = f"{self._filtered_count()} of {total} notes"
            hint = f"Filter: #{self.state.filter_tag} · Esc clears"
        elif self.state.query:
            n = len(self.matches)
            pos = self.match_index + 1 if n else 0
            notes = f"{total} notes"
            hint = f"Find: {self.state.query} · {pos} of {n} · Enter next · Esc closes"
        elif self.grid.editing:
            notes = f"{total} notes"
            hint = HINT_EDIT
        elif len(self.grid.selected_cells()) > 1:
            notes = f"{len(self.grid.selected_cells())} cells selected"
            hint = HINT_RANGE
        else:
            notes = (f"{total} note" if total == 1 else f"{total} notes") + dup_suffix
            hint = HINT_NORMAL
        if self.workbook.path is None:
            saved = "Unsaved · Ctrl+S" if total else "Unsaved"
        else:
            saved = "Saved" if not self.workbook.dirty else "Saving"
        self.sheetbar.set_status(notes, hint, saved)

    def after_change(self, row: int | None = None, col: int | None = None) -> None:
        """A cell or sheet changed: repaint, re-run find, autosave, refresh the status."""
        if row is not None and col is not None:
            self.model.cell_changed(row, col)
        else:
            self.model.refresh()
        if self.state.query:
            self._recompute_matches(keep_position=True)
        self.autosave()
        self.refresh_tags()
        self.autofit_columns()
        self.update_status()

    # -- cell editing -------------------------------------------------------------
    def on_cell_changed(self, row: int, col: int) -> None:
        self._last_cell[self.current] = (row, col)
        self.update_status()

    def on_edit_requested(self, initial: str | None) -> None:
        self.grid.begin_cell_edit(initial)
        self.update_status()

    def on_commit(self, row: int, col: int, text: str, d_row: int, d_col: int) -> None:
        before = self._snapshot({(row, col)})
        self.sheet.set_text(row, col, text)
        self._push_history(before, self._snapshot({(row, col)}))
        self.after_change(row, col)
        if d_row or d_col:
            self.grid.move_by(d_row, d_col)
        self.update_status()

    def on_cancel(self) -> None:
        self.grid.setFocus()
        self.update_status()

    def clear_cell(self) -> None:
        touched = [rc for rc in self.grid.selected_cells() if self.sheet.get(*rc) is not None]
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

    def toggle_bold(self) -> None:
        row, col = self.grid.current_cell()
        current = self.sheet.get(row, col)
        targets = [c for c in (self.sheet.get(*rc) for rc in self.grid.selected_cells()) if c is not None and c.text]
        if not targets:
            return
        coords = set(self.grid.selected_cells())
        before = self._snapshot(coords)
        new_value = not (current.bold if current is not None and current.text else targets[0].bold)
        for cell in targets:
            cell.bold = new_value
        self._push_history(before, self._snapshot(coords))
        if len(targets) == 1:
            self.after_change(row, col)
        else:
            self.after_change()

    def toggle_check(self) -> None:
        row, col = self.grid.current_cell()
        selected = self.grid.selected_cells()
        if len(selected) == 1:
            before = self._snapshot({(row, col)})
            cell = self.sheet.ensure(row, col)
            cell.check = NEXT_CHECK[cell.check]
            self.sheet.prune(row, col)
            self._push_history(before, self._snapshot({(row, col)}))
            self.after_change(row, col)
            return
        current = self.sheet.get(row, col)
        targets = [c for c in (self.sheet.get(*rc) for rc in selected) if c is not None and c.text]
        if not targets:
            return
        coords = set(selected)
        before = self._snapshot(coords)
        new_value = NEXT_CHECK[current.check if current is not None and current.text else targets[0].check]
        for cell in targets:
            cell.check = new_value
        self._push_history(before, self._snapshot(coords))
        self.after_change()

    def on_escape(self) -> None:
        if self.state.filter_tag is not None:
            self.set_filter(None)
        elif self.state.query:
            self.close_find()

    # -- clipboard ------------------------------------------------------------------
    def _selection_block(self) -> tuple[list[list[str]], int]:
        """The selected cells as rows of text, plus how many of them have text."""
        top, left, bottom, right = self.grid.selection_bounds()
        block = []
        for r in range(top, bottom + 1):
            row_values = []
            for c in range(left, right + 1):
                cell = self.sheet.get(r, c)
                row_values.append(cell.text if cell else "")
            block.append(row_values)
        filled = sum(1 for row_values in block for v in row_values if v)
        return block, filled

    def copy_cell(self) -> None:
        block, filled = self._selection_block()
        if not filled:
            return
        single = len(block) == 1 and len(block[0]) == 1
        text = block[0][0] if single else join_block(block, self.copy_sep)
        self._clip = (text, block)
        QApplication.clipboard().setText(text)
        self.flash_hint("Copied" if filled == 1 else f"Copied {filled} cells")

    def cut_cell(self) -> None:
        block, filled = self._selection_block()
        if not filled:
            return
        self.copy_cell()
        coords = set(self.grid.selected_cells())
        before = self._snapshot(coords)
        for row, col in coords:
            self.sheet.clear(row, col)
        self._push_history(before, self._snapshot(coords))
        self.after_change()
        self.flash_hint("Cut" if filled == 1 else f"Cut {filled} cells")

    def paste(self, spread: bool = True) -> None:
        text = QApplication.clipboard().text()
        if not text.strip():
            return
        if not spread:
            block = [[text.strip("\r\n")]]
        elif self._clip is not None and self._clip[0] == text:
            block = self._clip[1]  # copied inside GridPad: keep the exact cells
        else:
            block = split_paste(text)
        top, left, bottom, right = self.grid.selection_bounds()
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
        self.grid.select_range(top, left, top + rows - 1, left + cols - 1)
        if written:
            self.flash_hint(f"Pasted {written} cell" if written == 1 else f"Pasted {written} cells")

    def flash_hint(self, text: str) -> None:
        self.sheetbar.hint_label.setText(text)
        QTimer.singleShot(2000, self.update_status)

    # -- undo / redo ---------------------------------------------------------------
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

    def undo(self) -> None:
        if self.grid.editing:
            self.grid.editor.undo()
            return
        if not self._undo_stack:
            self.flash_hint("Nothing to undo")
            return
        entry = self._undo_stack.pop()
        self._redo_stack.append(entry)
        self._apply_state(entry[0], entry[1])
        self.flash_hint("Undone")

    def redo(self) -> None:
        if self.grid.editing:
            self.grid.editor.redo()
            return
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
            self.switch_sheet(sheet_index)
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
            self.grid.select_range(min(rows), min(cols), max(rows), max(cols))

    # -- sort and duplicates -------------------------------------------------------
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

    def _sort_box(self) -> tuple[int, int, int, int] | None:
        """Scope for the sort tools: a selected block if there is one, else the data island
        around the cursor (Excel's current region). None means the whole sheet."""
        if len(self.grid.selected_cells()) > 1:
            return self.grid.selection_bounds()
        row, col = self.grid.current_cell()
        region = current_region(self.sheet, row, col)
        max_r, max_c = self.sheet.used_extent()
        if max_r >= 0 and region == (0, 0, max_r, max_c):
            return None
        return region

    def _sort_scope(self) -> tuple[tuple[int, int, int, int] | None, bool]:
        box = self._sort_box()
        if box is not None and box[0] == box[2] and box[1] == box[3] and self.sheet.get(box[0], box[1]) is None:
            return box, False
        return box, True

    @staticmethod
    def _box_ref(box: tuple[int, int, int, int]) -> str:
        return f"{cell_ref(box[0], box[1])}:{cell_ref(box[2], box[3])}"

    def sort_rows_action(self, reverse: bool) -> None:
        self.grid.commit_edit()
        box, has_data = self._sort_scope()
        if not has_data:
            self.flash_hint("Click a cell inside your data first")
            return
        col = self.grid.current_cell()[1]
        count = self._sheet_op(lambda: sort_rows(self.sheet, col, reverse, box))
        if box:
            self.grid.select_range(*box)
            self.flash_hint(f"Sorted {self._box_ref(box)} by column {col_name(col)} · Ctrl+Z undoes")
        else:
            self.grid.select_cell(0, col)
            self.flash_hint(f"Sorted {count} rows by column {col_name(col)} · Ctrl+Z undoes")

    def duplicates_action(self) -> None:
        self.grid.commit_edit()
        box, has_data = self._sort_scope()
        if not has_data:
            self.flash_hint("Click a cell inside your data first")
            return
        col = self.grid.current_cell()[1]
        dup_values, dup_rows = self._sheet_op(lambda: duplicates_first(self.sheet, col, box))
        top = box[0] if box else 0
        if dup_rows:
            self.grid.select_range(top, col, top + dup_rows - 1, col)
            self.flash_hint(f"{dup_rows} rows share {dup_values} repeated values — moved to the top · Ctrl+Z undoes")
        else:
            self.flash_hint(f"No duplicates in column {col_name(col)}")

    def sort_menu(self) -> None:
        self.grid.commit_edit()
        letter = col_name(self.grid.current_cell()[1])
        box, has_data = self._sort_scope()
        if not has_data:
            self.flash_hint("Click a cell inside your data first")
            return
        scope = f" in {self._box_ref(box)}" if box else ""
        menu = QMenu(self)
        menu.setFont(theme.sans(13))
        az = menu.addAction(f"Sort rows A → Z by column {letter}{scope}")
        za = menu.addAction(f"Sort rows Z → A by column {letter}{scope}")
        menu.addSeparator()
        dup = menu.addAction(f"Check duplicates in column {letter}{scope} — group them on top")
        dedupe = menu.addAction(f"Delete duplicate rows in column {letter}{scope} — keep the first")
        az.triggered.connect(lambda: self.sort_rows_action(False))
        za.triggered.connect(lambda: self.sort_rows_action(True))
        dup.triggered.connect(self.duplicates_action)
        dedupe.triggered.connect(self.dedupe_action)
        menu.exec(QCursor.pos())

    def dedupe_action(self) -> None:
        self.grid.commit_edit()
        box, has_data = self._sort_scope()
        if not has_data:
            self.flash_hint("Click a cell inside your data first")
            return
        col = self.grid.current_cell()[1]
        removed, values_hit = self._sheet_op(lambda: dedupe_rows(self.sheet, col, box))
        if removed:
            self.flash_hint(f"Deleted {removed} duplicate rows ({values_hit} repeated values) · Ctrl+Z undoes")
        else:
            self.flash_hint(f"No duplicates in column {col_name(col)}")

    # -- rows and columns ----------------------------------------------------------
    def _row_header_menu(self, pos) -> None:
        header = self.grid.verticalHeader()
        row = header.logicalIndexAt(pos)
        if row < 0:
            return
        menu = QMenu(self)
        menu.setFont(theme.sans(13))
        above = menu.addAction("Insert row above")
        below = menu.addAction("Insert row below")
        menu.addSeparator()
        up = menu.addAction("Move row up")
        down = menu.addAction("Move row down")
        up.setEnabled(row > 0)
        menu.addSeparator()
        delete = menu.addAction(f"Delete row {row + 1}")
        chosen = menu.exec(header.mapToGlobal(pos))
        col = self.grid.current_cell()[1]
        if chosen is above:
            self._sheet_op(lambda: insert_row(self.sheet, row))
            self.grid.select_cell(row, col)
            self.flash_hint("Row inserted · Ctrl+Z undoes")
        elif chosen is below:
            self._sheet_op(lambda: insert_row(self.sheet, row + 1))
            self.grid.select_cell(row + 1, col)
            self.flash_hint("Row inserted · Ctrl+Z undoes")
        elif chosen is up:
            new_row = self._sheet_op(lambda: move_row(self.sheet, row, -1))
            self.grid.select_cell(new_row, col)
        elif chosen is down:
            new_row = self._sheet_op(lambda: move_row(self.sheet, row, 1))
            self.grid.select_cell(new_row, col)
        elif chosen is delete:
            self._sheet_op(lambda: delete_row(self.sheet, row))
            self.grid.select_cell(row, col)
            self.flash_hint(f"Row {row + 1} deleted · Ctrl+Z undoes")

    def _col_header_menu(self, pos) -> None:
        header = self.grid.horizontalHeader()
        col = header.logicalIndexAt(pos)
        if col < 0:
            return
        letter = col_name(col)
        menu = QMenu(self)
        menu.setFont(theme.sans(13))
        left = menu.addAction("Insert column left")
        right = menu.addAction("Insert column right")
        menu.addSeparator()
        move_l = menu.addAction("Move column left")
        move_r = menu.addAction("Move column right")
        move_l.setEnabled(col > 0)
        menu.addSeparator()
        delete = menu.addAction(f"Delete column {letter}")
        chosen = menu.exec(header.mapToGlobal(pos))
        row = self.grid.current_cell()[0]
        if chosen is left:
            self._sheet_op(lambda: insert_col(self.sheet, col))
            self.grid.select_cell(row, col)
            self.flash_hint("Column inserted · Ctrl+Z undoes")
        elif chosen is right:
            self._sheet_op(lambda: insert_col(self.sheet, col + 1))
            self.grid.select_cell(row, col + 1)
            self.flash_hint("Column inserted · Ctrl+Z undoes")
        elif chosen is move_l:
            new_col = self._sheet_op(lambda: move_col(self.sheet, col, -1))
            self.grid.select_cell(row, new_col)
        elif chosen is move_r:
            new_col = self._sheet_op(lambda: move_col(self.sheet, col, 1))
            self.grid.select_cell(row, new_col)
        elif chosen is delete:
            self._sheet_op(lambda: delete_col(self.sheet, col))
            self.grid.select_cell(row, col)
            self.flash_hint(f"Column {letter} deleted · Ctrl+Z undoes")

    # -- import and replace --------------------------------------------------------
    def import_file(self, path: str | None = None) -> None:
        self.grid.commit_edit()
        if not path:
            start = str(self.workbook.path.parent) if self.workbook.path else str(Path.home())
            path, _ = QFileDialog.getOpenFileName(self, "Import CSV or text", start,
                                                  "CSV or text (*.csv *.txt);;All files (*.*)")
            if not path:
                return
        try:
            raw = Path(path).read_bytes()
        except OSError as exc:
            QMessageBox.warning(self, "Couldn't import", f"{path} couldn't be read.\n{exc}")
            return
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", errors="replace")
        row, col = self.grid.current_cell()
        dialog = ImportDialog(Path(path).name, text, cell_ref(row, col), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        block = dialog.block()
        if not block:
            self.flash_hint("Nothing to import")
            return
        if dialog.to_new_sheet():
            name = self.workbook.unique_sheet_name(Path(path).stem or "Imported")
            index = self.workbook.add_sheet(name)
            self.switch_sheet(index)
            row, col = 0, 0
        rows = len(block)
        cols = max((len(r) for r in block), default=1)
        coords = {(row + r, col + c) for r in range(rows) for c in range(cols)
                  if row + r < MAX_ROWS and col + c < MAX_COLS}
        before = self._snapshot(coords)
        written = self.workbook.paste_block(self.current, row, col, block)
        self._push_history(before, self._snapshot(coords))
        self.after_change()
        self.grid.select_range(row, col, row + rows - 1, col + cols - 1)
        self.flash_hint(f"Imported {written} cells from {Path(path).name}")

    def replace_dialog(self) -> None:
        self.grid.commit_edit()
        dialog = ReplaceDialog(self.state.query, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        find, replacement = dialog.find_text(), dialog.replace_text()
        if not find:
            return
        indexes = range(len(self.workbook.sheets)) if dialog.all_sheets() else [self.current]
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

    def toggle_freeze(self) -> None:
        on = not self.grid._freeze_row
        self.grid.set_frozen(on)
        self.settings.setValue("freeze", on)
        self.flash_hint("Row 1 pinned while scrolling" if on else "Row 1 unpinned")

    # -- export --------------------------------------------------------------------
    def export_sheet(self) -> None:
        self.grid.commit_edit()
        dialog = ExportDialog(self.workbook, self.current, self.copy_sep, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.copy_sep = dialog.separator()
        self.settings.setValue("copy_sep", self.copy_sep)
        sheet = self.workbook.sheets[dialog.sheet_index()]
        suffix = dialog.suffix()
        folder = self.workbook.path.parent if self.workbook.path else Path.home()
        start = str(folder / (sheet.name + suffix))
        if suffix == ".csv":
            filters = "CSV file (*.csv);;Text file (*.txt)"
        else:
            filters = "Text file (*.txt);;CSV file (*.csv)"
        path, _ = QFileDialog.getSaveFileName(self, "Export sheet", start, filters)
        if not path:
            return
        if not path.lower().endswith((".csv", ".txt")):
            path += suffix
        try:
            Path(path).write_text(dialog.text() + "\n", encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", f"Couldn't write {path}.\n{exc}")
            return
        self.flash_hint(f"Exported {Path(path).name}")

    # -- tags and help -------------------------------------------------------------
    def tag_menu(self) -> None:
        counts = self.workbook.tag_counts()
        menu = QMenu(self)
        menu.setFont(theme.sans(13))
        if not counts:
            none_action = menu.addAction("No tags yet — write #word inside a note")
            none_action.setEnabled(False)
        for tag in sorted(counts, key=lambda t: (-counts[t], t)):
            action = menu.addAction(f"#{tag}   ·   {counts[tag]}")
            action.setCheckable(True)
            action.setChecked(tag == self.state.filter_tag)
            action.triggered.connect(lambda _=False, t=tag: self.set_filter(t))
        if counts:
            menu.addSeparator()
            clear = menu.addAction("Clear filter")
            clear.setEnabled(self.state.filter_tag is not None)
            clear.triggered.connect(lambda: self.set_filter(None))
        menu.exec(QCursor.pos())

    def show_help(self) -> None:
        HelpDialog(self).exec()

    def show_settings(self) -> None:
        self.grid.commit_edit()
        dialog = SettingsDialog(theme.current_theme(), theme.mono_family(), theme.sans_family(),
                                theme.app_bold(), self.copy_sep,
                                str(self.settings.value("effect", "None")), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.settings.setValue("theme", dialog.theme_name())
        self.settings.setValue("font_mono", dialog.mono_font())
        self.settings.setValue("font_sans", dialog.sans_font())
        self.settings.setValue("bold", dialog.bold())
        self.settings.setValue("effect", dialog.effect())
        self.copy_sep = dialog.separator()
        self.settings.setValue("copy_sep", self.copy_sep)
        self._reopen_with_new_look()

    def _reopen_with_new_look(self) -> None:
        """Rebuild the window so every widget picks up the new colors and fonts."""
        theme.load_appearance(self.settings)
        app = QApplication.instance()
        theme.apply_to_app(app)
        self._reopening = True
        replacement = MainWindow(self.workbook, self.settings)
        replacement.restoreGeometry(self.saveGeometry())
        replacement.show()
        app._gridpad_window = replacement  # keep a live reference
        self.close()

    # -- find ---------------------------------------------------------------------
    def on_query_changed(self, text: str) -> None:
        self.state.query = text.strip()
        if not self.state.query:
            self.state.clear_find()
            self.matches = []
            self.match_index = -1
            self.model.refresh()
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
        self.matches = self.workbook.find(self.state.query)
        self.match_index = -1
        if self.matches:
            if keep_position and previous is not None:
                for i, m in enumerate(self.matches):
                    if (m.sheet, m.row, m.col) == (previous.sheet, previous.row, previous.col):
                        self.match_index = i
                        break
            if self.match_index < 0:
                row, col = self.grid.current_cell()
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
        self.state.matches = {(m.row, m.col) for m in self.matches if m.sheet == self.current}
        cur = self.matches[self.match_index] if 0 <= self.match_index < len(self.matches) else None
        self.state.current_match = (cur.row, cur.col) if cur is not None and cur.sheet == self.current else None
        self.model.refresh()
        self.topbar.search.set_count(self.match_index + 1 if self.matches else 0, len(self.matches))

    def _show_match(self, select: bool) -> None:
        if not (0 <= self.match_index < len(self.matches)):
            return
        m = self.matches[self.match_index]
        if m.sheet != self.current:
            self.switch_sheet(m.sheet, keep_find=True)
        if select:
            self.grid.select_cell(m.row, m.col)
        self._sync_find_state()

    def step_match(self, delta: int) -> None:
        if not self.matches:
            return
        self.match_index = (self.match_index + delta) % len(self.matches)
        self._show_match(select=True)
        self.update_status()

    def close_find(self) -> None:
        self.topbar.search.clear()  # triggers on_query_changed("")
        self.grid.setFocus()

    # -- tags ---------------------------------------------------------------------
    def set_filter(self, tag: str | None) -> None:
        if tag == self.state.filter_tag:
            tag = None
        self.state.filter_tag = tag
        self.topbar.set_filter(tag)
        self.model.refresh()
        if tag is None:
            self.grid.setFocus()
        self.update_status()

    # -- sheets -------------------------------------------------------------------
    def switch_sheet(self, index: int, keep_find: bool = False) -> None:
        if not (0 <= index < len(self.workbook.sheets)):
            return
        self.grid.commit_edit()
        self._last_cell[self.current] = self.grid.current_cell()
        self.current = index
        self.model.set_sheet(self.sheet)
        self.autofit_columns()
        row, col = self._last_cell.get(index, (0, 0))
        self.grid.select_cell(row, col)
        self.sheetbar.set_sheets([s.name for s in self.workbook.sheets], self.current)
        if self.state.query and not keep_find:
            self._sync_find_state()
        self.update_status()

    def add_sheet(self) -> None:
        index = self.workbook.add_sheet()
        self.switch_sheet(index)
        self.autosave()
        self.update_status()
        self.rename_sheet(index)

    def rename_sheet(self, index: int) -> None:
        sheet = self.workbook.sheets[index]
        name, ok = QInputDialog.getText(self, "Rename sheet", "Sheet name", QLineEdit.EchoMode.Normal, sheet.name)
        name = name.strip()
        if ok and name and name != sheet.name:
            sheet.name = self.workbook.unique_sheet_name(name)
            self.workbook.dirty = True
            self.sheetbar.set_sheets([s.name for s in self.workbook.sheets], self.current)
            self.after_change()
        self.grid.setFocus()

    def duplicate_sheet(self, index: int) -> None:
        self._clear_history()  # sheet order changes would break saved undo positions
        new_index = self.workbook.duplicate_sheet(index)
        self.switch_sheet(new_index)
        self.after_change()

    def move_sheet(self, index: int, delta: int) -> None:
        self._clear_history()
        new_index = self.workbook.move_sheet(index, delta)
        if index == self.current:
            self.current = new_index
        elif new_index == self.current:
            self.current = index
        self.sheetbar.set_sheets([s.name for s in self.workbook.sheets], self.current)
        self.after_change()

    def delete_sheet(self, index: int) -> None:
        self._clear_history()
        sheet = self.workbook.sheets[index]
        if len(self.workbook.sheets) <= 1:
            return
        if sheet.note_count():
            answer = QMessageBox.question(
                self, "Delete sheet",
                f"Delete “{sheet.name}” and its {sheet.note_count()} notes?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.workbook.remove_sheet(index)
        self._last_cell.pop(index, None)
        self.current = min(self.current if index > self.current else max(0, self.current - 1),
                           len(self.workbook.sheets) - 1)
        self.model.set_sheet(self.sheet)
        self.sheetbar.set_sheets([s.name for s in self.workbook.sheets], self.current)
        self.after_change()

    # -- files --------------------------------------------------------------------
    def autosave(self) -> None:
        if self.workbook.path is not None:
            try:
                self.workbook.save()
            except OSError as exc:
                QMessageBox.warning(self, "Save failed", f"Couldn't save {self.workbook.name}.\n{exc}")
        else:
            self.workbook.dirty = True

    def save(self) -> bool:
        if self.workbook.path is None:
            return self.save_as()
        try:
            self.workbook.save()
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", f"Couldn't save {self.workbook.name}.\n{exc}")
            return False
        self.update_status()
        return True

    def save_as(self) -> bool:
        start = str(self.workbook.path) if self.workbook.path else str(Path.home() / ("notes" + FILE_SUFFIX))
        path, _ = QFileDialog.getSaveFileName(self, "Save workbook", start, f"GridPad workbook (*{FILE_SUFFIX})")
        if not path:
            return False
        if not path.endswith(FILE_SUFFIX):
            path += FILE_SUFFIX
        try:
            self.workbook.save(path)
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", f"Couldn't save to {path}.\n{exc}")
            return False
        self.settings.setValue("last_file", path)
        self.refresh_all()
        return True

    def open_file(self) -> None:
        start = str(self.workbook.path.parent) if self.workbook.path else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Open workbook", start, f"GridPad workbook (*{FILE_SUFFIX})")
        if path:
            self.open_path(path)

    def open_path(self, path: str) -> None:
        if not self._confirm_discard():
            return
        try:
            workbook = Workbook.load(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Couldn't open", f"{path} isn't a readable GridPad file.\n{exc}")
            return
        self.load_workbook(workbook)
        self.settings.setValue("last_file", str(path))

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if any(url.toLocalFile().lower().endswith((".csv", ".txt", FILE_SUFFIX))
               for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            lower = path.lower()
            if lower.endswith(FILE_SUFFIX):
                self.open_path(path)
                break
            if lower.endswith((".csv", ".txt")):
                self.import_file(path)
                break
        event.acceptProposedAction()

    def new_workbook(self) -> None:
        if not self._confirm_discard():
            return
        self.load_workbook(Workbook())
        self.settings.remove("last_file")

    def load_workbook(self, workbook: Workbook) -> None:
        self.grid.cancel_edit()
        self._clear_history()
        self.workbook = workbook
        self.current = 0
        self._last_cell = {}
        self.matches = []
        self.match_index = -1
        self.state.clear_find()
        self.state.filter_tag = None
        self.topbar.search.clear()
        self.topbar.set_filter(None)
        self.model.set_sheet(self.sheet)
        self.grid.select_cell(0, 0)
        self.refresh_all()
        self.grid.setFocus()

    def _confirm_discard(self) -> bool:
        """True if it is fine to drop the current workbook (saved, empty, or the user agreed)."""
        if self.workbook.path is not None or self.workbook.total_notes() == 0:
            return True
        answer = QMessageBox.question(
            self, "Unsaved notes",
            "This workbook hasn't been saved yet. Save it first?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return answer == QMessageBox.StandardButton.Discard

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if getattr(self, "_reopening", False):
            event.accept()
            return
        self.grid.commit_edit()
        if not self._confirm_discard():
            event.ignore()
            return
        self.settings.setValue("geometry", self.saveGeometry())
        if self.workbook.path is not None:
            self.settings.setValue("last_file", str(self.workbook.path))
        event.accept()
