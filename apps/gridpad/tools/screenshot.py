"""Render the app off-screen to PNGs, for checking the look without a display.

    python tools/screenshot.py out_dir

Writes main.png, empty.png, find.png, tags.png (and a demo workbook used to draw them).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings  # noqa: E402

from app.main import create_app  # noqa: E402
from app.main_window import MainWindow  # noqa: E402
from app.model import Cell, Sheet, Workbook, parse_ref  # noqa: E402


def demo_workbook(path: Path) -> Workbook:
    personal = Sheet("Personal")
    notes = {
        "A1": Cell("To do", bold=True), "B1": Cell("Ideas", bold=True), "C1": Cell("Shopping", bold=True),
        "D1": Cell("Reminders", bold=True), "E1": Cell("Links", bold=True),
        "A2": Cell("Book dentist #admin", check="todo"),
        "B2": Cell("Weekend trip to the coast in Sept?"),
        "C2": Cell("Oat milk, eggs, coffee beans, spinach"),
        "D2": Cell("Mum's birthday — 14 Oct"),
        "E2": Cell("https://example.com/dentist-booking"),
        "A3": Cell("Call plumber re: kitchen leak — quote was £180 #home"),
        "B3": Cell("Learn to make sourdough"),
        "C3": Cell("Printer ink (black)"),
        "D3": Cell("Car MOT due end of month"),
        "A4": Cell("Return library books", check="done"),
        "B4": Cell("Reading list — finish the three half-read ones"),
        "D4": Cell("Router password hint: old street name #home"),
        "A5": Cell("Renew passport — expires March #admin", check="todo"),
    }
    for ref, cell in notes.items():
        personal.cells[parse_ref(ref)] = cell
    work = Sheet("Work")
    work.cells[parse_ref("B7")] = Cell("Dentist appointment — block 3 pm Thu")
    work.cells[parse_ref("A1")] = Cell("Standup moved to 10:30 on Thursdays")
    projects = Sheet("Projects")
    wb = Workbook([personal, work, projects])
    wb.save(path)
    return wb


def shoot(window: MainWindow, app, out: Path) -> None:
    app.processEvents()
    app.processEvents()
    window.grab().save(str(out))
    print("wrote", out)


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "tools" / "shots")
    out_dir.mkdir(parents=True, exist_ok=True)
    app = create_app(["gridpad"])
    settings = QSettings(str(out_dir / "settings.ini"), QSettings.Format.IniFormat)

    demo_path = out_dir / "demo.gridpad"
    wb = demo_workbook(demo_path)
    window = MainWindow(wb, settings)
    window.resize(1280, 800)
    window.show()
    app.processEvents()

    # 1 · main: A3 selected
    window.grid.select_cell(2, 0)
    shoot(window, app, out_dir / "main.png")

    # 1c · editing A3 in place
    window.grid.begin_cell_edit(None)
    shoot(window, app, out_dir / "edit.png")
    window.grid.cancel_edit()

    # 1b · a block selected (A2:C4)
    window.grid.select_range(1, 0, 3, 2)
    shoot(window, app, out_dir / "range.png")
    window.grid.select_cell(2, 0)

    # 3 · find: "dentist"
    window.topbar.search.input.setText("dentist")
    shoot(window, app, out_dir / "find.png")
    window.close_find()

    # 4 · tag filter: #home
    window.grid.select_cell(2, 0)
    window.set_filter("home")
    shoot(window, app, out_dir / "tags.png")
    window.set_filter(None)

    # 2 · first run: brand-new workbook
    window.load_workbook(Workbook())
    shoot(window, app, out_dir / "empty.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
