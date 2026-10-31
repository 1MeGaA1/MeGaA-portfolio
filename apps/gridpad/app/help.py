"""The F1 popup: every keyboard shortcut on one card."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QGridLayout, QLabel, QPushButton, QVBoxLayout

from . import theme

KEYS: list[tuple[str, str]] = [
    ("Arrows · Tab", "Move between cells"),
    ("Shift+arrows · Shift+click · drag", "Select a block (headers select rows and columns)"),
    ("Ctrl+A", "Select the data block around you · again: the filled range · again: the whole grid"),
    ("Ctrl+End · Ctrl+Home", "Jump to the last filled cell · back to A1"),
    ("Ctrl+arrows", "Jump to the edge of your data in that direction"),
    ("Ctrl+Shift+arrows", "Select from here to the data edge"),
    ("Type, Enter or F2", "Edit the cell in place"),
    ("Enter / Tab while editing", "Save, then move down / right"),
    ("Shift+Enter while editing", "New line inside the note"),
    ("Esc", "Cancel edit · clear filter · close find"),
    ("Delete", "Clear the selected cells"),
    ("Ctrl+Z · Ctrl+Y", "Undo · redo cell changes"),
    ("Sort button (top bar)", "Sort rows by the selected column · group duplicates on top · delete duplicate rows, keeping the first. Scopes to the data block around your cell (or your selection) — other blocks never move"),
    ("Duplicate counter", "Repeated values show a red ×N badge in the cell; the status bar counts them live"),
    ("Ctrl+I, or drop a file", "Import a CSV or text file — pick the separator, into a new sheet or right here"),
    ("Ctrl+H", "Find and replace, this sheet or all sheets"),
    ("F8", "Pin row 1 (your labels) while you scroll"),
    ("Right-click a row or column header", "Insert, move or delete that row / column"),
    ("Ctrl+C · Ctrl+X · Ctrl+V", "Copy · cut · paste (lines go down; commas, tabs or ---- split across); copied blocks use your export separator"),
    ("Ctrl+Shift+V", "Paste as one note, unsplit"),
    ("Ctrl+B · Ctrl+K · Ctrl+L", "Bold · checkbox · bullet line"),
    ("#word inside a note", "Tags it — Ctrl+Shift+T filters, or click a tag pill"),
    ("Ctrl+F", "Find in all sheets · Enter next · Shift+Enter back"),
    ("Ctrl+T", "New sheet · Ctrl+PgUp / PgDn switch · right-click a tab for more"),
    ("Ctrl+S · Ctrl+O · Ctrl+N", "Save · open · new workbook"),
    ("Ctrl+E", "Export a sheet as CSV or text, separator of your choice"),
    ("Ctrl+,", "Theme, fonts, bold text, background effect and the column separator"),
    ("Ctrl+click a link cell", "Open the URL"),
]


class HelpDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard")
        self.setMinimumWidth(560)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(14)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(9)
        for row, (key, what) in enumerate(KEYS):
            key_label = QLabel(key)
            key_label.setFont(theme.mono(11))
            key_label.setStyleSheet(
                f"color: {theme.TEXT_SOFT}; border: 1px solid #3a3f49; border-radius: 4px; padding: 3px 7px;"
            )
            what_label = QLabel(what)
            what_label.setFont(theme.sans(12))
            what_label.setStyleSheet(f"color: {theme.TEXT_SOFT};")
            what_label.setWordWrap(True)
            grid.addWidget(key_label, row, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            grid.addWidget(what_label, row, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)

        close = QPushButton("Close")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        lay.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
