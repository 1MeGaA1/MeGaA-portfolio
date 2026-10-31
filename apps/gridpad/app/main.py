"""Application entry: builds the QApplication, opens the last workbook, shows the window."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import icons, theme
from .main_window import MainWindow
from .model import Workbook


def create_app(argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setApplicationName("GridPad")
    app.setOrganizationName("GridPad")
    app.setStyle("Fusion")
    theme.apply_to_app(app)
    app.setWindowIcon(QIcon(icons.pixmap("grid", theme.ACCENT, 64)))
    return app


def open_startup_workbook(settings: QSettings, argv: list[str]) -> Workbook:
    candidates = [a for a in argv[1:] if not a.startswith("-")]
    last = settings.value("last_file")
    if last:
        candidates.append(str(last))
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            try:
                return Workbook.load(path)
            except (OSError, ValueError):
                continue
    return Workbook()


def main() -> int:
    settings = QSettings("GridPad", "GridPad")
    theme.load_appearance(settings)
    app = create_app(sys.argv)
    workbook = open_startup_workbook(settings, sys.argv)
    window = MainWindow(workbook, settings)
    window.show()
    return app.exec()
