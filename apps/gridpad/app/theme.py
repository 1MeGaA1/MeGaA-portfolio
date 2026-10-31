"""Looks: eight dark themes and the fonts, palette and stylesheet built from the active one.

Every color is a module-level name (theme.BG, theme.ACCENT, ...) so the rest of the app
never knows which theme is active; apply_theme() swaps them all at once.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette

DEFAULT_THEME = "Workbench"

# Token roles: BG grid, PANEL bars, FIELD inputs, ACCENT selection/cursor color,
# ACCENT_BG selection fill, HI/HI_TEXT find-match highlight, TAG/TAG_BG tag pills.
THEMES: dict[str, dict[str, str]] = {
    "Workbench": dict(
        BG="#1a1c21", PANEL="#202329", FIELD="#16181c", BORDER="#2b2f37", CELL_BORDER="#262a31",
        HOVER="#2f343d", MENU_BG="#262a31", MENU_BORDER="#343943", SCROLL="#343943",
        TEXT="#e4e2db", TEXT_SOFT="#c6c9cf", ICON="#aeb2ba", MUTED="#8b8f98", DIM="#5d616a", DIM_STROKE="#4a4e57",
        ACCENT="#e2a94f", ACCENT_BG="#2b2619", HI="#4a3d1c", HI_TEXT="#f0be6a",
        TAG="#52c2a8", TAG_BG="#17332c", TAG_DIM="#3f6d60", TAG_BG_DIM="#1e2623", RED="#ec8b85",
    ),
    "Midnight": dict(
        BG="#16161e", PANEL="#1a1b26", FIELD="#121218", BORDER="#2a2c3d", CELL_BORDER="#232532",
        HOVER="#2e3048", MENU_BG="#24263a", MENU_BORDER="#3b3d54", SCROLL="#3b3d54",
        TEXT="#c0caf5", TEXT_SOFT="#a9b1d6", ICON="#9aa5ce", MUTED="#7982a9", DIM="#545c7e", DIM_STROKE="#4a4f6e",
        ACCENT="#7aa2f7", ACCENT_BG="#1f2a47", HI="#33467c", HI_TEXT="#a8c1ff",
        TAG="#73daca", TAG_BG="#16342f", TAG_DIM="#4a8a80", TAG_BG_DIM="#1c2827", RED="#f7768e",
    ),
    "Violet": dict(
        BG="#21222c", PANEL="#282a36", FIELD="#1d1e26", BORDER="#3a3d4d", CELL_BORDER="#313341",
        HOVER="#3d4152", MENU_BG="#303241", MENU_BORDER="#44475a", SCROLL="#44475a",
        TEXT="#f8f8f2", TEXT_SOFT="#d8d8d2", ICON="#b0b3c5", MUTED="#8b8fa5", DIM="#5e6272", DIM_STROKE="#515467",
        ACCENT="#bd93f9", ACCENT_BG="#322a47", HI="#4b3a75", HI_TEXT="#d6bbff",
        TAG="#66d597", TAG_BG="#1d3a2c", TAG_DIM="#47936a", TAG_BG_DIM="#212e27", RED="#ff6e6e",
    ),
    "Nord": dict(
        BG="#242933", PANEL="#2e3440", FIELD="#1f242e", BORDER="#3b4252", CELL_BORDER="#333a49",
        HOVER="#434c5e", MENU_BG="#353c4a", MENU_BORDER="#4c566a", SCROLL="#4c566a",
        TEXT="#e5e9f0", TEXT_SOFT="#d8dee9", ICON="#aeb8cc", MUTED="#7b88a1", DIM="#59647a", DIM_STROKE="#4c566a",
        ACCENT="#88c0d0", ACCENT_BG="#1f353d", HI="#2f4d59", HI_TEXT="#b3e0ec",
        TAG="#a3be8c", TAG_BG="#2c3626", TAG_DIM="#6f8560", TAG_BG_DIM="#2a2f28", RED="#bf616a",
    ),
    "Ember": dict(
        BG="#1d2021", PANEL="#282828", FIELD="#191b1c", BORDER="#3c3836", CELL_BORDER="#32302e",
        HOVER="#45403d", MENU_BG="#32302f", MENU_BORDER="#504945", SCROLL="#504945",
        TEXT="#ebdbb2", TEXT_SOFT="#d5c4a1", ICON="#bdae93", MUTED="#928374", DIM="#665c54", DIM_STROKE="#59524c",
        ACCENT="#fe8019", ACCENT_BG="#3a2617", HI="#5a3a1a", HI_TEXT="#fabd2f",
        TAG="#8ec07c", TAG_BG="#263524", TAG_DIM="#6a9260", TAG_BG_DIM="#282f26", RED="#fb4934",
    ),
    "Forest": dict(
        BG="#1e2326", PANEL="#272e33", FIELD="#1a1f22", BORDER="#384148", CELL_BORDER="#2f383e",
        HOVER="#414b53", MENU_BG="#323b41", MENU_BORDER="#475258", SCROLL="#475258",
        TEXT="#d3c6aa", TEXT_SOFT="#bfb397", ICON="#9da9a0", MUTED="#859289", DIM="#5d6b66", DIM_STROKE="#525f5a",
        ACCENT="#a7c080", ACCENT_BG="#2c3627", HI="#45543a", HI_TEXT="#c9e0a5",
        TAG="#83c092", TAG_BG="#21362b", TAG_DIM="#5d8a68", TAG_BG_DIM="#253029", RED="#e67e80",
    ),
    "Rosé": dict(
        BG="#191724", PANEL="#1f1d2e", FIELD="#141220", BORDER="#34304d", CELL_BORDER="#2a273f",
        HOVER="#393552", MENU_BG="#2a273f", MENU_BORDER="#443f65", SCROLL="#443f65",
        TEXT="#e0def4", TEXT_SOFT="#c5c3dd", ICON="#a8a6c5", MUTED="#908caa", DIM="#605d7a", DIM_STROKE="#524f6b",
        ACCENT="#ebbcba", ACCENT_BG="#3a2a30", HI="#55393f", HI_TEXT="#f5d4d2",
        TAG="#9ccfd8", TAG_BG="#1f353a", TAG_DIM="#628a91", TAG_BG_DIM="#232e31", RED="#eb6f92",
    ),
    "Carbon": dict(
        BG="#131313", PANEL="#1b1b1b", FIELD="#0e0e0e", BORDER="#2c2c2c", CELL_BORDER="#242424",
        HOVER="#333333", MENU_BG="#262626", MENU_BORDER="#3d3d3d", SCROLL="#3d3d3d",
        TEXT="#e8e8e8", TEXT_SOFT="#cfcfcf", ICON="#b0b0b0", MUTED="#8a8a8a", DIM="#5c5c5c", DIM_STROKE="#4c4c4c",
        ACCENT="#ffffff", ACCENT_BG="#2e2e2e", HI="#444444", HI_TEXT="#ffffff",
        TAG="#d0d0d0", TAG_BG="#2a2a2a", TAG_DIM="#7a7a7a", TAG_BG_DIM="#222222", RED="#e08585",
    ),
}

_current_theme = DEFAULT_THEME


def apply_theme(name: str) -> None:
    """Swap every color token to the named theme (falls back to the default)."""
    global _current_theme
    if name not in THEMES:
        name = DEFAULT_THEME
    _current_theme = name
    globals().update(THEMES[name])


def current_theme() -> str:
    return _current_theme


# -- fonts ------------------------------------------------------------------
MONO_FALLBACKS = ["JetBrains Mono", "Cascadia Mono", "Cascadia Code", "Consolas", "Courier New"]
SANS_FALLBACKS = ["IBM Plex Sans", "Segoe UI", "Arial"]

_mono_override: str | None = None
_sans_override: str | None = None
_app_bold = False


def _pick(candidates: list[str]) -> str:
    installed = set(QFontDatabase.families())
    for family in candidates:
        if family in installed:
            return family
    return candidates[-1]


def set_mono_family(family: str | None) -> None:
    global _mono_override
    _mono_override = family or None


def set_sans_family(family: str | None) -> None:
    global _sans_override
    _sans_override = family or None


def set_app_bold(on: bool) -> None:
    global _app_bold
    _app_bold = bool(on)


def app_bold() -> bool:
    return _app_bold


def mono_family() -> str:
    if _mono_override and _mono_override in QFontDatabase.families():
        return _mono_override
    return _pick(MONO_FALLBACKS)


def sans_family() -> str:
    if _sans_override and _sans_override in QFontDatabase.families():
        return _sans_override
    return _pick(SANS_FALLBACKS)


def _weight(bold: bool) -> QFont.Weight:
    """Base weight; in bold mode everything steps one weight up so cell-bold still stands out."""
    if bold:
        return QFont.Weight.Bold if _app_bold else QFont.Weight.DemiBold
    return QFont.Weight.DemiBold if _app_bold else QFont.Weight.Normal


def mono(size: int = 13, bold: bool = False) -> QFont:
    font = QFont(mono_family())
    font.setPixelSize(size)
    font.setWeight(_weight(bold))
    return font


def sans(size: int = 13, bold: bool = False) -> QFont:
    font = QFont(sans_family())
    font.setPixelSize(size)
    font.setWeight(_weight(bold))
    return font


def chrome(size: int = 11) -> QFont:
    """The app font at a small size and always regular weight — for hints and status text."""
    font = QFont(sans_family())
    font.setPixelSize(size)
    font.setWeight(QFont.Weight.Normal)
    return font


# -- application hookup -----------------------------------------------------
def load_appearance(settings) -> None:
    """Read the saved theme and font choices (QSettings) into this module."""
    apply_theme(str(settings.value("theme", DEFAULT_THEME)))
    family = settings.value("font_mono")
    set_mono_family(str(family) if family else None)
    sans_fam = settings.value("font_sans")
    set_sans_family(str(sans_fam) if sans_fam else None)
    set_app_bold(str(settings.value("bold", "false")).lower() in ("true", "1"))


def apply_to_app(app) -> None:
    app.setPalette(palette())
    app.setFont(sans(13))
    app.setStyleSheet(stylesheet())


def palette() -> QPalette:
    pal = QPalette()
    role = QPalette.ColorRole
    pal.setColor(role.Window, QColor(BG))
    pal.setColor(role.WindowText, QColor(TEXT))
    pal.setColor(role.Base, QColor(FIELD))
    pal.setColor(role.AlternateBase, QColor(PANEL))
    pal.setColor(role.Text, QColor(TEXT))
    pal.setColor(role.Button, QColor(PANEL))
    pal.setColor(role.ButtonText, QColor(TEXT))
    pal.setColor(role.Highlight, QColor(ACCENT_BG))
    pal.setColor(role.HighlightedText, QColor(TEXT))
    pal.setColor(role.ToolTipBase, QColor(MENU_BG))
    pal.setColor(role.ToolTipText, QColor(TEXT))
    pal.setColor(role.PlaceholderText, QColor(MUTED))
    pal.setColor(role.Link, QColor(ACCENT))
    pal.setColor(role.Light, QColor(HOVER))
    pal.setColor(role.Midlight, QColor(BORDER))
    pal.setColor(role.Mid, QColor(BORDER))
    pal.setColor(role.Dark, QColor(FIELD))
    pal.setColor(role.Shadow, QColor("#000000"))
    disabled = QPalette.ColorGroup.Disabled
    pal.setColor(disabled, role.Text, QColor(DIM))
    pal.setColor(disabled, role.ButtonText, QColor(DIM))
    pal.setColor(disabled, role.WindowText, QColor(DIM))
    return pal


def stylesheet() -> str:
    return f"""
