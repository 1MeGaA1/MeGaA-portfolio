"""Data model for GridPad: a workbook holds sheets, a sheet holds sparse text cells.

Saved as one JSON file (``*.gridpad``)::

    {"app": "gridpad", "version": 1,
     "sheets": [{"name": "Personal",
                 "cells": {"A3": {"text": "Call plumber #home", "check": "todo", ...}}}]}
"""
from __future__ import annotations

import copy
import csv
import io
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

FILE_SUFFIX = ".gridpad"
ROWS = 200  # minimum grid size shown; the grid grows with content
COLS = 26
MAX_ROWS = 20000  # hard safety caps for pasted data
MAX_COLS = 500

TAG_RE = re.compile(r"(?<![\w#])#([A-Za-z0-9_][\w-]*)")
URL_RE = re.compile(r"https?://\S+")


def col_name(col: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    name = ""
    col += 1
    while col:
        col, rem = divmod(col - 1, 26)
        name = chr(65 + rem) + name
    return name


def cell_ref(row: int, col: int) -> str:
    return f"{col_name(col)}{row + 1}"


def parse_ref(ref: str) -> tuple[int, int]:
    """'A3' -> (2, 0)."""
    m = re.fullmatch(r"([A-Z]+)(\d+)", ref.strip().upper())
    if not m:
        raise ValueError(f"bad cell reference: {ref!r}")
    letters, digits = m.groups()
    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch) - 64)
    return int(digits) - 1, col - 1


@dataclass
class Cell:
    text: str = ""
    bold: bool = False
    check: str | None = None  # None = no checkbox, "todo" or "done"
    created: float = field(default_factory=time.time)
    edited: float = field(default_factory=time.time)

    @property
    def tags(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for tag in TAG_RE.findall(self.text):
            tag = tag.lower()
            if tag not in seen:
                seen.add(tag)
                out.append(tag)
        return out

    @property
    def is_link(self) -> bool:
        return bool(URL_RE.fullmatch(self.text.strip()))

    @property
    def is_empty(self) -> bool:
        return not self.text and self.check is None

    def to_json(self) -> dict:
        data: dict = {"text": self.text}
        if self.bold:
            data["bold"] = True
        if self.check:
            data["check"] = self.check
        data["created"] = round(self.created)
        data["edited"] = round(self.edited)
        return data

    @classmethod
    def from_json(cls, data: dict) -> "Cell":
        now = time.time()
        check = data.get("check")
        return cls(
            text=str(data.get("text", "")),
            bold=bool(data.get("bold", False)),
            check=check if check in ("todo", "done") else None,
            created=float(data.get("created", now)),
            edited=float(data.get("edited", now)),
        )


class Sheet:
    def __init__(self, name: str, cells: dict[tuple[int, int], Cell] | None = None):
        self.name = name
        self.cells: dict[tuple[int, int], Cell] = cells if cells is not None else {}

    def get(self, row: int, col: int) -> Cell | None:
        return self.cells.get((row, col))

    def ensure(self, row: int, col: int) -> Cell:
        cell = self.cells.get((row, col))
        if cell is None:
            cell = Cell()
            self.cells[(row, col)] = cell
        return cell

    def set_text(self, row: int, col: int, text: str) -> Cell | None:
        """Write text into a cell; an emptied cell is dropped. Returns the cell or None."""
        text = text.strip("\n")
        cell = self.cells.get((row, col))
        if cell is None:
            if not text:
                return None
            cell = Cell(text=text)
            self.cells[(row, col)] = cell
            return cell
        if cell.text != text:
            cell.text = text
            cell.edited = time.time()
        if cell.is_empty:
            del self.cells[(row, col)]
            return None
        return cell

    def clear(self, row: int, col: int) -> None:
        self.cells.pop((row, col), None)

    def prune(self, row: int, col: int) -> None:
        cell = self.cells.get((row, col))
        if cell is not None and cell.is_empty:
            del self.cells[(row, col)]

    def note_count(self) -> int:
        return sum(1 for cell in self.cells.values() if cell.text)

    def used_extent(self) -> tuple[int, int]:
        """(last filled row, last filled column), or (-1, -1) when the sheet is empty."""
        if not self.cells:
            return (-1, -1)
        return (max(r for r, _ in self.cells), max(c for _, c in self.cells))

    def tag_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for cell in self.cells.values():
            for tag in cell.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return counts

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "cells": {cell_ref(r, c): cell.to_json() for (r, c), cell in sorted(self.cells.items())},
        }

    @classmethod
    def from_json(cls, data: dict) -> "Sheet":
        cells: dict[tuple[int, int], Cell] = {}
        for ref, cell_data in (data.get("cells") or {}).items():
            try:
                row, col = parse_ref(ref)
            except ValueError:
                continue
            if not (0 <= row < MAX_ROWS and 0 <= col < MAX_COLS):
                continue
            cell = Cell.from_json(cell_data or {})
            if not cell.is_empty:
                cells[(row, col)] = cell
        return cls(str(data.get("name") or "Sheet"), cells)


