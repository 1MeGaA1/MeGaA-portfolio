"""Generate the seed product pictures -> server/vortex_server/seed_media/products/<slug>.png
(256x256, transparent). The server copies them into its media dir on first seed and the
kiosk loads them over HTTP (serverHttp + image_url); staff replace them from the admin panel.

Foods/natural drinks: Twemoji SVGs (CC-BY 4.0) rendered with QtSvg.
Branded packs (sodas, energy drinks, water, chips, protein bar): drawn with QPainter as
brand-coloured cans / bottle / bags with the product name on the label, so no copyrighted
product photography is used.
"""
import os, sys, urllib.request
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (QGuiApplication, QImage, QPainter, QColor, QLinearGradient, QBrush,
                           QFont, QFontDatabase, QPainterPath)
from PySide6.QtSvg import QSvgRenderer

NAT = Path(__file__).resolve().parent.parent   # client-native
OUT = Path(__file__).resolve().parents[2] / "server" / "vortex_server" / "seed_media" / "products"
OUT.mkdir(parents=True, exist_ok=True)
SIZE = 256
TW = "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/svg/{}.svg"

EMOJI = {
    "orangejuice": "1f9c3",  # beverage box
    "icedtea": "1f9cb",      # bubble tea (iced drink with straw)
    "lemonade": "1f34b",     # lemon
    "coffee": "2615",        # hot beverage
    "oreo": "1f36a",         # cookie
    "snickers": "1f36b",     # chocolate bar
    "mms": "1f36c",          # candy
    "popcorn": "1f37f",
    "nuts": "1f95c",         # peanuts
    "pizza": "1f355",
    "burger": "1f354",
    "hotdog": "1f32d",
    "fries": "1f35f",
    "sandwich": "1f96a",
    "ramen": "1f35c",        # steaming bowl
}

app = QGuiApplication([])
for ttf in (NAT / "fonts").glob("*.ttf"):
    QFontDatabase.addApplicationFont(str(ttf))

AA = QPainter.RenderHint.Antialiasing
TAA = QPainter.RenderHint.TextAntialiasing
SMOOTH = QPainter.RenderHint.SmoothPixmapTransform
NOPEN = Qt.PenStyle.NoPen


def blank() -> QImage:
    img = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    return img


def painter(img: QImage) -> QPainter:
    p = QPainter(img)
    p.setRenderHint(AA); p.setRenderHint(TAA); p.setRenderHint(SMOOTH)
    p.setPen(NOPEN)
    return p


def save(img: QImage, slug: str) -> None:
    ok = img.save(str(OUT / f"{slug}.png"), "PNG")
    print(f"  {slug:12} {'OK' if ok else 'SAVE FAILED'}", flush=True)


def label(p: QPainter, rect: QRectF, text: str, color: str = "#ffffff", size: int = 22, spacing: float = 1.0) -> None:
    f = QFont("Rajdhani", size)
    f.setWeight(QFont.Weight.Bold)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    p.setPen(NOPEN)


# ------------------------------------------------------------------ emoji art
def render_emoji(slug: str, cp: str) -> None:
    data = urllib.request.urlopen(TW.format(cp), timeout=20).read()
    r = QSvgRenderer(data)
    img = blank(); p = painter(img)
    m = 20
    r.render(p, QRectF(m, m, SIZE - 2 * m, SIZE - 2 * m))
    p.end(); save(img, slug)


# ------------------------------------------------------------------ branded packs
def can(slug, base, dark, line1, line2=None, slim=False, text_color="#ffffff", band=None):
    img = blank(); p = painter(img)
    w = 82 if slim else 104
    x = (SIZE - w) / 2
    y0, y1 = 36, 224
    # body with cylindrical shading
    g = QLinearGradient(x, 0, x + w, 0)
    g.setColorAt(0.0, QColor(dark)); g.setColorAt(0.2, QColor(base))
    g.setColorAt(0.45, QColor(base).lighter(128)); g.setColorAt(0.72, QColor(base)); g.setColorAt(1.0, QColor(dark))
    path = QPainterPath(); path.addRoundedRect(QRectF(x, y0, w, y1 - y0), 13, 13)
    p.fillPath(path, QBrush(g))
    # optional label band
    if band:
        p.setBrush(QColor(band)); p.drawRect(QRectF(x, 104, w, 64))
    # lid + bottom rim (aluminium)
    lid = QLinearGradient(x, 0, x + w, 0)
    lid.setColorAt(0, QColor("#8f979f")); lid.setColorAt(0.5, QColor("#eef2f5")); lid.setColorAt(1, QColor("#7f878f"))
    p.setBrush(QBrush(lid)); p.drawEllipse(QRectF(x + 3, y0 - 7, w - 6, 16))
    p.setBrush(QColor("#c4cbd1")); p.drawRoundedRect(QRectF(x + 2, y1 - 7, w - 4, 10), 5, 5)
    # glossy highlight
    p.setBrush(QColor(255, 255, 255, 46)); p.drawRoundedRect(QRectF(x + 11, y0 + 14, 9, y1 - y0 - 34), 4, 4)
    # label text
    big = 22 if len(line1) <= 6 else 17
    if line2:
        label(p, QRectF(x - 6, 102, w + 12, 32), line1, text_color, big, 1.5)
        label(p, QRectF(x - 6, 134, w + 12, 32), line2, text_color, big, 1.5)
    else:
        label(p, QRectF(x - 6, 116, w + 12, 36), line1, text_color, big, 1.5)
    p.end(); save(img, slug)


