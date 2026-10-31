# GridPad

A notepad laid out like a spreadsheet. Every cell is a free-text note — no formulas,
no numbers — with the spreadsheet's bones kept: a grid you move around with Tab and
Enter, editing in the cell itself, sheets as tabs, and keyboard shortcuts for the
rest — press F1 for the full list.

Dark, dense, monospace ("Workbench" design).

## Run it

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python gridpad.py
```

(macOS / Linux: `.venv/bin/pip`, `.venv/bin/python`.) Only one dependency: PySide6 (Qt).

On Windows, open it by double-clicking **GridPad.pyw** (or the **GridPad** shortcut) —
no console window. Double-clicking `gridpad.py` also works but opens a terminal.

### Two engines

- **Qt Quick (default, smooth)** — `gridpad_qml.py`, what the **GridPad** shortcut opens. Everything
  is drawn by the GPU scene graph: pixel-smooth eased scrolling, a cursor that glides between cells,
  animations at your display's refresh rate, and the background effects as GPU particles. Python
  sits idle while anything moves.
- **Classic** — `gridpad.py` / `GridPad.pyw` / the **GridPad Classic** shortcut in this folder
  (QtWidgets, painted on the CPU).

Both read and write the same `.gridpad` files and share the same settings (theme, fonts, effect,
separator, last file). Don't keep both open on the same workbook — each autosaves.

Your notes live in one JSON file (`something.gridpad`). The first time, the workbook is
unsaved — press **Ctrl+S** to choose where it goes; after that every edit autosaves.
GridPad reopens the last workbook on launch.

## Keys

| Key | Does |
|---|---|
| Arrows, Tab / Shift+Tab | Move between cells |
| Shift+arrows, Shift+click, or drag | Select a block of cells (click a row/column header for the whole row/column; the corner for everything) |
| Ctrl+A | Select the data block around you — again: the filled range — again: the whole grid |
| Ctrl+End / Ctrl+Home | Jump to the last filled cell / back to A1 |
| Ctrl+arrows | Jump to the edge of your data in that direction |
| Ctrl+Shift+arrows | Select from here to the data edge |
| Ctrl+I (or drop a .csv/.txt on the window) | Import a file — pick the separator, into a new sheet or at the selected cell |
| Ctrl+H | Find and replace (case-insensitive), this sheet or all sheets |
| F8 | Pin row 1 (your labels) while scrolling |
| Right-click a row/column header | Insert, move or delete rows and columns |
| Enter or F2, or just start typing | Edit the cell in place, like Excel |
| Enter (while editing) | Save the note and move down |
| Tab (while editing) | Save the note and move right |
| Shift+Enter (while editing) | New line inside the note |
| Esc | Cancel the edit; clear a filter; close find |
| Delete / Backspace | Clear the cell |
| Ctrl+Z / Ctrl+Y | Undo / redo cell changes (while editing, they undo your typing instead) |
| "Check duplicates and sort" button | Sort rows A–Z / Z–A by the selected column, group rows with repeated values on top, or delete duplicate rows keeping the first (all undoable). Scopes to the contiguous data block around your cell — or exactly your selection — so separate tables on one sheet never disturb each other |
| Duplicate counter | Cells whose value repeats in their column show a live ×N badge, and the status bar counts them |
| Ctrl+C / Ctrl+X | Copy / cut — copied blocks join columns with your export separator (tab until you pick one in Ctrl+E) |
| Ctrl+V | Paste and spread: each line goes down a row; within a line, tabs, commas or `---` split into cells to the right |
| Ctrl+Shift+V | Paste the clipboard as one note, unsplit |
| Ctrl+B | Bold the cell |
| Ctrl+K | Cycle checkbox: none → to do → done |
| Ctrl+L | Toggle a "- " bullet on the current line |
| Ctrl+F | Find across all sheets (Enter next, Shift+Enter back) |
| Ctrl+T | New sheet · Ctrl+PgUp / Ctrl+PgDown switch sheets |
| Ctrl+S / Ctrl+Shift+S | Save / Save as · Ctrl+O open · Ctrl+N new workbook |
| Ctrl+E | Export a sheet to .csv or .txt, choosing what goes between columns (comma, tab, `----`, or anything custom) |
| Ctrl+Shift+T | Tag filter menu (or click a tag pill in a cell) |
| F1 | Every shortcut in one popup |
| Ctrl+, | Theme (8 dark ones), notes font, app font, bold text, a background effect (Starfield, Snow, Fireflies, Rain, Aurora, Embers), and the between-columns separator |
| Ctrl+click a link cell | Open the URL |

Write `#word` anywhere in a note to tag it. Click its pill in the cell, or press
Ctrl+Shift+T for the tag menu, to show only notes with that tag; Esc clears the
filter. Right-click a sheet tab to rename,
duplicate, move or delete it; double-click to rename. Columns size themselves to the
longest note in them (110–440 px); hover a cell that still truncates to read it all.

## Layout of the code

```
gridpad.py            entry point
app/model.py          Workbook / Sheet / Cell, JSON load & save, find
app/grid.py           the grid: table model, painted cells and headers, key handling
app/export.py         the Ctrl+E export dialog (sheet + separator + preview)
app/help.py           the F1 shortcuts popup
app/settings.py       the Ctrl+, appearance dialog (theme + font)
app/main_window.py    top bar, sheet bar, and all the behaviour wired together
app/theme.py          colors, fonts, palette, stylesheet
app/icons.py          stroke icons drawn with QPainter
tools/screenshot.py   renders the app off-screen to PNGs (for checking the look)

gridpad_qml.py        entry point, Qt Quick edition
quick/backend.py      every behaviour (selection, editing, undo, find, sort, files) as a QObject for QML
quick/main.py         app + QML engine setup, the stroke-icon image provider
quick/qml/Main.qml    the window: shortcuts, file dialogs, drag and drop, confirm flows
quick/qml/Grid.qml    TableView grid, headers, pinned row, in-cell editor, smooth wheel/glide
quick/qml/*.qml       CellDelegate, Effects (GPU particles), TopBar, SearchBox, SheetBar, the
                      dialogs, and the shared controls (GP*.qml, Theme singleton)
tools/smoke_test_qml.py  backend + real-window key checks for the Qt Quick edition
tools/qml_harness.py     load any QML file against the real backend, report warnings, grab a PNG
```

## File format

```json
{"app": "gridpad", "version": 1,
 "sheets": [{"name": "Personal",
             "cells": {"A3": {"text": "Call plumber #home", "check": "todo",
                              "created": 1755590000, "edited": 1755590000}}}]}
```

`check` is `"todo"` or `"done"` (absent = no checkbox); `bold` is `true` when set;
tags are simply `#words` inside the text.
