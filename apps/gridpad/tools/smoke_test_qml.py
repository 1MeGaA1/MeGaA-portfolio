"""Scripted behaviour check for the Qt Quick edition, run off-screen:  python tools/smoke_test_qml.py

Part 1 drives quick.backend.Backend directly (the same checks as tools/smoke_test.py, so both
editions provably behave alike). Part 2 loads quick/qml/Main.qml and drives the real window
with key presses, asserting on the model and the saved file.
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

from PySide6.QtCore import QEvent, QSettings, Qt, QtMsgType, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QGuiApplication, QKeyEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from app.model import Workbook, current_region  # noqa: E402
from quick.backend import Backend  # noqa: E402
from quick.main import build_engine, create_app  # noqa: E402

checks = 0
qml_warnings: list[str] = []


def ok(cond: bool, what: str) -> None:
    global checks
    checks += 1
    if not cond:
        raise SystemExit(f"FAIL: {what}")
    print("ok  -", what)


def on_message(kind, _context, message) -> None:
    if kind in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
        qml_warnings.append(message)
        print("WARNING:", message)


def backend_checks(app, tmp: Path) -> None:
    settings = QSettings(str(tmp / "settings.ini"), QSettings.Format.IniFormat)
    path = tmp / "smoke.gridpad"
    wb = Workbook()
    wb.save(path)
    b = Backend(wb, settings)
    sheet = b.sheet
    clip = QGuiApplication.clipboard()

    # Editing: commit moves down, tags parse, autosave writes the file.
    b.setEditing(True)
    ok(b.editing and "Enter saves" in b.statusHint, "editing shows the edit hint")
    b.commitEdit(0, 0, "Hello #home", 1, 0)
    ok(sheet.get(0, 0).text == "Hello #home", "commit saves the note into A1")
    ok(b.current_cell() == (1, 0) and not b.editing, "after saving, the cursor moves down to A2")
    ok(sheet.get(0, 0).tags == ["home"], "#home is parsed as a tag")
    saved = json.loads(path.read_text(encoding="utf-8"))
    ok(saved["sheets"][0]["cells"]["A1"]["text"] == "Hello #home", "autosave wrote the file")
    b.commitEdit(1, 0, "a\nb", 1, 0)
    ok(sheet.get(1, 0).text == "a\nb", "a newline survives in the note")
    b.commitEdit(0, 2, "x", 0, 1)
    ok(sheet.get(0, 2).text == "x" and b.current_cell() == (0, 3), "Tab-commit saves and moves right")
    b.select_range(0, 2, 0, 3)
    b.clearCells()
    ok(sheet.get(0, 2) is None, "a selected block clears")

    # Moves, checkbox, bold.
    b.select_cell(0, 0)
    b.tabMove(True)
    ok(b.current_cell() == (0, 1), "Tab moves one cell right")
    b.tabMove(False)
    b.tabMove(False)
    ok(b.current_cell() == (0, 0), "Shift+Tab at A1 stays put")
    b.select_cell(1, 0)
    b.clearCells()
    ok(sheet.get(1, 0) is None, "Delete clears the cell")
    b.select_cell(0, 0)
    b.toggleCheck()
    ok(sheet.get(0, 0).check == "todo", "Ctrl+K adds a checkbox")
    b.toggleCheck()
    ok(sheet.get(0, 0).check == "done", "Ctrl+K again ticks it")
    b.toggleCheck()
    ok(sheet.get(0, 0).check is None, "Ctrl+K a third time removes it")
    b.toggleBold()
    ok(sheet.get(0, 0).bold, "Ctrl+B bolds the cell")

    # Clipboard.
    clip.setText("one, two ,three\nfour\tfive")
    b.select_cell(5, 0)
    b.paste(True)
    ok([sheet.get(5, c).text for c in range(3)] == ["one", "two", "three"], "paste spreads a comma line across the row")
    ok(sheet.get(6, 0).text == "four" and sheet.get(6, 1).text == "five", "the next line goes down a row; tabs split too")
    clip.setText("left-----middle----right")
    b.select_cell(7, 0)
    b.paste(True)
    ok([sheet.get(7, c).text for c in range(3)] == ["left", "middle", "right"], "runs of dashes split too")
    clip.setText("keep, this\ntogether")
    b.select_cell(8, 0)
    b.paste(False)
    ok(sheet.get(8, 0).text == "keep, this\ntogether" and sheet.get(8, 1) is None, "paste(false) keeps one note")
    b.select_cell(5, 0)
    b.copy()
    ok(clip.text() == "one", "copy takes the cell text")
    b.cut()
    ok(sheet.get(5, 0) is None and clip.text() == "one", "cut removes it")

    # Ranges.
    b.select_cell(6, 0)
    b.extendBy(0, 1)
    b.extendBy(1, 0)
    ok(b.selection_bounds() == (6, 0, 7, 1) and b._selected_count() == 4, "Shift+arrows select a 2x2 block")
    ok((b.selTop, b.selLeft, b.selBottom, b.selRight) == (6, 0, 7, 1), "the selection properties follow")
    b.copy()
    ok(clip.text() == "four\tfive\nleft\tmiddle", "copying a block gives tab-separated rows")
    b.select_cell(10, 2)
    b.paste(True)
    ok(sheet.get(10, 2).text == "four" and sheet.get(11, 3).text == "middle", "pasting a block keeps its shape")
    ok(b.selection_bounds() == (10, 2, 11, 3), "the pasted block is selected afterwards")
    b.toggleBold()
    ok(all(sheet.get(r, c).bold for r in (10, 11) for c in (2, 3)), "Ctrl+B bolds every cell in the block")
    b.clearCells()
    ok(all(sheet.get(r, c) is None for r in (10, 11) for c in (2, 3)), "Delete clears the whole block")
    clip.setText("same")
    b.select_range(12, 0, 12, 2)
    b.paste(True)
    ok([sheet.get(12, c).text for c in range(3)] == ["same"] * 3, "one value pasted into a range fills it")
    b.select_range(6, 0, 7, 1)
    b.cut()
    ok(sheet.get(6, 0) is None and sheet.get(7, 1) is None and sheet.get(7, 2).text == "right",
       "cut takes just the block")
    b.copy_sep = "----"
    sheet.set_text(15, 0, "aa")
    sheet.set_text(15, 1, "bb")
    b.select_range(15, 0, 15, 1)
    b.copy()
    ok(clip.text() == "aa----bb", "block copy uses the chosen ---- separator")
    b.select_cell(17, 0)
    b.paste(True)
    ok(sheet.get(17, 0).text == "aa" and sheet.get(17, 1).text == "bb", "and pastes back as separate cells")
    b.copy_sep = "\t"

    # Find across sheets.
    idx = b.workbook.add_sheet("Work")
    b.switchSheet(idx)
    b.sheet.set_text(2, 1, "hello again")
    b.after_change(2, 1)
    b.switchSheet(0)
    b.setQuery("hello")
    ok(len(b.matches) == 2 and b.matchLabel == "1 of 2", "find sees matches on both sheets")
    ok(b._current_match == (0, 0) and b.match_kind((0, 0)) == 2, "the first match is the one on the current sheet")
    b.stepMatch(1)
    ok(b.current == idx and b.current_cell() == (2, 1), "Enter steps to the match on the other sheet")
    cleared = []
    b.searchCleared.connect(lambda: cleared.append(True))
    b.closeFind()
    ok(b.query == "" and cleared, "closing find clears the query and the box")

    # Tag filter.
    b.switchSheet(0)
    b.setFilter("home")
    ok(b.filterTag == "home" and "Filter: #home" in b.statusHint, "filtering by a tag")
    b.escape()
    ok(b.filterTag == "", "Esc clears the filter")
    b.setFilter("home")
    b.setFilter("home")
    ok(b.filterTag == "", "the same tag again clears it")

    # Sheets.
    renames = []
    b.renameRequested.connect(lambda i, name: renames.append((i, name)))
    b.duplicateSheet(0)
    ok(len(b.workbook.sheets) == 3 and b.sheet.get(0, 0).text == "Hello #home", "duplicate copies the notes")
    b.moveSheet(1, 1)
    ok(b.workbook.sheets[2].name.endswith("copy"), "move right reorders sheets")
    b.deleteSheet(2)
    ok(len(b.workbook.sheets) == 2 and b.sheetNames == ["Sheet 1", "Work"], "delete removes a sheet")
    b.addSheet()
    ok(renames and renames[-1][0] == 2 and b.currentSheet == 2, "a new sheet asks to be renamed")
    b.renameSheet(2, "  Ideas ")
    ok(b.sheetNames[2] == "Ideas", "rename trims and applies")
    b.deleteSheet(2)
    b.switchSheet(0)

    again = Workbook.load(path)
    ok([s.name for s in again.sheets] == [s.name for s in b.workbook.sheets], "sheet names survive a reload")
    ok(again.sheets[0].get(0, 0).text == "Hello #home" and again.sheets[0].get(0, 0).bold,
       "cell text and bold survive a reload")

    # Auto-fit.
    b.sheet.set_text(20, 4, "a really long note that should stretch this column quite a lot indeed")
    b.after_change(20, 4)
    ok(b.colWidths[4] > 300, "a long note widens its column")
    b.sheet.clear(20, 4)
    b.after_change(20, 4)
    ok(b.colWidths[4] == 180 and b.colWidths[9] == 180, "clearing shrinks it back; empty columns keep 180")
    ok(len(b.colWidths) == b.model.columnCount(), "one width per column")

    # Undo / redo.
    b.select_cell(21, 0)
    b.commitEdit(21, 0, "undo me", 1, 0)
    b.undo()
    ok(sheet.get(21, 0) is None, "undo takes the note back out")
    b.redo()
    ok(sheet.get(21, 0) is not None and sheet.get(21, 0).text == "undo me", "redo brings it back")
    b.undo()
    b.select_cell(21, 0)
    clip.setText("p1, p2")
    b.paste(True)
    b.undo()
    ok(sheet.get(21, 0) is None and sheet.get(21, 1) is None, "undo reverts a whole paste")

    # Growth.
    ok(b.model.rowCount() == 200 and b.model.columnCount() == 26, "a light sheet shows the base 200 x 26 grid")
    b.select_cell(0, 25)
    clip.setText("z1\tz2\tz3")
    b.paste(True)
    ok(sheet.get(0, 27).text == "z3" and b.model.columnCount() >= 32 and len(b.colWidths) >= 32,
       "pasting past Z grows new columns (and their widths)")
    ok(b.first_row.columnCount() == b.model.columnCount(), "the pinned row grows with it")
    b.undo()

    # Sort / duplicates / islands / Ctrl+A ladder.
    sort_idx = b.workbook.add_sheet("SortT")
    b.switchSheet(sort_idx)
    for i, v in enumerate(["b@x.com", "a@x.com", "c@x.com", "a@x.com", "b@x.com", "d@x.com"]):
        b.sheet.set_text(i, 0, v)
        b.sheet.set_text(i, 1, f"pw{i}")
    b.after_change()
    b.select_cell(0, 0)
    info = b.sortMenuInfo()
    ok(info["ok"] and info["letter"] == "A", "the sort menu knows the column")
    b.sortRows(False)
    ok([b.sheet.get(r, 0).text for r in range(6)]
       == ["a@x.com", "a@x.com", "b@x.com", "b@x.com", "c@x.com", "d@x.com"], "sort A-Z orders rows")
    ok(b.sheet.get(0, 1).text == "pw1", "whole rows move together")
    b.groupDuplicates()
    ok([b.sheet.get(r, 0).text for r in (4, 5)] == ["c@x.com", "d@x.com"], "duplicates grouped on top")
    b.undo()
    b.undo()
    ok([b.sheet.get(r, 0).text for r in range(6)]
       == ["b@x.com", "a@x.com", "c@x.com", "a@x.com", "b@x.com", "d@x.com"], "two undos restore the order")
    b.select_cell(40, 5)
    ok(not b.sortMenuInfo()["ok"] and "inside your data" in b.statusHint, "sorting outside data asks for a cell")

    island_idx = b.workbook.add_sheet("IslandT")
    b.switchSheet(island_idx)
    for i, v in enumerate(["b", "a", "b"]):
        b.sheet.set_text(i, 0, v)
        b.sheet.set_text(i, 1, f"p{i}")
    for i, v in enumerate(["z", "y"]):
        b.sheet.set_text(i, 3, v)
    b.after_change()
    ok(current_region(b.sheet, 0, 0) == (0, 0, 2, 1), "the island around A1 is detected")
    b.select_cell(0, 0)
    b.selectAllLadder()
    ok(b.selection_bounds() == (0, 0, 2, 1), "Ctrl+A selects the island first")
    b.selectAllLadder()
    ok(b.selection_bounds() == (0, 0, 2, 3), "Ctrl+A again selects the whole filled range")
    b.selectAllLadder()
    ok(b._selected_count() == b.model.rowCount() * b.model.columnCount(), "a third press selects the whole grid")
    b.select_cell(1, 0)
    b.dedupe()
    ok(b.sheet.get(2, 0) is None or b.sheet.get(2, 0).text != "b", "dedupe inside the island")
    ok(b.sheet.get(0, 3).text == "z", "the second island is untouched")
    b.undo()

    # Rows / columns from the header menus.
    b.select_cell(0, 0)
    b.rowAction("above", 0)
    ok(b.sheet.get(0, 0) is None and b.sheet.get(1, 0).text == "b", "insert row above")
    b.undo()
    b.colAction("left", 0)
    ok(b.sheet.get(0, 1).text == "b", "insert column left")
    b.undo()
    b.colAction("delete", 2)
    ok(b.sheet.get(0, 2).text == "z", "delete column C pulls D left")
    b.undo()

    # Jumps.
    b.switchSheet(0)
    used_r, used_c = b.sheet.used_extent()
    scrolls = []
    b.scrollRequested.connect(lambda r, c, glide: scrolls.append((r, c, glide)))
    b.ctrlEnd()
    ok(b.current_cell() == (used_r, used_c) and scrolls[-1] == (used_r, used_c, True), "Ctrl+End glides to the last cell")
    b.ctrlHome()
    ok(b.current_cell() == (0, 0), "Ctrl+Home returns to A1")
    b.jump("down")
    last_in_col = max(r for (r, c) in b.sheet.cells if c == 0)
    ok(b.current_cell() == (last_in_col, 0), "Ctrl+Down swipes to the last filled row of the column")
    b.select_cell(0, 0)
    b.jumpExtend("down")
    ok(b.selection_bounds() == (0, 0, last_in_col, 0), "Ctrl+Shift+Down selects to the data edge")
    b.selectRows(3, 5, 2)
    ok(b.selection_bounds() == (3, 0, 5, b.model.columnCount() - 1), "header drag selects whole rows")
    b.selectCols(1, 1, 0)
    ok(b.selection_bounds() == (0, 1, b.model.rowCount() - 1, 1), "header click selects a whole column")

    # Duplicate counter, freeze, effects, settings.
    b.sheet.set_text(30, 0, "twin")
    b.sheet.set_text(31, 0, "twin")
    b.select_cell(30, 0)
    b.after_change()
    ok(b.model.dups.get((30, 0)) == 2 and "duplicates" in b.statusNotes, "duplicates counted live")
    b.sheet.clear(30, 0)
    b.sheet.clear(31, 0)
    b.after_change()
    b.setFreeze(False)
    ok(not b.freeze, "row 1 unpinned")
    b.toggleFreeze()
    ok(b.freeze and settings.value("freeze") in (True, "true"), "F8 pins row 1 and remembers it")
    state = b.settingsState()
    b.applySettings("Nord", state["mono"], state["sans"], True, "Snow", 1, "")
    ok(b.palette.name == "Nord" and b.palette.bold and b.effect == "Snow" and b.copy_sep == "\t",
       "Appearance applies theme, bold, effect and separator live")
    b.applySettings("Workbench", state["mono"], state["sans"], False, "Bogus", 3, " | ")
    ok(b.effect == "None" and b.copy_sep == " | ", "unknown effects fall back to none; custom separator kept")
    b.copy_sep = "\t"

    # Import / export / replace.
    csv_path = tmp / "people.csv"
    csv_path.write_bytes(b"name,mail\nann,a@x\nbob,b@x\n")
    ready = []
    b.importReady.connect(lambda name, ref: ready.append((name, ref)))
    b.beginImport(str(csv_path))
    ok(ready and ready[-1][0] == "people.csv", "import reads the file and asks for the dialog")
    preview = b.importPreview(0, "")
    ok(preview["summary"].startswith("3 rows × 2 columns"), "import preview counts rows and columns")
    before_sheets = len(b.workbook.sheets)
    b.finishImport(0, "", True)
    ok(len(b.workbook.sheets) == before_sheets + 1 and b.sheet.get(2, 1).text == "b@x", "import into a new sheet")
    target = b.exportTarget(b.current, 0, "")
    ok(target["suffix"] == ".csv" and target["file"].endswith("people.csv"), "export suggests name.csv")
    out = tmp / "out.csv"
    b.exportTo(b.current, out.as_uri())
    ok(out.read_text(encoding="utf-8").startswith("name,mail\nann,a@x"), "export writes the sheet")
    b.replaceAll("@x", "@y", False)
    ok(b.sheet.get(1, 1).text == "a@y", "replace all in this sheet")
    b.undo()
    ok(b.sheet.get(1, 1).text == "a@x", "and it undoes")

    # Files: save-as through the dialog path, discard check, drop classification.
    nb = Backend(Workbook(), settings)
    asked = []
    nb.saveAsRequested.connect(lambda: asked.append(True))
    nb.commitEdit(0, 0, "unsaved", 0, 0)
    ok(nb.needsDiscardConfirm() and not nb.save() and asked, "saving a new workbook asks for a file")
    target_file = tmp / "fresh"
    ok(nb.saveTo(target_file.as_uri()) and (tmp / "fresh.gridpad").exists() and not nb.needsDiscardConfirm(),
       "saveTo adds .gridpad and the workbook is safe")
    drop = nb.classifyDrop([csv_path.as_uri(), "file:///x/y.bin"])
    ok(drop["kind"] == "import", "dropping a csv imports it")
    nb.newWorkbook()
    ok(nb.workbook.total_notes() == 0 and nb.fileName == "untitled.gridpad", "new workbook starts empty")
    nb.openPath(str(tmp / "fresh.gridpad"))
    ok(nb.sheet.get(0, 0).text == "unsaved", "openPath loads a workbook")
    nb.saveWindowGeometry(10, 20, 1000, 700, False)
    ok(nb.windowGeometry() == [10, 20, 1000, 700, False], "window geometry round-trips")


def window_checks(app, tmp: Path) -> None:
    settings = QSettings(str(tmp / "settings2.ini"), QSettings.Format.IniFormat)
    path = tmp / "ui.gridpad"
    wb = Workbook()
    wb.save(path)
    backend = Backend(wb, settings)
    engine = build_engine(backend)
    ok(bool(engine.rootObjects()), "Main.qml loads")
    win = engine.rootObjects()[0]
    win.show()
    QTest.qWait(300)
    win.requestActivate()
    QTest.qWait(100)
    sheet = backend.sheet

    def keys(text: str) -> None:
        # QTest.keyClicks only takes widgets, and QTest.keyClick lowercases Shift+letters,
        # so type into the QQuickWindow with key events that carry the real character.
        for ch in text:
            code = Qt.Key(ord(ch.upper()))
            mods = Qt.KeyboardModifier.ShiftModifier if ch.isupper() else Qt.KeyboardModifier.NoModifier
            for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                QGuiApplication.sendEvent(win, QKeyEvent(kind, code, mods, ch))
        QTest.qWait(30)

    def key(k, mods=Qt.KeyboardModifier.NoModifier) -> None:
        QTest.keyClick(win, k, mods)
        QTest.qWait(30)

    keys("H")
    ok(backend.editing, "typing opens the in-cell editor")
    keys("ello #home")
    key(Qt.Key.Key_Return)
    ok(sheet.get(0, 0) is not None and sheet.get(0, 0).text == "Hello #home", "Enter saves the note into A1")
    ok(backend.current_cell() == (1, 0), "and the cursor moves down")
    saved = json.loads(path.read_text(encoding="utf-8"))
    ok(saved["sheets"][0]["cells"]["A1"]["text"] == "Hello #home", "autosave wrote the file")
    keys("a")
    key(Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    keys("b")
    key(Qt.Key.Key_Return)
    ok(sheet.get(1, 0).text == "a\nb", "Shift+Enter inserts a new line")
    backend.select_cell(1, 0)
    key(Qt.Key.Key_F2)
    keys("zzz")
    key(Qt.Key.Key_Escape)
    ok(sheet.get(1, 0).text == "a\nb" and not backend.editing, "Esc cancels the edit")
    backend.select_cell(0, 2)
    keys("x")
    key(Qt.Key.Key_Tab)
    ok(sheet.get(0, 2).text == "x" and backend.current_cell() == (0, 3), "Tab saves and moves right")
    key(Qt.Key.Key_Left)
    ok(backend.current_cell() == (0, 2), "arrow keys move the cursor")
    key(Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    ok(backend.selection_bounds() == (0, 2, 0, 3), "Shift+arrow extends the selection")
    key(Qt.Key.Key_Delete)
    ok(sheet.get(0, 2) is None, "Delete clears the selection")
    backend.select_cell(0, 0)
    key(Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
    ok(sheet.get(0, 0).check == "todo", "Ctrl+K adds a checkbox")
    key(Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier)
    ok(sheet.get(0, 0).bold, "Ctrl+B bolds the cell")
    key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    ok(not sheet.get(0, 0).bold, "Ctrl+Z undoes it")
    key(Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    ok(sheet.get(0, 0).bold, "Ctrl+Y redoes it")
    QGuiApplication.clipboard().setText("p1, p2")
    backend.select_cell(4, 0)
    key(Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    ok(sheet.get(4, 1) is not None and sheet.get(4, 1).text == "p2", "Ctrl+V spreads across cells")
    key(Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    ok(backend._selected_count() > 1, "Ctrl+A selects the data block")
    key(Qt.Key.Key_F8)
    ok(not backend.freeze, "F8 toggles the pinned row")
    win.close()
    QTest.qWait(100)


def main() -> int:
    qInstallMessageHandler(on_message)
    app = create_app(["gridpad"])
    tmp = Path(tempfile.mkdtemp())
    backend_checks(app, tmp)
    window_checks(app, tmp)
    ok(not qml_warnings, "no QML warnings")
    print(f"\nall {checks} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