def bottle(slug):
    img = blank(); p = painter(img)
    cx = SIZE / 2
    p.setBrush(QColor("#2f7bff")); p.drawRoundedRect(QRectF(cx - 17, 24, 34, 22), 5, 5)          # cap
    p.setBrush(QColor(200, 230, 255, 170)); p.drawRoundedRect(QRectF(cx - 13, 44, 26, 28), 5, 5)  # neck
    g = QLinearGradient(cx - 46, 0, cx + 46, 0)
    g.setColorAt(0, QColor(140, 195, 255, 150)); g.setColorAt(0.5, QColor(225, 243, 255, 215)); g.setColorAt(1, QColor(120, 175, 240, 160))
    p.setBrush(QBrush(g)); p.drawRoundedRect(QRectF(cx - 46, 68, 92, 160), 20, 20)               # body
    p.setBrush(QColor("#1e63e9")); p.drawRect(QRectF(cx - 46, 122, 92, 46))                        # label band
    label(p, QRectF(cx - 46, 122, 92, 46), "WATER", "#ffffff", 17, 2.5)
    p.setBrush(QColor(255, 255, 255, 95)); p.drawRoundedRect(QRectF(cx - 36, 80, 10, 136), 5, 5)  # shine
    p.end(); save(img, slug)


def bag(slug, base, dark, line1, text_color, line2=None):
    img = blank(); p = painter(img)
    x0, x1, y0, y1 = 58, 198, 36, 224
    n = 8; step = (x1 - x0 - 12) / n
    path = QPainterPath(); path.moveTo(x0 + 6, y0)
    for i in range(n):                                   # crimped top edge
        path.lineTo(x0 + 6 + step * (i + 0.5), y0 + 8); path.lineTo(x0 + 6 + step * (i + 1), y0)
    path.lineTo(x1, y0 + 16); path.lineTo(x1 - 4, y1 - 16); path.lineTo(x1 - 6, y1)
    for i in range(n):                                   # crimped bottom edge
        path.lineTo(x1 - 6 - step * (i + 0.5), y1 - 8); path.lineTo(x1 - 6 - step * (i + 1), y1)
    path.lineTo(x0, y1 - 16); path.lineTo(x0 + 4, y0 + 16); path.closeSubpath()
    g = QLinearGradient(x0, 0, x1, 0)
    g.setColorAt(0, QColor(dark)); g.setColorAt(0.35, QColor(base)); g.setColorAt(0.55, QColor(base).lighter(118)); g.setColorAt(1, QColor(dark))
    p.fillPath(path, QBrush(g))
    p.setBrush(QColor(255, 255, 255, 36)); p.drawRoundedRect(QRectF(x0 + 14, y0 + 26, 16, y1 - y0 - 52), 8, 8)   # foil shine
    p.setBrush(QColor(0, 0, 0, 80)); p.drawEllipse(QRectF(x0 + 20, 92, x1 - x0 - 40, 78))                        # label oval
    label(p, QRectF(x0, 98, x1 - x0, 36), line1, text_color, 24 if len(line1) <= 6 else 20, 1.5)
    if line2:
        label(p, QRectF(x0, 134, x1 - x0, 26), line2, text_color, 12, 2.5)
    p.end(); save(img, slug)


def bar(slug):
    img = blank(); p = painter(img)
    rect = QRectF(30, 96, 196, 64)
    g = QLinearGradient(30, 0, 226, 0)
    g.setColorAt(0, QColor("#1b1b22")); g.setColorAt(0.5, QColor("#33333f")); g.setColorAt(1, QColor("#15151b"))
    path = QPainterPath(); path.addRoundedRect(rect, 10, 10); p.fillPath(path, QBrush(g))
    p.setBrush(QColor("#0f0f14"))
    p.drawRoundedRect(QRectF(20, 104, 16, 48), 4, 4); p.drawRoundedRect(QRectF(220, 104, 16, 48), 4, 4)   # crimped ends
    p.setBrush(QColor("#00ff88")); p.drawRect(QRectF(30, 128, 196, 4))                                       # accent stripe
    label(p, QRectF(30, 98, 196, 30), "PROTEIN", "#ffffff", 22, 3)
    label(p, QRectF(30, 132, 196, 26), "BAR · 20g", "#00ff88", 12, 2)
    p.end(); save(img, slug)


# ------------------------------------------------------------------ run
print("emoji art:")
failed = []
for slug, cp in EMOJI.items():
    try:
        render_emoji(slug, cp)
    except Exception as exc:
        failed.append(slug); print(f"  {slug:12} FAILED: {exc}", flush=True)

print("branded packs:")
can("cocacola", "#e0142b", "#7a0a17", "Coca", "Cola")
can("pepsi",    "#0f5bd6", "#082f73", "PEPSI")
can("sprite",   "#12a84a", "#0a5a2a", "Sprite")
can("redbull",  "#1b3f8f", "#0d1f4d", "Red", "Bull", slim=True, text_color="#ffd400")
can("monster",  "#101014", "#000000", "MONSTER", "ENERGY", slim=True, text_color="#39ff14")
bottle("water")
bag("doritos", "#d31a1a", "#6e0b0b", "Doritos", "#ffd21f", "NACHO CHEESE")
bag("lays",    "#ffc21a", "#b8860b", "Lay's",   "#d3202a", "CLASSIC")
bar("proteinbar")

(OUT / "ATTRIBUTION.txt").write_text(
    "Food/drink illustrations: Twemoji (https://github.com/twitter/twemoji), CC-BY 4.0.\n"
    "Branded packs (cans, bottle, bags, bar) are original vector drawings generated by tools/make_shop_images.py.\n",
    "utf-8")
print("failed:", failed if failed else "none")
print(f"written to {OUT}")
