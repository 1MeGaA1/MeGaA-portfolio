"""Load a QML file against the real backend and report every QML warning (+ an optional PNG).

    python tools/qml_harness.py FILE.qml [--png out.png] [--ms 900] [--workbook demo.gridpad]
                                [--size 1280x800] [--js "code"] [--visible] [--offscreen]

FILE.qml is quick/qml/Main.qml or a small test file that does `import "<path to quick/qml>"`.
The root object should be a Window / ApplicationWindow. It renders on the GPU like the real
app but stays invisible (transparent, behind everything, never focused) so tests never
disturb the desktop; --visible shows it normally.
--js runs after the delay with `win`, `backend`, `gridModel` in scope; its result is printed.
Without --workbook the demo workbook from tools/screenshot.py is used (in a temp folder),
and settings go to a temp ini so the user's own settings are never touched.
Exits 1 when the file fails to load or anything logs a warning.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("qml")
    ap.add_argument("--png")
    ap.add_argument("--ms", type=int, default=900)
    ap.add_argument("--workbook")
    ap.add_argument("--size", default="1280x800")
    ap.add_argument("--js")
    ap.add_argument("--offscreen", action="store_true")
    ap.add_argument("--visible", action="store_true")
    args = ap.parse_args()

    if args.offscreen:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if sys.platform == "win32":
            os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
    os.environ["QT_FORCE_STDERR_LOGGING"] = "1"

    from PySide6.QtCore import QSettings, Qt, QTimer, QUrl, qInstallMessageHandler, QtMsgType  # noqa: E402

    from app import theme  # noqa: E402
    from app.model import Workbook  # noqa: E402
    from quick.backend import Backend  # noqa: E402
    from quick.main import IconProvider, create_app  # noqa: E402
    from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent  # noqa: E402

    problems: list[str] = []

    def on_message(kind, _context, message) -> None:
        if kind in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            problems.append(message)
            print("WARNING:", message, flush=True)
        else:
            print("log:", message, flush=True)

    qInstallMessageHandler(on_message)
    app = create_app(["harness"])
    tmp = Path(tempfile.mkdtemp())
    settings = QSettings(str(tmp / "settings.ini"), QSettings.Format.IniFormat)
    theme.load_appearance(settings)
    if args.workbook:
        workbook = Workbook.load(args.workbook)
    else:
        from screenshot import demo_workbook  # noqa: E402
        workbook = demo_workbook(tmp / "demo.gridpad")
    backend = Backend(workbook, settings)

    engine = QQmlApplicationEngine()
    engine.addImageProvider("icons", IconProvider())
    ctx = engine.rootContext()
    ctx.setContextProperty("backend", backend)
    ctx.setContextProperty("gridModel", backend.model)
    ctx.setContextProperty("firstRowModel", backend.first_row)
    ctx.setContextProperty("themeSource", backend.palette)
    engine.warnings.connect(lambda errs: [problems.append(e.toString()) or print("WARNING:", e.toString())
                                          for e in errs])
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(Path(args.qml).resolve())))
    if component.isError():
        for err in component.errors():
            print("WARNING:", err.toString())
        print("FAILED: QML did not load")
        return 1
    win = component.beginCreate(ctx)
    if win is None:
        print("FAILED: QML did not load")
        return 1
    hidden = not args.visible and not args.offscreen
    if hidden:
        win.setProperty("visible", False)  # don't let `visible: true` pop it up before we hide it
    component.completeCreate()
    if component.isError():
        for err in component.errors():
            print("WARNING:", err.toString())
        print("FAILED: QML did not load")
        return 1
    w, h = (int(v) for v in args.size.lower().split("x"))
    try:
        win.setWidth(w)
        win.setHeight(h)
        if hidden:
            # Still a real, exposed, GPU-rendered window (so particles and shadows render), but
            # fully transparent, behind every other window, no taskbar button and never
            # activated: it can't flash on screen or steal the keyboard.
            win.setFlags(win.flags() | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus
                         | Qt.WindowType.WindowStaysOnBottomHint)
            win.setOpacity(0.0)
            win.setPosition(0, 0)
        win.show()
    except AttributeError:
        pass

    def finish() -> None:
        if args.js:
            from PySide6.QtQml import QQmlExpression  # noqa: E402
            ctx.setContextProperty("win", win)
            expr = QQmlExpression(ctx, win, f"(function(){{ {args.js} }})()")
            result = expr.evaluate()
            if expr.hasError():
                problems.append(expr.error().toString())
                print("WARNING: js:", expr.error().toString())
            print("js:", result[0] if isinstance(result, tuple) else result)
            app.processEvents()
        if args.png:
            image = win.grabWindow()
            image.save(args.png)
            print("saved", args.png, image.width(), "x", image.height())
        app.quit()

    QTimer.singleShot(args.ms, finish)
    app.exec()
    print(f"{len(problems)} warning(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
