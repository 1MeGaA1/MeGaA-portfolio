"""Export a sheet as delimited text (.csv / .txt) with a separator of your choice."""
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
from .model import Workbook, export_text

SEPARATORS: list[tuple[str, str | None]] = [
    ("Comma (CSV)", ","),
    ("Tab", "\t"),
    ("Four dashes ----", "----"),
    ("Custom", None),
]


class ExportDialog(QDialog):
    def __init__(self, workbook: Workbook, current_sheet: int, initial_sep: str = "\t", parent=None) -> None:
        super().__init__(parent)
        self.workbook = workbook
        self.setWindowTitle("Export sheet")
        self.setMinimumWidth(430)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.addWidget(QLabel("Sheet"), 0, 0)
        self.sheet_box = QComboBox()
        for sheet in workbook.sheets:
            self.sheet_box.addItem(sheet.name)
        self.sheet_box.setCurrentIndex(current_sheet)
        form.addWidget(self.sheet_box, 0, 1)
        form.addWidget(QLabel("Between columns"), 1, 0)
        self.sep_box = QComboBox()
        for label, _ in SEPARATORS:
            self.sep_box.addItem(label)
        form.addWidget(self.sep_box, 1, 1)
        self.custom = QLineEdit(" ---- ")
        self.custom.setPlaceholderText("Type any separator")
        self.custom.setFont(theme.mono(12))
        form.addWidget(self.custom, 2, 1)
        form.setColumnStretch(1, 1)
        lay.addLayout(form)

        preview_title = QLabel("Preview")
        preview_title.setFont(theme.sans(11))
        preview_title.setStyleSheet(f"color: {theme.MUTED};")
        lay.addWidget(preview_title)
        self.preview = QLabel("")
        self.preview.setFont(theme.mono(11))
        self.preview.setStyleSheet(
            f"color: {theme.TEXT_SOFT}; background: {theme.FIELD}; border: 1px solid {theme.BORDER}; "
            "border-radius: 4px; padding: 8px;"
        )
        lay.addWidget(self.preview)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setText("Export")
        save_btn.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        preset = next((i for i, (_, sep) in enumerate(SEPARATORS) if sep == initial_sep), None)
        if preset is None:
            self.sep_box.setCurrentIndex(len(SEPARATORS) - 1)
            self.custom.setText(initial_sep)
        else:
            self.sep_box.setCurrentIndex(preset)

        self.sheet_box.currentIndexChanged.connect(self._refresh)
        self.sep_box.currentIndexChanged.connect(self._refresh)
        self.custom.textChanged.connect(self._refresh)
        self._refresh()

    # -- choices ---------------------------------------------------------------
    def separator(self) -> str:
        sep = SEPARATORS[self.sep_box.currentIndex()][1]
        if sep is None:
            return self.custom.text() or ","
        return sep

    def sheet_index(self) -> int:
        return self.sheet_box.currentIndex()

    def suffix(self) -> str:
        return ".csv" if self.separator() == "," else ".txt"

    def text(self) -> str:
        return export_text(self.workbook.sheets[self.sheet_index()], self.separator())

    def _refresh(self, *_args) -> None:
        self.custom.setVisible(SEPARATORS[self.sep_box.currentIndex()][1] is None)
        lines = self.text().split("\n")[:3]
        shown = [line if len(line) <= 56 else line[:55] + "…" for line in lines]
        self.preview.setText("\n".join(shown) if any(shown) else "Nothing on this sheet yet")
