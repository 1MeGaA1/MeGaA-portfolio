"""Ctrl+I / drag-and-drop: import a CSV or text file into cells."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from . import theme
from .model import parse_delimited

IMPORT_SEPARATORS: list[tuple[str, str | None]] = [
    ("Auto detect", "auto"),
    ("Comma (CSV)", ","),
    ("Tab", "\t"),
    ("Four dashes ----", "----"),
    ("Custom", None),
]


class ImportDialog(QDialog):
    def __init__(self, file_name: str, text: str, target_ref: str, parent=None) -> None:
        super().__init__(parent)
        self._text = text
        self.setWindowTitle("Import")
        self.setMinimumWidth(470)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        title = QLabel(file_name)
        title.setFont(theme.sans(14, bold=True))
        lay.addWidget(title)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.addWidget(QLabel("Between columns"), 0, 0)
        self.sep_box = QComboBox()
        for label, _ in IMPORT_SEPARATORS:
            self.sep_box.addItem(label)
        form.addWidget(self.sep_box, 0, 1)
        self.custom = QLineEdit(";")
        self.custom.setPlaceholderText("Type any separator")
        self.custom.setFont(theme.mono(12))
        form.addWidget(self.custom, 1, 1)
        form.addWidget(QLabel("Put it"), 2, 0)
        self.dest_box = QComboBox()
        self.dest_box.addItem("In a new sheet")
        self.dest_box.addItem(f"Here, starting at {target_ref}")
        form.addWidget(self.dest_box, 2, 1)
        form.setColumnStretch(1, 1)
        lay.addLayout(form)

        self.summary = QLabel("")
        self.summary.setFont(theme.sans(11))
        self.summary.setStyleSheet(f"color: {theme.MUTED};")
        lay.addWidget(self.summary)
        self.preview = QLabel("")
        self.preview.setFont(theme.mono(11))
        self.preview.setStyleSheet(
            f"color: {theme.TEXT_SOFT}; background: {theme.FIELD}; border: 1px solid {theme.BORDER}; "
            "border-radius: 4px; padding: 8px;"
        )
        lay.addWidget(self.preview)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("Import")
        ok_btn.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self.sep_box.currentIndexChanged.connect(self._refresh)
        self.custom.textChanged.connect(self._refresh)
        self._refresh()

    def _sep(self) -> str:
        sep = IMPORT_SEPARATORS[self.sep_box.currentIndex()][1]
        if sep is None:
            return self.custom.text() or ","
        return sep

    def block(self) -> list[list[str]]:
        return parse_delimited(self._text, self._sep())

    def to_new_sheet(self) -> bool:
        return self.dest_box.currentIndex() == 0

    def _refresh(self, *_args) -> None:
        self.custom.setVisible(IMPORT_SEPARATORS[self.sep_box.currentIndex()][1] is None)
        block = self.block()
        rows = len(block)
        cols = max((len(r) for r in block), default=0)
        self.summary.setText(f"{rows} rows × {cols} columns detected")
        lines = []
        for row in block[:3]:
            joined = " | ".join(row[:6])
            lines.append(joined if len(joined) <= 58 else joined[:57] + "…")
        self.preview.setText("\n".join(lines) if lines else "Nothing to import")
