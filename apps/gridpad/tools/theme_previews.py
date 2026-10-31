"""Render every theme as one labelled contact sheet, plus a font sample sheet.

    python tools/theme_previews.py [out_dir]

Writes themes.png (the app in each theme) and fonts.png (each installed mono font).
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

from PySide6.QtCore import QRect, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen  # noqa: E402

from app import theme  # noqa: E402
from app.main import create_app  # noqa: E402
from app.main_window import MainWindow  # noqa: E402
from app.settings import mono_families  # noqa: E402
from tools.screenshot import demo_workbook  # noqa: E402


def themes_sheet(app, out_dir: Path) -> None:
    settings = QSettings(str(out_dir / "preview-settings.ini"), QSettings.Format.IniFormat)
    workbook = demo_workbook(out_dir / "preview-demo.gridpad")
    shots: list[tuple[str, QImage]] = []
    for name in theme.THEMES:
        theme.apply_theme(name)
        theme.apply_to_app(app)
        window = MainWindow(workbook, settings)
        window.resize(1280, 800)
        window.show()
        app.processEvents()
        window.grid.select_cell(2, 0)
        app.processEvents()
        app.processEvents()
        image = window.grab().toImage().scaled(
            620, 388, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        shots.append((name, image))
        window._reopening = True
        window.close()
        app.processEvents()
        print("rendered", name)
    theme.apply_theme(theme.DEFAULT_THEME)
    theme.apply_to_app(app)

    cols, pad, label_h = 2, 16, 36
    cell_w, cell_h = 620, 388 + label_h
    rows = (len(shots) + cols - 1) // cols
    sheet = QImage(cols * cell_w + pad * (cols + 1), rows * cell_h + pad * (rows + 1),
                   QImage.Format.Format_RGB32)
    sheet.fill(QColor("#0b0b0d"))
    painter = QPainter(sheet)
    label_font = QFont("Segoe UI")
    label_font.setPixelSize(17)
    label_font.setWeight(QFont.Weight.DemiBold)
    for i, (name, image) in enumerate(shots):
        x = pad + (i % cols) * (cell_w + pad)
        y = pad + (i // cols) * (cell_h + pad)
        painter.setFont(label_font)
        painter.setPen(QColor("#e8e8e8"))
        painter.drawText(QRect(x + 2, y, cell_w, label_h), Qt.AlignmentFlag.AlignVCenter, f"{i + 1} · {name}")
        painter.drawImage(x, y + label_h, image)
        painter.setPen(QPen(QColor("#2e2e33")))
        painter.drawRect(x, y + label_h, image.width() - 1, image.height() - 1)
    painter.end()
    sheet.save(str(out_dir / "themes.png"))
    print("wrote", out_dir / "themes.png")


def fonts_sheet(out_dir: Path) -> None:
    families = mono_families()
    line_h, width = 84, 940
    sheet = QImage(width, len(families) * line_h + 16, QImage.Format.Format_RGB32)
    sheet.fill(QColor("#16181c"))
    painter = QPainter(sheet)
    for i, family in enumerate(families):
        y = 8 + i * line_h
        label = QFont("Segoe UI")
        label.setPixelSize(13)
        painter.setFont(label)
        painter.setPen(QColor("#8b8f98"))
        painter.drawText(QRect(20, y + 6, width - 40, 20), Qt.AlignmentFlag.AlignVCenter, family)
        sample = QFont(family)
        sample.setPixelSize(16)
        painter.setFont(sample)
        painter.setPen(QColor("#e4e2db"))
        painter.drawText(QRect(20, y + 30, width - 40, 26), Qt.AlignmentFlag.AlignVCenter,
                         "Call plumber re: kitchen leak — quote was £180  #home  A3  0123456789  Il1 O0")
        painter.setPen(QPen(QColor("#2b2f37")))
        painter.drawLine(20, y + line_h - 6, width - 20, y + line_h - 6)
    painter.end()
    sheet.save(str(out_dir / "fonts.png"))
    print("wrote", out_dir / "fonts.png")


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "tools" / "shots")
    out_dir.mkdir(parents=True, exist_ok=True)
    app = create_app(["gridpad"])
    themes_sheet(app, out_dir)
    fonts_sheet(out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
