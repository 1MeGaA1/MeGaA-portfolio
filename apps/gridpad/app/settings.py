"""The Ctrl+, dialog: theme, fonts, bold text and the column separator; the window reopens with them."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from . import theme
from .effects import EFFECTS
from .export import SEPARATORS

SKIP_FAMILIES = {"SimSun-ExtB", "SimSun-ExtG", "Simplified Arabic Fixed"}


def mono_families() -> list[str]:
    """Monospace families installed on this machine, minus CJK/legacy system faces."""
    out = []
    for family in QFontDatabase.families():
        if family.startswith("@") or family in SKIP_FAMILIES:
            continue
        if QFontDatabase.isFixedPitch(family):
            out.append(family)
    return sorted(out)


def ui_families() -> list[str]:
    return sorted(f for f in QFontDatabase.families() if not f.startswith("@"))


class SettingsDialog(QDialog):
    def __init__(self, current_theme: str, current_mono: str, current_sans: str,
                 current_bold: bool, current_sep: str, current_effect: str = "None", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Appearance")
        self.setMinimumWidth(460)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        form.addWidget(QLabel("Theme"), 0, 0)
        self.theme_box = QComboBox()
        for name in theme.THEMES:
            self.theme_box.addItem(name)
        self.theme_box.setCurrentText(current_theme if current_theme in theme.THEMES else theme.DEFAULT_THEME)
        form.addWidget(self.theme_box, 0, 1)

        form.addWidget(QLabel("Notes font"), 1, 0)
        self.mono_box = QComboBox()
        families = mono_families()
        if current_mono and current_mono not in families:
            families.insert(0, current_mono)
        for i, family in enumerate(families):
            self.mono_box.addItem(family)
            self.mono_box.setItemData(i, QFont(family), Qt.ItemDataRole.FontRole)
        self.mono_box.setCurrentText(current_mono or theme.mono_family())
        form.addWidget(self.mono_box, 1, 1)

        form.addWidget(QLabel("App font"), 2, 0)
        self.sans_box = QComboBox()
        sans_list = ui_families()
        if current_sans and current_sans not in sans_list:
            sans_list.insert(0, current_sans)
        for i, family in enumerate(sans_list):
            self.sans_box.addItem(family)
            self.sans_box.setItemData(i, QFont(family), Qt.ItemDataRole.FontRole)
        self.sans_box.setCurrentText(current_sans or theme.sans_family())
        form.addWidget(self.sans_box, 2, 1)

        self.bold_check = QCheckBox("Bold text everywhere")
        self.bold_check.setChecked(bool(current_bold))
        form.addWidget(self.bold_check, 3, 1)

        form.addWidget(QLabel("Effect"), 4, 0)
        self.effect_box = QComboBox()
        for i, (name, desc) in enumerate(EFFECTS):
            self.effect_box.addItem(f"{name}  ·  {desc}")
            self.effect_box.setItemData(i, name)
        current_i = next((i for i, (n, _) in enumerate(EFFECTS) if n == current_effect), 0)
        self.effect_box.setCurrentIndex(current_i)
        form.addWidget(self.effect_box, 4, 1)

        form.addWidget(QLabel("Between columns"), 5, 0)
        self.sep_box = QComboBox()
        for label, _ in SEPARATORS:
            self.sep_box.addItem(label)
        form.addWidget(self.sep_box, 5, 1)
        self.custom = QLineEdit(" ---- ")
        self.custom.setPlaceholderText("Type any separator")
        self.custom.setFont(theme.mono(12))
        form.addWidget(self.custom, 6, 1)
        preset = next((i for i, (_, sep) in enumerate(SEPARATORS) if sep == current_sep), None)
        if preset is None:
            self.sep_box.setCurrentIndex(len(SEPARATORS) - 1)
            self.custom.setText(current_sep)
        else:
            self.sep_box.setCurrentIndex(preset)

        form.setColumnStretch(1, 1)
        lay.addLayout(form)

        self.preview = QLabel()
        lay.addWidget(self.preview)

        note = QLabel("Applies right away and is remembered. The separator is used when copying "
                      "blocks and as the export default. Install a font and it appears here.")
        note.setWordWrap(True)
        note.setFont(theme.sans(11))
        note.setStyleSheet(f"color: {theme.MUTED};")
        lay.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("Apply")
        ok_btn.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self.theme_box.currentIndexChanged.connect(self._refresh)
        self.mono_box.currentIndexChanged.connect(self._refresh)
        self.sans_box.currentIndexChanged.connect(self._refresh)
        self.bold_check.toggled.connect(self._refresh)
        self.sep_box.currentIndexChanged.connect(self._refresh)
        self.custom.textChanged.connect(self._refresh)
        self._refresh()

    # -- choices ----------------------------------------------------------------
    def theme_name(self) -> str:
        return self.theme_box.currentText()

    def mono_font(self) -> str:
        return self.mono_box.currentText()

    def sans_font(self) -> str:
        return self.sans_box.currentText()

    def bold(self) -> bool:
        return self.bold_check.isChecked()

    def separator(self) -> str:
        sep = SEPARATORS[self.sep_box.currentIndex()][1]
        if sep is None:
            return self.custom.text() or ","
        return sep

    def effect(self) -> str:
        return str(self.effect_box.currentData())

    def _refresh(self, *_args) -> None:
        self.custom.setVisible(SEPARATORS[self.sep_box.currentIndex()][1] is None)
        colors = theme.THEMES[self.theme_name()]
        width, height = 428, 104
        pm = QPixmap(width, height)
        pm.fill(QColor(colors["BG"]))
        painter = QPainter(pm)
        heavy = QFont.Weight.DemiBold if self.bold() else QFont.Weight.Normal

        mono_font = QFont(self.mono_font())
        mono_font.setPixelSize(13)
        mono_font.setWeight(heavy)
        sans_font = QFont(self.sans_font())
        sans_font.setPixelSize(12)
        sans_font.setWeight(QFont.Weight.Bold if self.bold() else QFont.Weight.DemiBold)

        painter.fillRect(0, 0, width, 26, QColor(colors["PANEL"]))
        painter.setPen(QPen(QColor(colors["BORDER"])))
        painter.drawLine(0, 26, width, 26)
        painter.setFont(sans_font)
        painter.setPen(QColor(colors["TEXT"]))
        painter.drawText(QRect(12, 0, 220, 26), Qt.AlignmentFlag.AlignVCenter, self.theme_name())
        small_sans = QFont(self.sans_font())
        small_sans.setPixelSize(11)
        small_sans.setWeight(heavy)
        painter.setFont(small_sans)
        painter.setPen(QColor(colors["MUTED"]))
        painter.drawText(QRect(12, 0, width - 24, 26), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                         f"{self.sans_font()} + {self.mono_font()}")

        cell = QRect(12, 38, 310, 26)
        painter.fillRect(cell, QColor(colors["ACCENT_BG"]))
        painter.setPen(QPen(QColor(colors["ACCENT"])))
        painter.drawRect(cell.adjusted(0, 0, -1, -1))
        painter.setFont(mono_font)
        painter.setPen(QColor(colors["TEXT"]))
        painter.drawText(cell.adjusted(8, 0, -60, 0), Qt.AlignmentFlag.AlignVCenter, "Call plumber — £180")
        pill = QRect(cell.right() - 54, cell.center().y() - 8, 48, 17)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors["TAG_BG"]))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.drawRoundedRect(pill, 3, 3)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        small_mono = QFont(self.mono_font())
        small_mono.setPixelSize(11)
        small_mono.setWeight(heavy)
        painter.setFont(small_mono)
        painter.setPen(QColor(colors["TAG"]))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, "#home")

        painter.setFont(mono_font)
        hl = QRect(12, 74, 62, 20)
        painter.fillRect(hl, QColor(colors["HI"]))
        painter.setPen(QColor(colors["HI_TEXT"]))
        painter.drawText(hl, Qt.AlignmentFlag.AlignCenter, "found")
        painter.setPen(QColor(colors["MUTED"]))
        sep = self.separator().replace("\t", "⇥")
        painter.drawText(QRect(86, 74, width - 98, 20), Qt.AlignmentFlag.AlignVCenter,
                         f"copy: aa{sep}bb · 18 notes")
        painter.end()
        self.preview.setPixmap(pm)