QToolTip {{
    background: {MENU_BG};
    color: {TEXT};
    border: 1px solid {MENU_BORDER};
    padding: 4px 6px;
}}
QFrame#topbar {{ background: {PANEL}; border-bottom: 1px solid {BORDER}; }}
QFrame#sheetbar {{ background: {PANEL}; border-top: 1px solid {BORDER}; }}

QFrame#searchbox {{
    background: {FIELD};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
QFrame#searchbox[active="true"] {{ border: 1px solid {ACCENT}; }}
QLineEdit#searchinput {{
    background: transparent;
    border: none;
    padding: 0;
    color: {TEXT};
    selection-background-color: {HI};
    selection-color: {HI_TEXT};
}}
QLineEdit {{
    background: {FIELD};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    color: {TEXT};
    selection-background-color: {HI};
    selection-color: {HI_TEXT};
}}
QLineEdit:focus {{ border: 1px solid {ACCENT}; }}

QPlainTextEdit#celleditor {{
    background: {FIELD};
    border: 1px solid {ACCENT};
    border-radius: 0;
    padding: 0px 2px;
    color: {TEXT};
    selection-background-color: {HI};
    selection-color: {HI_TEXT};
}}

QToolButton {{
    background: transparent;
    border: none;
    border-radius: 4px;
    color: {ICON};
    padding: 3px;
}}
QToolButton:hover {{ background: {HOVER}; color: {TEXT}; }}
QToolButton:pressed {{ background: {ACCENT_BG}; }}
QToolButton:checked {{ background: {ACCENT_BG}; color: {ACCENT}; }}
QToolButton:disabled {{ color: {DIM}; }}

