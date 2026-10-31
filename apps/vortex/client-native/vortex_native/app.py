"""Entry point for the native Vortex kiosk (PySide6 + QML)."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from vortex_client import config as vc_config
from vortex_client.config import load_config

from .controller import Controller

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    BUNDLE = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent.parent      # client-native
    BUNDLE = BASE_DIR
QML_DIR = BUNDLE / "qml"
FONT_DIR = BUNDLE / "fonts"
LOG_PATH = BASE_DIR / "client-native.log"

log = logging.getLogger("vortex.native")


def setup_logging(debug: bool) -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    try:
        fh = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)


def load_fonts() -> None:
    if not FONT_DIR.exists():
        log.warning("no font dir; using system fonts")
        return
    loaded = 0
    for ttf in FONT_DIR.glob("*.ttf"):
        if QFontDatabase.addApplicationFont(str(ttf)) != -1:
            loaded += 1
        else:
            log.warning("could not load font %s", ttf.name)
    log.info("loaded %d fonts", loaded)


def main() -> int:
    # Keep the native client's own client.json / catalog.json (not the web client's).
    vc_config.CONFIG_PATH = BASE_DIR / "client.json"
    vc_config.CATALOG_PATH = BASE_DIR / "catalog.json"
    cfg = load_config()
    setup_logging(cfg.debug)
    log.info("Vortex native client starting; server=%s station=%s kiosk=%s",
             cfg.server, cfg.station_name, cfg.kiosk and not cfg.debug)

    # Kiosk stays on top; the frameless/fullscreen decision is made in QML from vortex.kiosk.
    QGuiApplication.setApplicationName("Vortex")
    QGuiApplication.setOrganizationName("Vortex")
    app = QGuiApplication(sys.argv)
    load_fonts()

    controller = Controller(cfg, app)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("vortex", controller)
    engine.addImportPath(str(QML_DIR))

    main_qml = QML_DIR / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(main_qml)))
    if not engine.rootObjects():
        log.error("QML failed to load: %s", main_qml)
        return 2

    controller.start("Vortex")
    code = app.exec()
    log.info("native client exited with code %s", controller.exit_code)
    return controller.exit_code


if __name__ == "__main__":
    sys.exit(main())
