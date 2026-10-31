"""Small stroke icons drawn with QPainter (no image files), matching the design's 24px grid."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from . import theme

_cache: dict[tuple[str, str, int], QPixmap] = {}


def pixmap(name: str, color: str = theme.ICON, size: int = 16) -> QPixmap:
    key = (name, color, size)
    if key in _cache:
        return _cache[key]
    scale = 2  # crisp on HiDPI
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.scale(size * scale / 24.0, size * scale / 24.0)
    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    _draw(painter, name)
    painter.end()
    pm.setDevicePixelRatio(scale)
    _cache[key] = pm
    return pm


def icon(name: str, color: str = theme.ICON, size: int = 16) -> QIcon:
    return QIcon(pixmap(name, color, size))


def _line(p: QPainter, x1: float, y1: float, x2: float, y2: float) -> None:
    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def _draw(p: QPainter, name: str) -> None:
    if name == "grid":
        for x, y in ((3.5, 3.5), (13.5, 3.5), (3.5, 13.5), (13.5, 13.5)):
            p.drawRoundedRect(QRectF(x, y, 7, 7), 1.5, 1.5)
    elif name == "bold":
        path = QPainterPath()
        path.moveTo(7, 5)
        path.lineTo(13, 5)
        path.arcTo(QRectF(9.5, 5, 7, 7), 90, -180)
        path.lineTo(7, 12)
        path.closeSubpath()
        path.moveTo(7, 12)
        path.lineTo(14, 12)
        path.arcTo(QRectF(10.5, 12, 7, 7), 90, -180)
        path.lineTo(7, 19)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "list":
        for y in (6, 12, 18):
            _line(p, 9, y, 20, y)
            _line(p, 4, y, 4.01, y)
    elif name == "check":
        p.drawRoundedRect(QRectF(4, 4, 16, 16), 3, 3)
        p.drawPolyline([QPointF(9, 12), QPointF(11, 14), QPointF(15, 10)])
    elif name == "tag":
        p.drawPolygon([
            QPointF(20.3, 12.2), QPointF(12.2, 20.3), QPointF(10.8, 20.3), QPointF(4, 13.5),
            QPointF(4, 4), QPointF(13.5, 4), QPointF(20.3, 10.8),
        ])
        p.drawEllipse(QPointF(8.5, 8.5), 1.0, 1.0)
    elif name == "link":
        p.save()
        p.translate(12, 12)
        p.rotate(-45)
        p.drawRoundedRect(QRectF(-9, -3, 10, 6), 3, 3)
        p.drawRoundedRect(QRectF(-1, -3, 10, 6), 3, 3)
        _line(p, -3, 0, 3, 0)
        p.restore()
    elif name == "plus":
        _line(p, 12, 5, 12, 19)
        _line(p, 5, 12, 19, 12)
    elif name == "x":
        _line(p, 6, 6, 18, 18)
        _line(p, 18, 6, 6, 18)
    elif name == "search":
        p.drawEllipse(QPointF(11, 11), 7, 7)
        _line(p, 16.2, 16.2, 20, 20)
    elif name == "chevron-up":
        p.drawPolyline([QPointF(6, 15), QPointF(12, 9), QPointF(18, 15)])
    elif name == "chevron-down":
        p.drawPolyline([QPointF(6, 9), QPointF(12, 15), QPointF(18, 9)])
    elif name == "sort":
        _line(p, 9, 6.5, 9, 17.5)
        p.drawPolyline([QPointF(5.5, 10), QPointF(9, 6.5), QPointF(12.5, 10)])
        _line(p, 15, 6.5, 15, 17.5)
        p.drawPolyline([QPointF(11.5, 14), QPointF(15, 17.5), QPointF(18.5, 14)])
    elif name == "gear":
        p.drawEllipse(QPointF(12, 12), 6.2, 6.2)
        p.drawEllipse(QPointF(12, 12), 2.4, 2.4)
        for i in range(8):
            a = math.pi * i / 4
            p.drawLine(
                QPointF(12 + 6.2 * math.cos(a), 12 + 6.2 * math.sin(a)),
                QPointF(12 + 8.8 * math.cos(a), 12 + 8.8 * math.sin(a)),
            )
    elif name == "upload":
        _line(p, 12, 14.5, 12, 4.5)
        p.drawPolyline([QPointF(7, 9.5), QPointF(12, 4.5), QPointF(17, 9.5)])
        _line(p, 5, 19, 19, 19)
    elif name == "download":
        _line(p, 12, 4, 12, 14.5)
        p.drawPolyline([QPointF(7, 10), QPointF(12, 15), QPointF(17, 10)])
        _line(p, 5, 19, 19, 19)
    elif name == "chevron-right":
        p.drawPolyline([QPointF(9, 6), QPointF(15, 12), QPointF(9, 18)])
    elif name == "chevron-left":
        p.drawPolyline([QPointF(15, 6), QPointF(9, 12), QPointF(15, 18)])
