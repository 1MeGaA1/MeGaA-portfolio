"""Qt Quick entry: builds the app, hands the backend to QML and loads qml/Main.qml."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPen, QPixmap
from PySide6.QtQml import QQmlApplicationEngine, QQmlImageProviderBase
from PySide6.QtQuick import QQuickImageProvider, QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle

from app import icons, theme
from app.main import open_startup_workbook

from .backend import Backend

QML_DIR = Path(__file__).resolve().parent / "qml"


class IconProvider(QQuickImageProvider):
    """image://icons/<name>/<rrggbb> — the classic edition's stroke icons, drawn at any size."""

    def __init__(self) -> None:
        super().__init__(QQmlImageProviderBase.ImageType.Pixmap)

    def requestPixmap(self, icon_id: str, size, requested_size) -> QPixmap:  # noqa: N802
        name, _, color = icon_id.partition("/")
        px = 32
        if requested_size.isValid() and max(requested_size.width(), requested_size.height()) > 0:
            px = max(requested_size.width(), requested_size.height())
        pm = QPixmap(px, px)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.scale(px / 24.0, px / 24.0)
        pen = QPen(QColor("#" + color.lstrip("#") if color else theme.ICON), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        icons._draw(painter, name)  # noqa: SLF001 — same drawing code as the classic edition
        painter.end()
        return pm


def create_app(argv: list[str] | None = None) -> QGuiApplication:
    QQuickStyle.setStyle("Basic")  # the one style whose controls take any background
    QQuickWindow.setTextRenderType(QQuickWindow.TextRenderType.NativeTextRendering)  # crisp small mono text
    app = QGuiApplication.instance() or QGuiApplication(argv or sys.argv)
    app.setApplicationName("GridPad")
    app.setOrganizationName("GridPad")
    return app


def build_engine(backend: Backend) -> QQmlApplicationEngine:
    engine = QQmlApplicationEngine()
    engine.addImageProvider("icons", IconProvider())
    ctx = engine.rootContext()
    ctx.setContextProperty("backend", backend)
    ctx.setContextProperty("gridModel", backend.model)
    ctx.setContextProperty("firstRowModel", backend.first_row)
    ctx.setContextProperty("themeSource", backend.palette)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    return engine


def main() -> int:
    settings = QSettings("GridPad", "GridPad")
    theme.load_appearance(settings)
    app = create_app(sys.argv)

    def set_icon() -> None:
        app.setWindowIcon(QIcon(icons.pixmap("grid", theme.ACCENT, 64)))

    set_icon()
    workbook = open_startup_workbook(settings, sys.argv)
    backend = Backend(workbook, settings)
    backend.palette.changed.connect(set_icon)
    engine = build_engine(backend)
    if not engine.rootObjects():
        return 1
    return app.exec()