QToolButton#sheettab {{
    border-radius: 0;
    padding: 0 14px;
    color: {MUTED};
    border-top: 2px solid transparent;
}}
QToolButton#sheettab:hover {{ background: {HOVER}; color: {TEXT}; }}
QToolButton#sheettab:checked {{ background: transparent; color: {ACCENT}; border-top: 2px solid {ACCENT}; }}
QToolButton#sheettab:checked:hover {{ background: {ACCENT_BG}; }}

QPushButton {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 12px;
    color: {TEXT};
}}
QPushButton:hover {{ background: {HOVER}; }}
QPushButton:default {{ border: 1px solid {ACCENT}; }}

QPushButton#chip {{
    background: {TAG_BG};
    color: {TAG};
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
}}
QPushButton#chip:hover {{ background: {HOVER}; }}

QComboBox {{
    background: {FIELD};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    color: {TEXT};
}}
QComboBox:hover {{ border: 1px solid {MENU_BORDER}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {MENU_BG};
    border: 1px solid {MENU_BORDER};
    color: {TEXT};
    selection-background-color: {HOVER};
    selection-color: {TEXT};
}}

QListWidget {{
    background: {PANEL};
    border: none;
    border-top: 1px solid {BORDER};
    outline: none;
}}
QListWidget::item {{
    border-bottom: 1px solid {BORDER};
    color: {TEXT};
}}
QListWidget::item:hover {{ background: {HOVER}; }}
QListWidget::item:selected {{ background: {ACCENT_BG}; color: {TEXT}; }}

QMenu {{
    background: {MENU_BG};
    border: 1px solid {MENU_BORDER};
    border-radius: 6px;
    padding: 6px;
}}
QMenu::item {{
    padding: 6px 28px 6px 10px;
    border-radius: 4px;
    color: {TEXT};
}}
QMenu::item:selected {{ background: {HOVER}; }}
QMenu::item:disabled {{ color: {DIM}; }}
QMenu::separator {{ height: 1px; background: {MENU_BORDER}; margin: 4px 4px; }}

QScrollBar:vertical {{ background: {BG}; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {SCROLL}; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: {BG}; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {SCROLL}; border-radius: 5px; min-width: 24px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

QTableView {{
    background: transparent;
    border: none;
    gridline-color: {CELL_BORDER};
    selection-background-color: transparent;
    outline: none;
}}
QTableView QTableCornerButton::section {{
    background: {PANEL};
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
}}
QHeaderView {{ background: {PANEL}; border: none; }}
QHeaderView::section {{ background: {PANEL}; border: none; }}

QMessageBox, QInputDialog, QDialog {{ background: {PANEL}; }}
QMessageBox QPushButton, QInputDialog QPushButton {{ min-width: 72px; }}
"""


apply_theme(DEFAULT_THEME)
