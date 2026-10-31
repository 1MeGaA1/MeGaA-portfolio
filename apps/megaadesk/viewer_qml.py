"""
MeGaADesk QML viewer (PySide6 / Qt Quick).

GPU-composited remote screen with a Qt Quick front-end. The pure-stdlib engine
(capture/codec/crypto/protocol) is unchanged; this only replaces the display and
input layer. The controlled host needs no dependencies; only this viewer machine
needs PySide6.

Usage:
  python viewer_qml.py                                   # opens the connect UI
  python viewer_qml.py --host 192.168.1.50 --password S  # auto-connect (direct)
  python viewer_qml.py --relay host:7000 --id PC01 --password S
"""
import argparse
import socket
import sys
import threading

from PySide6.QtCore import Qt, QObject, Signal, Slot, QRectF, QUrl, QTimer
from PySide6.QtGui import QGuiApplication, QImage, QColor
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
from PySide6.QtQuick import QQuickPaintedItem, QQuickItem

from common import framec, protocol

_QT_BTN = {Qt.LeftButton: 0, Qt.RightButton: 1, Qt.MiddleButton: 2}


class RemoteScreen(QQuickPaintedItem):
    """Qt Quick item that paints the remote frame and captures input."""

    inputMouse = Signal(int, int, int, int)  # kind, x, y, data (remote pixels)
    inputKey = Signal(bool, int)             # down, virtual-key

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptedMouseButtons(Qt.AllButtons)
        self.setAcceptHoverEvents(True)
        self.setFlag(QQuickItem.ItemAcceptsInputMethod, True)
        self._img = QImage(1, 1, QImage.Format_RGB888)
        self._img.fill(QColor("black"))
        self._rw, self._rh = 1, 1
        self._scale, self._ox, self._oy = 1.0, 0.0, 0.0

    def set_remote_size(self, w, h):
        self._rw, self._rh = w, h

    @Slot(QImage)
    def show_frame(self, img):
        self._img = img
        self.update()

    def paint(self, painter):
        iw, ih = self.width(), self.height()
        painter.fillRect(QRectF(0, 0, iw, ih), QColor("black"))
        if self._rw <= 0 or self._rh <= 0:
            return
        self._scale = min(iw / self._rw, ih / self._rh)
        dw, dh = self._rw * self._scale, self._rh * self._scale
        self._ox, self._oy = (iw - dw) / 2, (ih - dh) / 2
        painter.drawImage(QRectF(self._ox, self._oy, dw, dh), self._img)

    # --- input mapping ----------------------------------------------------
    def _map(self, px, py):
        if self._scale <= 0:
            return 0, 0
        rx = int((px - self._ox) / self._scale)
        ry = int((py - self._oy) / self._scale)
        return max(0, min(self._rw - 1, rx)), max(0, min(self._rh - 1, ry))

    def hoverMoveEvent(self, e):
        x, y = self._map(e.position().x(), e.position().y())
        self.inputMouse.emit(protocol.M_MOVE, x, y, 0)

    def mouseMoveEvent(self, e):
        x, y = self._map(e.position().x(), e.position().y())
        self.inputMouse.emit(protocol.M_MOVE, x, y, 0)

    def mousePressEvent(self, e):
        self.forceActiveFocus()
        x, y = self._map(e.position().x(), e.position().y())
        self.inputMouse.emit(protocol.M_DOWN, x, y, _QT_BTN.get(e.button(), 0))

    def mouseReleaseEvent(self, e):
        x, y = self._map(e.position().x(), e.position().y())
        self.inputMouse.emit(protocol.M_UP, x, y, _QT_BTN.get(e.button(), 0))

    def wheelEvent(self, e):
        self.inputMouse.emit(protocol.M_WHEEL, 0, 0, int(e.angleDelta().y() / 120))

    def keyPressEvent(self, e):
        vk = e.nativeVirtualKey()
        if vk:
            self.inputKey.emit(True, vk)

    def keyReleaseEvent(self, e):
        vk = e.nativeVirtualKey()
        if vk:
            self.inputKey.emit(False, vk)


