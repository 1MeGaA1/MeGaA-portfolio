"""Scripted behaviour check, run off-screen:  python tools/smoke_test.py

Drives the real window with key presses and asserts on the model and the saved file.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPoint, QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.main import create_app  # noqa: E402
from app.main_window import MainWindow  # noqa: E402
from app.model import Sheet, Workbook, export_text, parse_ref  # noqa: E402

checks = 0


def ok(cond: bool, what: str) -> None:
    global checks
    checks += 1
    if not cond:
        raise SystemExit(f"FAIL: {what}")
    print("ok  -", what)


def key(widget, k, mods=Qt.KeyboardModifier.NoModifier, text: str = "") -> None:
    QTest.keyClick(widget, k, mods) if not text else QTest.keyClicks(widget, text)


def main() -> int:
    app = create_app(["gridpad"])
    tmp = Path(tempfile.mkdtemp())
    settings = QSettings(str(tmp / "settings.ini"), QSettings.Format.IniFormat)
    path = tmp / "smoke.gridpad"
    wb = Workbook()
    wb.save(path)
    win = MainWindow(wb, settings)
    win.show()
    app.processEvents()
    grid = win.grid
    sheet = win.sheet

    # Type into A1, Enter saves and moves down — editing happens in the cell, Excel style.
    grid.setFocus()
    QTest.keyClicks(grid, "H")  # first key starts editing in the cell
    app.processEvents()
    ok(grid.editing and grid.editor.hasFocus(), "typing opens the in-cell editor")
    QTest.keyClicks(grid.editor, "ello #home")
    QTest.keyClick(grid.editor, Qt.Key.Key_Return)
    app.processEvents()
    ok(sheet.get(0, 0) is not None and sheet.get(0, 0).text == "Hello #home", "Enter saves the note into A1")
    ok(grid.current_cell() == (1, 0), "after saving, the cursor moves down to A2")
    ok(sheet.get(0, 0).tags == ["home"], "#home is parsed as a tag")
    saved = json.loads(path.read_text(encoding="utf-8"))
    ok(saved["sheets"][0]["cells"]["A1"]["text"] == "Hello #home", "autosave wrote the file")

    # Shift+Enter makes a new line; Esc cancels an edit.
    QTest.keyClicks(grid, "a")
    QTest.keyClick(grid.editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    QTest.keyClicks(grid.editor, "b")
    QTest.keyClick(grid.editor, Qt.Key.Key_Return)
    app.processEvents()
    ok(sheet.get(1, 0).text == "a\nb", "Shift+Enter inserts a new line")
    grid.select_cell(1, 0)
    QTest.keyClick(grid, Qt.Key.Key_F2)
    QTest.keyClicks(grid.editor, "zzz")
    QTest.keyClick(grid.editor, Qt.Key.Key_Escape)
    app.processEvents()
    ok(sheet.get(1, 0).text == "a\nb", "Esc cancels the edit")
    ok(grid.hasFocus(), "Esc hands focus back to the grid")

    # Tab saves and moves right; losing focus saves too.
    grid.select_cell(0, 2)
    QTest.keyClicks(grid, "x")
    QTest.keyClick(grid.editor, Qt.Key.Key_Tab)
    app.processEvents()
    ok(sheet.get(0, 2).text == "x" and grid.current_cell() == (0, 3), "Tab saves and moves right")
    QTest.keyClicks(grid, "q")
    grid.setFocus()
    app.processEvents()
    ok(sheet.get(0, 3) is not None and sheet.get(0, 3).text == "q", "losing focus saves the cell")
    grid.select_range(0, 2, 0, 3)
    QTest.keyClick(grid, Qt.Key.Key_Delete)
    ok(sheet.get(0, 2) is None and sheet.get(0, 3) is None, "cleanup block cleared")

    # Tab moves right; Delete clears; Ctrl+K cycles the checkbox; Ctrl+B bolds.
    grid.select_cell(0, 0)
    QTest.keyClick(grid, Qt.Key.Key_Tab)
    ok(grid.current_cell() == (0, 1), "Tab moves one cell right")
    grid.select_cell(1, 0)
    QTest.keyClick(grid, Qt.Key.Key_Delete)
    ok(sheet.get(1, 0) is None, "Delete clears the cell")
    grid.select_cell(0, 0)
    win.toggle_check()
    ok(sheet.get(0, 0).check == "todo", "Ctrl+K adds a checkbox")
    win.toggle_check()
    ok(sheet.get(0, 0).check == "done", "Ctrl+K again ticks it")
    win.toggle_check()
    ok(sheet.get(0, 0).check is None, "Ctrl+K a third time removes it")
    win.toggle_bold()
    ok(sheet.get(0, 0).bold, "Ctrl+B bolds the cell")

    # Clipboard: paste spreads across cells, Ctrl+Shift+V keeps it whole, copy/cut.
    clip = QApplication.clipboard()
    clip.setText("one, two ,three\nfour\tfive")
    grid.select_cell(5, 0)
    QTest.keyClick(grid, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    ok([sheet.get(5, c).text for c in range(3)] == ["one", "two", "three"], "Ctrl+V spreads a comma line across the row")
    ok(sheet.get(6, 0).text == "four" and sheet.get(6, 1).text == "five", "the next line goes down a row; tabs split too")
    clip.setText("left-----middle----right")
    grid.select_cell(7, 0)
    win.paste(spread=True)
    ok([sheet.get(7, c).text for c in range(3)] == ["left", "middle", "right"], "runs of dashes split too")
    clip.setText("keep, this\ntogether")
    grid.select_cell(8, 0)
    QTest.keyClick(grid, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    app.processEvents()
    ok(sheet.get(8, 0).text == "keep, this\ntogether" and sheet.get(8, 1) is None, "Ctrl+Shift+V pastes as one note")
    grid.select_cell(5, 0)
    QTest.keyClick(grid, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    ok(clip.text() == "one", "Ctrl+C copies the cell text")
    QTest.keyClick(grid, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
    ok(sheet.get(5, 0) is None and clip.text() == "one", "Ctrl+X cuts it")

    # Ranges: Shift+arrows select a block; copy / paste / bold / delete / cut act on it.
    grid.select_cell(6, 0)  # four | five  over  left | middle
    QTest.keyClick(grid, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    QTest.keyClick(grid, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    app.processEvents()
    ok(len(grid.selected_cells()) == 4 and grid.selection_bounds() == (6, 0, 7, 1), "Shift+arrows select a 2x2 block")
    ok(grid.verticalHeader().highlighted == {6, 7} and grid.horizontalHeader().highlighted == {0, 1},
       "row and column headers light up for the block")
    QTest.keyClick(grid, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    ok(clip.text() == "four\tfive\nleft\tmiddle", "copying a block gives tab-separated rows")
    grid.select_cell(10, 2)
    QTest.keyClick(grid, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    ok(sheet.get(10, 2).text == "four" and sheet.get(11, 3).text == "middle", "pasting a block keeps its shape")
    ok(grid.selection_bounds() == (10, 2, 11, 3), "the pasted block is selected afterwards")
    win.toggle_bold()
    ok(all(sheet.get(r, c).bold for r in (10, 11) for c in (2, 3)), "Ctrl+B bolds every cell in the block")
    QTest.keyClick(grid, Qt.Key.Key_Delete)
    ok(all(sheet.get(r, c) is None for r in (10, 11) for c in (2, 3)), "Delete clears the whole block")
    clip.setText("same")
    grid.select_range(12, 0, 12, 2)
    win.paste()
    ok([sheet.get(12, c).text for c in range(3)] == ["same"] * 3, "one value pasted into a range fills it")
    grid.select_range(6, 0, 7, 1)
    QTest.keyClick(grid, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
    ok(sheet.get(6, 0) is None and sheet.get(7, 1) is None and sheet.get(7, 2).text == "right",
       "Ctrl+X cuts just the block")
    ok(clip.text() == "four\tfive\nleft\tmiddle", "and puts it on the clipboard")

    # Copied blocks follow the chosen export separator.
    win.copy_sep = "----"
    sheet.set_text(15, 0, "aa")
    sheet.set_text(15, 1, "bb")
    grid.select_range(15, 0, 15, 1)
    QTest.keyClick(grid, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    ok(clip.text() == "aa----bb", "block copy uses the chosen ---- separator")
    grid.select_cell(17, 0)
    QTest.keyClick(grid, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    ok(sheet.get(17, 0).text == "aa" and sheet.get(17, 1).text == "bb", "and still pastes back as separate cells")
    win.copy_sep = "\t"

    # Find across sheets.
    idx = win.workbook.add_sheet("Work")  # straight on the model: the UI path opens a rename dialog
    win.switch_sheet(idx)
    win.sheet.set_text(2, 1, "hello again")
    win.after_change(2, 1)
    win.switch_sheet(0)
    win.topbar.search.input.setText("hello")
    app.processEvents()
    ok(len(win.matches) == 2, "find sees matches on both sheets")
    ok(win.state.current_match == (0, 0), "the first match is the one on the current sheet")
    win.step_match(1)
    ok(win.current == idx and grid.current_cell() == (2, 1), "Enter steps to the match on the other sheet")
    win.close_find()
    ok(win.state.query == "", "Esc closes find")

    # Tag filter: click the pill in the cell, or the Ctrl+Shift+T menu path (set_filter).
    win.switch_sheet(0)
    pill_rect = grid.visualRect(win.model.index(0, 0))
    QTest.mouseClick(grid.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     QPoint(pill_rect.right() - 15, pill_rect.center().y()))
    app.processEvents()
    ok(win.state.filter_tag == "home", "clicking a tag pill filters by it")
    win.grid.setFocus()
    QTest.keyClick(grid, Qt.Key.Key_Escape)
    ok(win.state.filter_tag is None, "Esc clears the filter")
    win.set_filter("home")
    ok(win.state.filter_tag == "home", "the tag menu path filters too")
    win.set_filter(None)

    # Sheets: duplicate, move, delete.
    win.switch_sheet(0)
    win.duplicate_sheet(0)
    ok(len(win.workbook.sheets) == 3 and win.sheet.get(0, 0).text == "Hello #home", "duplicate copies the notes")
    win.move_sheet(1, 1)
    ok(win.workbook.sheets[2].name.endswith("copy"), "move right reorders sheets")
    win.workbook.remove_sheet(2)
    win.current = 0
    win.model.set_sheet(win.sheet)
    win.after_change()
    ok(len(win.workbook.sheets) == 2, "delete removes a sheet")

    # Reload from disk and compare.
    again = Workbook.load(path)
    ok([s.name for s in again.sheets] == [s.name for s in win.workbook.sheets], "sheet names survive a reload")
    ok(again.sheets[0].get(0, 0).text == "Hello #home" and again.sheets[0].get(0, 0).bold, "cell text and bold survive a reload")
    ok(parse_ref("AA10") == (9, 26), "cell refs beyond Z parse")

    # Export with a chosen separator.
    t = Sheet("T")
    t.set_text(0, 0, "a,b")
    t.set_text(0, 2, "c\nd")
    t.set_text(1, 1, "e")
    ok(export_text(t, ",") == '"a,b",,"c\nd"\n,e,', "CSV export quotes commas and newlines")
    ok(export_text(t, "----") == "a,b--------c d\n----e----", "dash export joins columns with ----")
    ok(export_text(t, "\t") == "a,b\t\tc d\n\te\t", "tab export works")

    # Themes: every palette keeps text readable, and switching swaps the module colors.
    from app import theme as theme_mod

    def lum(color: str) -> float:
        def lin(c: float) -> float:
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = (lin(int(color[i:i + 2], 16) / 255) for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def contrast(a: str, b: str) -> float:
        la, lb = lum(a), lum(b)
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

    for name, c in theme_mod.THEMES.items():
        readable = (
            contrast(c["TEXT"], c["BG"]) >= 7
            and contrast(c["TEXT"], c["ACCENT_BG"]) >= 4.5
            and contrast(c["MUTED"], c["PANEL"]) >= 3
            and contrast(c["ACCENT"], c["ACCENT_BG"]) >= 3
            and contrast(c["TAG"], c["TAG_BG"]) >= 3
            and contrast(c["HI_TEXT"], c["HI"]) >= 3
        )
        ok(readable, f"theme {name} keeps its text readable")
    theme_mod.apply_theme("Nord")
    ok(theme_mod.ACCENT == theme_mod.THEMES["Nord"]["ACCENT"], "apply_theme swaps the palette")
    theme_mod.set_mono_family("Courier New")
    ok(theme_mod.mono_family() == "Courier New", "the mono font can be chosen")
    theme_mod.set_mono_family(None)
    theme_mod.apply_theme(theme_mod.DEFAULT_THEME)

    # Bold mode steps every weight up while keeping cell-bold distinct.
    from PySide6.QtGui import QFont
    theme_mod.set_app_bold(True)
    ok(theme_mod.sans(13).weight() == QFont.Weight.DemiBold
       and theme_mod.mono(13, bold=True).weight() == QFont.Weight.Bold, "bold mode thickens both fonts")
    theme_mod.set_app_bold(False)
    ok(theme_mod.sans(13).weight() == QFont.Weight.Normal, "and turns back off")

    # Columns auto-fit their content.
    win.sheet.set_text(20, 4, "a really long note that should stretch this column quite a lot indeed")
    win.after_change(20, 4)
    ok(grid.columnWidth(4) > 300, "a long note widens its column")
    win.sheet.clear(20, 4)
    win.after_change(20, 4)
    ok(grid.columnWidth(4) == 180, "clearing shrinks it back to the default")
    ok(grid.columnWidth(9) == 180, "empty columns keep the default width")

    # A column autosizes with enough headroom that a just-fitting note never elides.
    from PySide6.QtGui import QFontMetrics
    from app import theme as theme_for_fit
    email = "someone.long.name@example.com"
    win.sheet.set_text(22, 4, email)
    win.after_change(22, 4)
    fit_fm = QFontMetrics(theme_for_fit.mono(13))
    ok(grid.columnWidth(4) >= fit_fm.horizontalAdvance(email) + 17,
       "the column is wider than the text plus padding and grid line")
    win.sheet.clear(22, 4)
    win.after_change(22, 4)

    # Undo / redo.
    grid.select_cell(21, 0)
    QTest.keyClicks(grid, "u")
    QTest.keyClicks(grid.editor, "ndo me")
    QTest.keyClick(grid.editor, Qt.Key.Key_Return)
    app.processEvents()
    ok(sheet.get(21, 0).text == "undo me", "typed a note for the undo test")
    win.undo()
    ok(sheet.get(21, 0) is None, "Ctrl+Z takes the note back out")
    win.redo()
    ok(sheet.get(21, 0) is not None and sheet.get(21, 0).text == "undo me", "Ctrl+Y brings it back")
    win.undo()
    grid.select_cell(21, 0)
    clip.setText("p1, p2")
    QTest.keyClick(grid, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    ok(sheet.get(21, 0).text == "p1" and sheet.get(21, 1).text == "p2", "pasted for the undo test")
    win.undo()
    ok(sheet.get(21, 0) is None and sheet.get(21, 1) is None, "undo reverts a whole paste")
    grid.select_cell(21, 0)
    win.toggle_check()
    ok(sheet.get(21, 0) is not None and sheet.get(21, 0).check == "todo", "checkbox added for the undo test")
    win.undo()
    ok(sheet.get(21, 0) is None, "undo reverts the checkbox too")

    # The grid grows with content, Excel-style.
    ok(win.model.rowCount() == 200 and win.model.columnCount() == 26, "a light sheet shows the base 200 x 26 grid")
    grid.select_cell(0, 25)  # column Z
    clip.setText("z1\tz2\tz3")
    QTest.keyClick(grid, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    ok(sheet.get(0, 27) is not None and sheet.get(0, 27).text == "z3", "pasting past column Z lands in column AB")
    ok(win.model.columnCount() >= 32, "and the grid grew new columns to hold it")
    win.undo()
    win.sheet.set_text(400, 0, "deep note")
    win.after_change(400, 0)
    ok(win.model.rowCount() >= 431, "a note far down grows the rows")
    win.sheet.clear(400, 0)
    win.after_change(400, 0)

    # Sort and duplicates (whole rows move together; both undoable).
    sort_idx = win.workbook.add_sheet("SortT")
    win.switch_sheet(sort_idx)
    for i, v in enumerate(["b@x.com", "a@x.com", "c@x.com", "a@x.com", "b@x.com", "d@x.com"]):
        win.sheet.set_text(i, 0, v)
        win.sheet.set_text(i, 1, f"pw{i}")
    win.after_change()
    grid.select_cell(0, 0)
    win.sort_rows_action(reverse=False)
    ok([win.sheet.get(r, 0).text for r in range(6)]
       == ["a@x.com", "a@x.com", "b@x.com", "b@x.com", "c@x.com", "d@x.com"], "sort A-Z orders rows by the column")
    ok(win.sheet.get(0, 1).text == "pw1", "whole rows move together")
    win.duplicates_action()
    ok([win.sheet.get(r, 0).text for r in range(4)]
       == ["a@x.com", "a@x.com", "b@x.com", "b@x.com"], "duplicate values grouped at the top")
    ok([win.sheet.get(r, 0).text for r in (4, 5)] == ["c@x.com", "d@x.com"], "unique values follow A-Z")
    win.undo()
    win.undo()
    ok([win.sheet.get(r, 0).text for r in range(6)]
       == ["b@x.com", "a@x.com", "c@x.com", "a@x.com", "b@x.com", "d@x.com"], "two undos restore the original order")

    # Range-scoped sorting: with a block selected, only that block reorders (Excel-style).
    range_idx = win.workbook.add_sheet("RangeT")
    win.switch_sheet(range_idx)
    for i, (a, b, c) in enumerate([("b", "2", "x0"), ("c", "3", "x1"), ("a", "1", "x2")]):
        win.sheet.set_text(i, 0, a)
        win.sheet.set_text(i, 1, b)
        win.sheet.set_text(i, 2, c)
    win.after_change()
    grid.select_range(0, 0, 2, 1)  # columns A:B only
    win.sort_rows_action(reverse=False)
    ok([win.sheet.get(i, 0).text for i in range(3)] == ["a", "b", "c"], "range sort orders the selected rows")
    ok([win.sheet.get(i, 1).text for i in range(3)] == ["1", "2", "3"], "columns inside the selection move together")
    ok([win.sheet.get(i, 2).text for i in range(3)] == ["x0", "x1", "x2"], "columns outside the selection stay put")
    win.sheet.set_text(4, 0, "dup")
    win.sheet.set_text(5, 0, "dup")
    win.sheet.set_text(6, 0, "dup")
    win.after_change()
    grid.select_range(4, 0, 5, 0)
    win.dedupe_action()
    ok(win.sheet.get(4, 0) is not None and win.sheet.get(4, 0).text == "dup"
       and win.sheet.get(5, 0) is None
       and win.sheet.get(6, 0) is not None and win.sheet.get(6, 0).text == "dup",
       "range dedupe only touches the selected rows")
    win.undo()
    ok(win.sheet.get(5, 0) is not None, "and it undoes like everything else")

    # Data islands: two separate tables on one sheet — sorting one never touches the other.
    from app.model import current_region
    island_idx = win.workbook.add_sheet("IslandT")
    win.switch_sheet(island_idx)
    for i, v in enumerate(["b", "a", "b"]):  # island 1: A1:B3
        win.sheet.set_text(i, 0, v)
        win.sheet.set_text(i, 1, f"p{i}")
    for i, v in enumerate(["z", "y"]):  # island 2: D1:D2, separated by empty column C
        win.sheet.set_text(i, 3, v)
    win.after_change()
    ok(current_region(win.sheet, 0, 0) == (0, 0, 2, 1), "the island around A1 is detected")
    ok(current_region(win.sheet, 0, 3) == (0, 3, 1, 3), "the second island stays separate")
    grid.select_cell(1, 0)  # a single cell inside island 1
    win.duplicates_action()
    ok([win.sheet.get(i, 0).text for i in range(3)] == ["b", "b", "a"], "duplicates grouped inside the island only")
    ok(win.sheet.get(0, 3).text == "z" and win.sheet.get(1, 3).text == "y", "the second island is untouched")
    win.undo()
    grid.select_cell(0, 0)
    QTest.keyClick(grid, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    ok(grid.selection_bounds() == (0, 0, 2, 1), "Ctrl+A selects the island first")
    QTest.keyClick(grid, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    ok(grid.selection_bounds() == (0, 0, 2, 3), "Ctrl+A again selects the whole filled range")

    # Row / column surgery, dedupe, replace and import parsing (model level).
    from app.model import (dedupe_rows, delete_row, insert_row, move_row,
                           parse_delimited, replace_in_sheet)
    t2 = Sheet("T2")
    for i, v in enumerate(["a", "b", "c"]):
        t2.set_text(i, 0, v)
    insert_row(t2, 1)
    ok(t2.get(0, 0).text == "a" and t2.get(1, 0) is None and t2.get(2, 0).text == "b", "insert_row opens a gap")
    delete_row(t2, 1)
    ok([t2.get(i, 0).text for i in range(3)] == ["a", "b", "c"], "delete_row closes it again")
    move_row(t2, 0, 1)
    ok([t2.get(i, 0).text for i in range(2)] == ["b", "a"], "move_row swaps neighbours")
    d = Sheet("D")
    for i, v in enumerate(["x@a", "y@b", "x@a", "z@c", "X@A ", "y@b"]):
        d.set_text(i, 0, v)
        d.set_text(i, 1, f"row{i}")
    removed, values_hit = dedupe_rows(d, 0)
    ok((removed, values_hit) == (3, 2), "dedupe deletes 3 repeats across 2 values")
    ok([d.get(i, 0).text for i in range(3)] == ["x@a", "y@b", "z@c"], "one of each value survives, in order")
    ok(d.get(0, 1).text == "row0" and d.get(1, 1).text == "row1", "the first occurrence is the one kept")
    r = Sheet("R")
    r.set_text(0, 0, "mail@Old.com")
    r.set_text(1, 0, "keep")
    r.set_text(2, 0, "old.COM and old.com")
    matches, cells_changed = replace_in_sheet(r, "old.com", "new.org")
    ok((matches, cells_changed) == (3, 2), "replace counts matches case-insensitively")
    ok(r.get(0, 0).text == "mail@new.org" and r.get(2, 0).text == "new.org and new.org", "replacement applied")
    ok(parse_delimited("a;b\nc;d", ";") == [["a", "b"], ["c", "d"]], "custom separator import parses")
    ok(parse_delimited('x,"y,z"\n1,2', ",") == [["x", "y,z"], ["1", "2"]], "CSV import respects quoted commas")

    # Duplicate counter: repeated values get a live ×N count, per column.
    from app.model import duplicate_counts
    dc = Sheet("DC")
    dc.set_text(0, 0, "a@x")
    dc.set_text(1, 0, "A@X ")
    dc.set_text(2, 0, "b")
    dc.set_text(0, 1, "a@x")
    counts = duplicate_counts(dc)
    ok(counts.get((0, 0)) == 2 and counts.get((1, 0)) == 2, "both copies carry the value's count")
    ok((2, 0) not in counts and (0, 1) not in counts, "uniques and other columns stay unbadged")
    win.switch_sheet(0)
    win.sheet.set_text(30, 0, "twin")
    win.sheet.set_text(31, 0, "twin")
    win.after_change()
    ok(win.model.dups.get((30, 0)) == 2, "the grid tracks duplicates live")
    ok(f"{len(win.model.dups)} duplicates" in win.sheetbar.notes_label.text(), "the status bar counts them")
    win.sheet.clear(30, 0)
    win.sheet.clear(31, 0)
    win.after_change()
    ok((30, 0) not in win.model.dups and (31, 0) not in win.model.dups,
       "and their counter clears when they're gone")

    # Ctrl+Shift+Down extends the selection to the data edge; F8 pins row 1.
    grid.select_cell(0, 0)
    QTest.keyClick(grid, Qt.Key.Key_Down,
                   Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    app.processEvents()
    last_col0 = max(row for (row, c) in win.sheet.cells if c == 0)
    ok(grid.selection_bounds() == (0, 0, last_col0, 0), "Ctrl+Shift+Down selects down to the data edge")
    win.grid.set_frozen(True)
    ok(win.grid.frozen.isVisible(), "pinning shows the frozen row strip")
    win.grid.set_frozen(False)
    ok(not win.grid.frozen.isVisible(), "unpinning hides it")

    # Ctrl+A selects just the filled range; Ctrl+End / Ctrl+Home / Ctrl+arrows jump through data.
    win.switch_sheet(0)
    used_r, used_c = win.sheet.used_extent()
    grid.select_cell(5, 1)  # sits on a small leftover data block, apart from the main one
    QTest.keyClick(grid, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    ok(grid.selection_bounds() == (5, 1, 5, 2), "Ctrl+A selects the data block around the cursor")
    QTest.keyClick(grid, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    ok(grid.selection_bounds() == (0, 0, used_r, used_c), "Ctrl+A again selects the whole filled range")
    QTest.keyClick(grid, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    ok(len(grid.selected_cells()) == win.model.rowCount() * win.model.columnCount(),
       "and a third press selects the whole grid")
    QTest.keyClick(grid, Qt.Key.Key_End, Qt.KeyboardModifier.ControlModifier)
    ok(grid.current_cell() == (used_r, used_c), "Ctrl+End jumps to the last filled cell")
    QTest.keyClick(grid, Qt.Key.Key_Home, Qt.KeyboardModifier.ControlModifier)
    ok(grid.current_cell() == (0, 0), "Ctrl+Home returns to A1")
    QTest.keyClick(grid, Qt.Key.Key_Down, Qt.KeyboardModifier.ControlModifier)
    last_in_col = max(r for (r, c) in win.sheet.cells if c == 0)
    ok(grid.current_cell() == (last_in_col, 0), "Ctrl+Down swipes to the last filled row of the column")

    # Background effects: every one spawns and renders a frame without errors.
    from app.effects import EFFECTS
    win.effects.set_effect("Starfield")
    app.processEvents()
    ok(win.effects._effect == "Starfield" and len(win.effects._items) > 0, "starfield spawns its stars")
    for name, _ in EFFECTS:
        win.effects.set_effect(name)
        if name != "None":
            win.effects._tick()
        win.effects.grab()
    ok(True, "every effect renders a frame")
    win.effects.set_effect("Bogus")
    ok(win.effects._effect == "None", "unknown effect names fall back to none")

    print(f"\nall {checks} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
