"""Animated background effects drawn behind the grid, colored from the active theme."""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from . import theme

EFFECTS: list[tuple[str, str]] = [
    ("None", "plain background"),
    ("Starfield", "twinkling depth + streaks"),
    ("Snow", "slow drifting flakes"),
    ("Fireflies", "wandering glow"),
    ("Rain", "falling streaks"),
    ("Aurora", "slow colour waves"),
    ("Embers", "rising sparks"),
]


def _with_alpha(color: str, alpha: int) -> QColor:
    c = QColor(color)
    c.setAlpha(max(0, min(255, alpha)))
    return c


class EffectCanvas(QWidget):
    """Sits behind the (transparent) grid and animates at ~25 fps when an effect is on."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._effect = "None"
        self._t = 0.0
        self._items: list[dict] = []
        self._streaks: list[dict] = []
        self._rng = random.Random()
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

    # -- control ----------------------------------------------------------------
    def set_effect(self, name: str) -> None:
        if name not in {n for n, _ in EFFECTS}:
            name = "None"
        self._effect = name
        self._spawn()
        if name == "None":
            self._timer.stop()
        else:
            self._timer.start()
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._spawn()

    def _spawn(self) -> None:
        w, h = max(1, self.width()), max(1, self.height())
        rng = random.Random(7)
        self._streaks = []
        e = self._effect
        if e == "Starfield":
            self._items = [dict(x=rng.uniform(0, w), y=rng.uniform(0, h), z=rng.uniform(0.25, 1.0),
                                p=rng.uniform(0, math.tau)) for _ in range(140)]
        elif e == "Snow":
            self._items = [dict(x=rng.uniform(0, w), y=rng.uniform(0, h), s=rng.uniform(0.5, 1.6),
                                r=rng.uniform(1.4, 3.2), p=rng.uniform(0, math.tau)) for _ in range(90)]
        elif e == "Fireflies":
            self._items = [dict(x=rng.uniform(0, w), y=rng.uniform(0, h), vx=rng.uniform(-0.6, 0.6),
                                vy=rng.uniform(-0.6, 0.6), p=rng.uniform(0, math.tau)) for _ in range(22)]
        elif e == "Rain":
            self._items = [dict(x=rng.uniform(0, w), y=rng.uniform(0, h), s=rng.uniform(6.0, 11.0),
                                ln=rng.uniform(10, 22)) for _ in range(110)]
        elif e == "Aurora":
            self._items = [dict(cx=rng.uniform(0.15, 0.85), cy=rng.uniform(0.1, 0.6),
                                p=rng.uniform(0, math.tau), hue=i) for i in range(3)]
        elif e == "Embers":
            self._items = [dict(x=rng.uniform(0, w), y=rng.uniform(0, h), s=rng.uniform(0.6, 1.8),
                                p=rng.uniform(0, math.tau), hot=rng.random() < 0.4) for _ in range(60)]
        else:
            self._items = []

    # -- animation --------------------------------------------------------------
    def _tick(self) -> None:
        self._t += 0.04
        w, h = max(1, self.width()), max(1, self.height())
        e = self._effect
        if e == "Starfield":
            for it in self._items:
                it["x"] = (it["x"] + 0.08 * it["z"]) % w
            if self._rng.random() < 0.012:
                angle = self._rng.uniform(math.radians(20), math.radians(60))
                self._streaks.append(dict(x=self._rng.uniform(0, w), y=self._rng.uniform(0, h * 0.5),
                                          vx=math.cos(angle) * 14, vy=math.sin(angle) * 14, life=1.0))
            for st in self._streaks:
                st["x"] += st["vx"]
                st["y"] += st["vy"]
                st["life"] -= 0.045
            self._streaks = [st for st in self._streaks if st["life"] > 0]
        elif e == "Snow":
            for it in self._items:
                it["y"] = (it["y"] + it["s"]) % (h + 8)
                it["x"] = (it["x"] + math.sin(self._t + it["p"]) * 0.4) % w
        elif e == "Fireflies":
            for it in self._items:
                it["vx"] = max(-0.9, min(0.9, it["vx"] + self._rng.uniform(-0.12, 0.12)))
                it["vy"] = max(-0.9, min(0.9, it["vy"] + self._rng.uniform(-0.12, 0.12)))
                it["x"] = (it["x"] + it["vx"]) % w
                it["y"] = (it["y"] + it["vy"]) % h
        elif e == "Rain":
            for it in self._items:
                it["y"] += it["s"]
                it["x"] += 1.2
                if it["y"] > h + 24:
                    it["y"] = -24.0
                    it["x"] = self._rng.uniform(-20, w)
                it["x"] %= w + 40
        elif e == "Embers":
            for it in self._items:
                it["y"] -= it["s"]
                it["x"] = (it["x"] + math.sin(self._t * 2 + it["p"]) * 0.5) % w
                if it["y"] < -8:
                    it["y"] = h + self._rng.uniform(0, 40)
                    it["x"] = self._rng.uniform(0, w)
        self.update()

    # -- painting ---------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme.BG))
        e = self._effect
        if e == "None":
            painter.end()
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = max(1, self.width()), max(1, self.height())
        if e == "Starfield":
            for i, it in enumerate(self._items):
                twinkle = abs(math.sin(self._t * (0.8 + it["z"]) + it["p"]))
                alpha = int((28 + 130 * twinkle) * it["z"])
                color = theme.ACCENT if i % 7 == 0 else theme.TEXT
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(_with_alpha(color, alpha))
                r = 0.6 + 1.7 * it["z"]
                painter.drawEllipse(QPointF(it["x"], it["y"]), r, r)
            for st in self._streaks:
                life = st["life"]
                tail_x, tail_y = st["x"] - st["vx"] * 5, st["y"] - st["vy"] * 5
                painter.setPen(QPen(_with_alpha(theme.TEXT, int(50 * life)), 2.4))
                painter.drawLine(QPointF(tail_x, tail_y), QPointF(st["x"], st["y"]))
                painter.setPen(QPen(_with_alpha(theme.TEXT, int(190 * life)), 1.2))
                painter.drawLine(QPointF((tail_x + st["x"]) / 2, (tail_y + st["y"]) / 2),
                                 QPointF(st["x"], st["y"]))
        elif e == "Snow":
            painter.setPen(Qt.PenStyle.NoPen)
            for it in self._items:
                painter.setBrush(_with_alpha(theme.TEXT, 60))
                painter.drawEllipse(QPointF(it["x"], it["y"]), it["r"], it["r"])
        elif e == "Fireflies":
            for it in self._items:
                pulse = abs(math.sin(self._t * 1.4 + it["p"]))
                glow = QRadialGradient(QPointF(it["x"], it["y"]), 10)
                glow.setColorAt(0.0, _with_alpha(theme.TAG, int(30 + 110 * pulse)))
                glow.setColorAt(1.0, _with_alpha(theme.TAG, 0))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(glow)
                painter.drawEllipse(QPointF(it["x"], it["y"]), 10, 10)
                painter.setBrush(_with_alpha(theme.TAG, int(80 + 140 * pulse)))
                painter.drawEllipse(QPointF(it["x"], it["y"]), 1.6, 1.6)
        elif e == "Rain":
            painter.setPen(QPen(_with_alpha(theme.ACCENT, 52), 1.0))
            for it in self._items:
                painter.drawLine(QPointF(it["x"], it["y"]), QPointF(it["x"] + 2.5, it["y"] + it["ln"]))
        elif e == "Aurora":
            hues = [theme.ACCENT, theme.TAG, theme.RED]
            for it in self._items:
                cx = (it["cx"] + math.sin(self._t * 0.25 + it["p"]) * 0.16) * w
                cy = (it["cy"] + math.sin(self._t * 0.18 + it["p"] * 2) * 0.10) * h
                grad = QRadialGradient(QPointF(cx, cy), w * 0.45)
                grad.setColorAt(0.0, _with_alpha(hues[it["hue"] % 3], 26))
                grad.setColorAt(1.0, _with_alpha(hues[it["hue"] % 3], 0))
                painter.fillRect(self.rect(), grad)
        elif e == "Embers":
            painter.setPen(Qt.PenStyle.NoPen)
            for it in self._items:
                closeness = 1.0 - (it["y"] / (h + 1))
                alpha = int(30 + 150 * (1.0 - closeness))
                color = theme.RED if it["hot"] else theme.ACCENT
                painter.setBrush(_with_alpha(color, alpha))
                painter.drawEllipse(QPointF(it["x"], it["y"]), 1.3 + it["s"] * 0.6, 1.3 + it["s"] * 0.6)
        painter.end()