@dataclass
class Match:
    sheet: int
    row: int
    col: int
    cell: Cell


class Workbook:
    def __init__(self, sheets: list[Sheet] | None = None, path: Path | None = None):
        self.sheets: list[Sheet] = sheets or [Sheet("Sheet 1")]
        self.path: Path | None = path
        self.dirty = False

    # -- file -------------------------------------------------------------
    @property
    def name(self) -> str:
        return self.path.name if self.path else "untitled" + FILE_SUFFIX

    @classmethod
    def load(cls, path: str | Path) -> "Workbook":
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("not a GridPad file")
        sheets = [Sheet.from_json(s) for s in data.get("sheets", []) if isinstance(s, dict)]
        return cls(sheets or [Sheet("Sheet 1")], path)

    def save(self, path: str | Path | None = None) -> None:
        if path is not None:
            self.path = Path(path)
        if self.path is None:
            raise ValueError("workbook has no path yet")
        data = {"app": "gridpad", "version": 1, "sheets": [s.to_json() for s in self.sheets]}
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)
        self.dirty = False

    # -- stats ------------------------------------------------------------
    def total_notes(self) -> int:
        return sum(s.note_count() for s in self.sheets)

    def tag_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for sheet in self.sheets:
            for tag, n in sheet.tag_counts().items():
                counts[tag] = counts.get(tag, 0) + n
        return counts

    # -- sheets -----------------------------------------------------------
    def unique_sheet_name(self, base: str) -> str:
        names = {s.name for s in self.sheets}
        if base not in names:
            return base
        n = 2
        while f"{base} {n}" in names:
            n += 1
        return f"{base} {n}"

    def add_sheet(self, name: str | None = None, index: int | None = None) -> int:
        sheet = Sheet(self.unique_sheet_name(name or "Sheet"))
        if name is None:
            sheet.name = self.unique_sheet_name(f"Sheet {len(self.sheets) + 1}")
        if index is None:
            index = len(self.sheets)
        self.sheets.insert(index, sheet)
        self.dirty = True
        return index

    def duplicate_sheet(self, index: int) -> int:
        src = self.sheets[index]
        dup = Sheet(self.unique_sheet_name(f"{src.name} copy"), copy.deepcopy(src.cells))
        self.sheets.insert(index + 1, dup)
        self.dirty = True
        return index + 1

    def move_sheet(self, index: int, delta: int) -> int:
        new_index = max(0, min(len(self.sheets) - 1, index + delta))
        if new_index != index:
            sheet = self.sheets.pop(index)
            self.sheets.insert(new_index, sheet)
            self.dirty = True
        return new_index

    def remove_sheet(self, index: int) -> None:
        if len(self.sheets) <= 1:
            raise ValueError("a workbook needs at least one sheet")
        del self.sheets[index]
        self.dirty = True

    # -- clipboard --------------------------------------------------------
    def paste_block(self, sheet_index: int, row: int, col: int, block: list[list[str]]) -> int:
        """Write a block of values with its top-left at (row, col), replacing what was there.

        Empty values clear their target cell. Returns how many non-empty values were written.
        """
        sheet = self.sheets[sheet_index]
        written = 0
        for r, parts in enumerate(block):
            for c, value in enumerate(parts):
                rr, cc = row + r, col + c
                if rr >= MAX_ROWS or cc >= MAX_COLS:
                    continue
                sheet.set_text(rr, cc, value)
                if value:
                    written += 1
        self.dirty = True
        return written

    def paste(self, sheet_index: int, row: int, col: int, text: str, spread: bool = True) -> int:
        """Write clipboard text starting at (row, col); returns how many cells were written."""
        block = split_paste(text) if spread else [[text.strip("\r\n")]]
        return self.paste_block(sheet_index, row, col, block)

    # -- search -----------------------------------------------------------
    def find(self, query: str) -> list[Match]:
        query = query.strip().lower()
        if not query:
            return []
        out: list[Match] = []
        for si, sheet in enumerate(self.sheets):
            for (row, col), cell in sorted(sheet.cells.items()):
                if query in cell.text.lower():
                    out.append(Match(si, row, col, cell))
        return out


DASH_RUN = re.compile(r"-{3,}")