class Backend(QObject):
    """Owns the network connection; bridges frames/input to the QML item."""

    connected = Signal(int, int)   # w, h
    failed = Signal(str)
    disconnected = Signal()
    frameReady = Signal(QImage)

    def __init__(self):
        super().__init__()
        self.chan = None
        self.screen = None
        self._stop = threading.Event()

    def attach_screen(self, screen):
        self.screen = screen
        self.frameReady.connect(screen.show_frame)
        screen.inputMouse.connect(self._on_mouse)
        screen.inputKey.connect(self._on_key)

    # --- QML-invoked slots ------------------------------------------------
    @Slot(str, int, str)
    def connectDirect(self, host, port, password):
        self._start(lambda: socket.create_connection((host, int(port)), timeout=10), password)

    @Slot(str, str, str)
    def connectRelay(self, relay, host_id, password):
        def mk():
            from common import relaylink
            return relaylink.viewer_connect(relay, host_id)
        self._start(mk, password)

    @Slot()
    def disconnect(self):
        self._stop.set()
        if self.chan:
            self.chan.close()

    # --- input handlers (GUI thread) --------------------------------------
    def _on_mouse(self, kind, x, y, data):
        if self.chan:
            try:
                self.chan.send(protocol.OP_MOUSE, protocol.pack_mouse(kind, x, y, data))
            except OSError:
                pass

    def _on_key(self, down, vk):
        if self.chan:
            try:
                self.chan.send(protocol.OP_KEY, protocol.pack_key(down, vk))
            except OSError:
                pass

    # --- worker -----------------------------------------------------------
    def _start(self, connect_fn, password):
        self._stop.clear()
        threading.Thread(target=self._worker, args=(connect_fn, password), daemon=True).start()

    def _worker(self, connect_fn, password):
        try:
            sock = connect_fn()
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            chan = protocol.viewer_handshake(sock, password)
            op, payload = chan.recv()
        except ValueError:
            self.failed.emit("Wrong password (authentication rejected).")
            return
        except (OSError, ConnectionError) as e:
            self.failed.emit(f"Connection failed: {e}")
            return
        if op != protocol.OP_SCREEN_INFO:
            self.failed.emit("Protocol error: expected screen info.")
            return

        w, h, sh = protocol.unpack_screen_info(payload)
        self.chan = chan
        self.screen.set_remote_size(w, h)
        self.connected.emit(w, h)

        fb = framec.FrameBuffer(w, h, sh)
        stride = w * 3
        while not self._stop.is_set():
            try:
                op, payload = chan.recv()
            except (OSError, ConnectionError, ValueError):
                break
            if op == protocol.OP_FRAME:
                fb.apply_packed(payload)
                # deep-copy so the QImage owns its pixels across threads
                img = QImage(bytes(fb.buf), w, h, stride, QImage.Format_RGB888)
                self.frameReady.emit(img.copy())
        self.disconnected.emit()


def main():
    ap = argparse.ArgumentParser(description="MeGaADesk QML viewer.")
    ap.add_argument("--password")
    ap.add_argument("--host")
    ap.add_argument("--port", type=int, default=7777)
    ap.add_argument("--relay")
    ap.add_argument("--id", dest="host_id")
    ap.add_argument("--selftest", type=float, default=0, help="auto-quit after N seconds (dev)")
    args = ap.parse_args()

    app = QGuiApplication(sys.argv)
    qmlRegisterType(RemoteScreen, "MeGaADesk", 1, 0, "RemoteScreen")
    backend = Backend()

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    import os
    engine.load(QUrl.fromLocalFile(os.path.join(os.path.dirname(__file__), "qml", "main.qml")))
    if not engine.rootObjects():
        sys.exit("Failed to load QML.")

    win = engine.rootObjects()[0]
    screen = win.findChild(RemoteScreen, "remoteScreen")
    backend.attach_screen(screen)

    # optional auto-connect for testing / launchers
    if args.password and (args.host or args.relay):
        if args.relay:
            QTimer.singleShot(200, lambda: backend.connectRelay(args.relay, args.host_id or "", args.password))
        else:
            QTimer.singleShot(200, lambda: backend.connectDirect(args.host, args.port, args.password))

    if args.selftest:
        got = {"frames": 0}
        backend.frameReady.connect(lambda *_: got.__setitem__("frames", got["frames"] + 1))
        def done():
            print(f"selftest: received {got['frames']} frames")
            app.quit()
        QTimer.singleShot(int(args.selftest * 1000), done)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
