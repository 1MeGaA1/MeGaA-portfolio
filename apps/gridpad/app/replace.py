"""Ctrl+H: find and replace across a sheet or the whole workbook."""
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


class ReplaceDialog(QDialog):
    def __init__(self, initial_find: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Find and replace")
        self.setMinimumWidth(420)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.addWidget(QLabel("Find"), 0, 0)
        self.find_edit = QLineEdit(initial_find)
        self.find_edit.setFont(theme.mono(12))
        form.addWidget(self.find_edit, 0, 1)
        form.addWidget(QLabel("Replace with"), 1, 0)
        self.replace_edit = QLineEdit("")
        self.replace_edit.setFont(theme.mono(12))
        form.addWidget(self.replace_edit, 1, 1)
        form.addWidget(QLabel("Where"), 2, 0)
        self.scope_box = QComboBox()
        self.scope_box.addItem("This sheet")
        self.scope_box.addItem("All sheets")
        form.addWidget(self.scope_box, 2, 1)
        form.setColumnStretch(1, 1)
        lay.addLayout(form)

        note = QLabel("Matches ignore upper/lower case. Ctrl+Z undoes the whole replace.")
        note.setWordWrap(True)
        note.setFont(theme.sans(11))
        note.setStyleSheet(f"color: {theme.MUTED};")
        lay.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("Replace all")
        ok_btn.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.find_edit.setFocus()
        self.find_edit.selectAll()

    def find_text(self) -> str:
        return self.find_edit.text()

    def replace_text(self) -> str:
        return self.replace_edit.text()

    def all_sheets(self) -> bool:
        return self.scope_box.currentIndex() == 1