def split_paste(text: str) -> list[list[str]]:
    """Turn pasted text into rows of cells.

    Lines become rows. Within a line, tabs win (that is what spreadsheets put on the
    clipboard), then commas (quoted CSV fields stay whole), then runs of three or more
    dashes; anything else is one cell. Pieces are trimmed.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    rows: list[list[str]] = []
    for line in text.split("\n"):
        if "\t" in line:
            parts = next(csv.reader([line], dialect="excel-tab"))
        elif "," in line:
            parts = next(csv.reader([line], skipinitialspace=True))
        elif DASH_RUN.search(line):
            parts = DASH_RUN.split(line)
        else:
            parts = [line]
        rows.append([p.strip() for p in parts])
    return rows


def export_text(sheet: "Sheet", sep: str) -> str:
    """The sheet's used range as delimited text: one line per row, cells joined by sep.

    A comma separator produces proper CSV (quoted fields, newlines kept); any other
    separator joins plainly, with newlines inside notes flattened to spaces.
    """
    if not sheet.cells:
        return ""
    max_row = max(r for r, _ in sheet.cells)
    max_col = max(c for _, c in sheet.cells)
    grid = [["" for _ in range(max_col + 1)] for _ in range(max_row + 1)]
    for (r, c), cell in sheet.cells.items():
        grid[r][c] = cell.text
    if sep == ",":
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerows(grid)
        return buf.getvalue().rstrip("\n")
    return "\n".join(sep.join(value.replace("\n", " ") for value in row) for row in grid)


Box = tuple[int, int, int, int]  # top, left, bottom, right — a selected block


def _box_or_all(sheet: Sheet, box: Box | None) -> Box:
    if box is not None:
        return box
    max_r, max_c = sheet.used_extent()
    return (0, 0, max(max_r, 0), max(max_c, 0))


def _box_rows(sheet: Sheet, box: Box) -> dict[int, dict[int, Cell]]:
    top, left, bottom, right = box
    rows: dict[int, dict[int, Cell]] = {r: {} for r in range(top, bottom + 1)}
    for (r, c), cell in sheet.cells.items():
        if top <= r <= bottom and left <= c <= right:
            rows[r][c] = cell
    return rows


def _box_rebuild(sheet: Sheet, box: Box, rows: dict[int, dict[int, Cell]], order: list[int]) -> None:
    top, left, bottom, right = box
    for r in range(top, bottom + 1):
        for c in range(left, right + 1):
            sheet.cells.pop((r, c), None)
    for i, old_r in enumerate(order):
        for c, cell in rows[old_r].items():
            sheet.cells[(top + i, c)] = cell


def _col_value(rows: dict[int, dict[int, Cell]], col: int):
    def value(r: int) -> str:
        cell = rows[r].get(col)
        return cell.text.strip().lower() if cell is not None and cell.text else ""
    return value


def sort_rows(sheet: Sheet, col: int, reverse: bool = False, box: Box | None = None) -> int:
    """Reorder rows by the text in one column — the whole sheet, or just `box`, Excel-style.

    Cells outside the box never move; rows with nothing in the sort column go last.
    Returns how many rows had something to sort.
    """
    box = _box_or_all(sheet, box)
    rows = _box_rows(sheet, box)
    value = _col_value(rows, col)
    filled = sorted((r for r in rows if value(r)), key=lambda r: (value(r), r))
    if reverse:
        filled.reverse()
    empty = sorted(r for r in rows if not value(r))
    _box_rebuild(sheet, box, rows, filled + empty)
    return len(filled)


def duplicates_first(sheet: Sheet, col: int, box: Box | None = None) -> tuple[int, int]:
    """Group rows whose value in `col` repeats up top (biggest groups first), sheet-wide or in `box`.

    Below the duplicates come the unique values A–Z, then rows with nothing in that column.
    Returns (how many values repeat, how many rows hold them).
    """
    box = _box_or_all(sheet, box)
    rows = _box_rows(sheet, box)
    value = _col_value(rows, col)
    counts: dict[str, int] = {}
    for r in rows:
        v = value(r)
        if v:
            counts[v] = counts.get(v, 0) + 1
    dup_values = {v for v, n in counts.items() if n > 1}
    originals = sorted(rows)
    dup_rows = [r for r in originals if value(r) in dup_values]
    dup_rows.sort(key=lambda r: (-counts[value(r)], value(r), r))
    unique_rows = sorted((r for r in originals if value(r) and value(r) not in dup_values),
                         key=lambda r: (value(r), r))
    empty_rows = [r for r in originals if not value(r)]
    _box_rebuild(sheet, box, rows, dup_rows + unique_rows + empty_rows)
    return len(dup_values), len(dup_rows)


def dedupe_rows(sheet: Sheet, col: int, box: Box | None = None) -> tuple[int, int]:
    """Delete rows whose value in `col` already appeared above — the first of each stays.

    Scoped to `box` when given (cells outside it never move). Rows with nothing in that
    column are never touched. Returns (rows deleted, values that repeated).
    """
    box = _box_or_all(sheet, box)
    rows = _box_rows(sheet, box)
    value = _col_value(rows, col)
    seen: set[str] = set()
    keep: list[int] = []
    removed = 0
    values_hit: set[str] = set()
    for r in sorted(rows):
        v = value(r)
        if v and v in seen:
            removed += 1
            values_hit.add(v)
            continue
        if v:
            seen.add(v)
        keep.append(r)
    _box_rebuild(sheet, box, rows, keep)
    return removed, len(values_hit)


def current_region(sheet: Sheet, row: int, col: int) -> Box:
    """The contiguous block of data around a cell — Excel's "current region".

    Grows a rectangle from the cell until it is surrounded by empty rows and columns.
    """
    top = bottom = row
    left = right = col
    changed = True
    while changed:
        changed = False
        for (r, c) in sheet.cells:
            if top - 1 <= r <= bottom + 1 and left - 1 <= c <= right + 1:
                if not (top <= r <= bottom and left <= c <= right):
                    top, bottom = min(top, r), max(bottom, r)
                    left, right = min(left, c), max(right, c)
                    changed = True
    return (top, left, bottom, right)


def duplicate_counts(sheet: Sheet) -> dict[tuple[int, int], int]:
    """Cells whose text repeats within their own column → how many times that value appears.

    Matching ignores upper/lower case and surrounding spaces; empty cells never count.
    """
    per_value: dict[tuple[int, str], list[tuple[int, int]]] = {}
    for (r, c), cell in sheet.cells.items():
        v = cell.text.strip().lower()
        if v:
            per_value.setdefault((c, v), []).append((r, c))
    out: dict[tuple[int, int], int] = {}
    for positions in per_value.values():
        if len(positions) > 1:
            for rc in positions:
                out[rc] = len(positions)
    return out


def insert_row(sheet: Sheet, row: int) -> None:
    sheet.cells = {(r + 1 if r >= row else r, c): cell for (r, c), cell in sheet.cells.items()}


def delete_row(sheet: Sheet, row: int) -> None:
    sheet.cells = {(r - 1 if r > row else r, c): cell for (r, c), cell in sheet.cells.items() if r != row}


def move_row(sheet: Sheet, row: int, delta: int) -> int:
    other = row + delta
    if other < 0 or other >= MAX_ROWS:
        return row
    swap = {row: other, other: row}
    sheet.cells = {(swap.get(r, r), c): cell for (r, c), cell in sheet.cells.items()}
    return other


def insert_col(sheet: Sheet, col: int) -> None:
    sheet.cells = {(r, c + 1 if c >= col else c): cell for (r, c), cell in sheet.cells.items()}


def delete_col(sheet: Sheet, col: int) -> None:
    sheet.cells = {(r, c - 1 if c > col else c): cell for (r, c), cell in sheet.cells.items() if c != col}


def move_col(sheet: Sheet, col: int, delta: int) -> int:
    other = col + delta
    if other < 0 or other >= MAX_COLS:
        return col
    swap = {col: other, other: col}
    sheet.cells = {(r, swap.get(c, c)): cell for (r, c), cell in sheet.cells.items()}
    return other


def replace_in_sheet(sheet: Sheet, find: str, replacement: str) -> tuple[int, int]:
    """Case-insensitive text replace across every cell; returns (matches replaced, cells changed)."""
    if not find:
        return (0, 0)
    pattern = re.compile(re.escape(find), re.IGNORECASE)
    matches = 0
    cells_changed = 0
    for rc in list(sheet.cells):
        cell = sheet.cells[rc]
        new_text, count = pattern.subn(replacement, cell.text)
        if count:
            matches += count
            cells_changed += 1
            sheet.set_text(rc[0], rc[1], new_text)
    return matches, cells_changed


def parse_delimited(text: str, sep: str) -> list[list[str]]:
    """A whole file into rows of cells. sep is 'auto', ',', a tab, or any literal string."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not text:
        return []
    if sep == "auto":
        return split_paste(text)
    if sep in (",", "\t"):
        dialect = "excel" if sep == "," else "excel-tab"
        return [[p.strip() for p in row] for row in csv.reader(io.StringIO(text), dialect=dialect)]
    return [[p.strip() for p in line.split(sep)] for line in text.split("\n")]


def join_block(block: list[list[str]], sep: str = "\t") -> str:
    """Cells to clipboard text: one row per line, columns joined by sep.

    Tab and comma produce proper spreadsheet clipboard text (quoted fields); any other
    separator joins plainly, with newlines inside notes flattened to spaces.
    """
    if sep in ("\t", ","):
        buf = io.StringIO()
        writer = csv.writer(buf, dialect="excel-tab" if sep == "\t" else "excel", lineterminator="\n")
        for row in block:
            writer.writerow(row)
        return buf.getvalue().rstrip("\n")
    return "\n".join(sep.join(value.replace("\n", " ") for value in row) for row in block)
