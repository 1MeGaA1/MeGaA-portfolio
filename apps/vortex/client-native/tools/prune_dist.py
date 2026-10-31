"""Trim the PyInstaller build of unused Qt modules + dev files.

--collect-all PySide6 (needed so the QtQuick QML modules get bundled) pulls in ~670 MB
of Qt, most of it unused (WebEngine, Quick3D, Pdf, docs, headers). This removes the parts
the native client never touches, bringing the folder to ~335 MB. Safe: the app uses only
QtQuick, QtQuick.Controls.Basic, QtQuick.Layouts, QtQuick.Shapes.

Run after build:  python tools/prune_dist.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

DIST = Path(__file__).resolve().parent.parent / "dist" / "VortexClientNative" / "_internal" / "PySide6"

DEV_DIRS = ["doc", "glue", "include", "typesystems", "support", "examples", "scripts",
            "metatypes", "translations"]
# unused QML module dirs under PySide6/qml
QML_DIRS = ["QtQuick3D", "QtWebEngine", "Qt3D", "QtCharts", "QtDataVisualization",
            "QtVirtualKeyboard", "QtMultimedia", "QtPositioning", "QtSensors", "QtTest",
            "QtWebSockets", "QtWebChannel", "QtLocation", "QtQuick/VirtualKeyboard"]
# unused Qt6 module runtime prefixes (Qt6<X>.dll and Qt<X>.pyd)
MOD = ["WebEngineCore", "WebEngineWidgets", "WebEngineQuick", "Quick3D", "Quick3DRuntimeRender",
       "Quick3DUtils", "Quick3DAssetImport", "Quick3DAssetUtils", "Quick3DParticles",
       "Quick3DPhysics", "Qt3DCore", "Qt3DRender", "Qt3DExtras", "Qt3DInput", "Qt3DLogic",
       "Qt3DAnimation", "Qt3DQuick", "Pdf", "PdfWidgets", "PdfQuick", "Charts", "ChartsQml",
       "DataVisualization", "DataVisualizationQml", "VirtualKeyboard", "Multimedia",
       "MultimediaWidgets", "MultimediaQuick", "Sensors", "SensorsQuick", "Positioning",
       "PositioningQuick", "Bluetooth", "Nfc", "SerialPort", "SerialBus", "WebSockets",
       "WebChannel", "WebChannelQuick", "RemoteObjects", "RemoteObjectsQml", "Help",
       "Designer", "DesignerComponents", "UiTools", "Test", "Sql", "TextToSpeech",
       "SpatialAudio", "Location"]


def main() -> None:
    if not DIST.exists():
        sys.exit(f"no build to prune at {DIST}")
    before = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    for d in DEV_DIRS:
        shutil.rmtree(DIST / d, ignore_errors=True)
    for d in QML_DIRS:
        shutil.rmtree(DIST / "qml" / d, ignore_errors=True)
    for f in DIST.glob("*.rst"):
        f.unlink(missing_ok=True)
    for m in MOD:
        (DIST / f"Qt6{m}.dll").unlink(missing_ok=True)
        (DIST / f"Qt{m}.pyd").unlink(missing_ok=True)
    after = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    print(f"pruned {(before - after) / 1e6:.0f} MB  ({before/1e6:.0f} -> {after/1e6:.0f} MB)")


if __name__ == "__main__":
    main()
