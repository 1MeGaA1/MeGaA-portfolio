"""Controller: the bridge between the Vortex backend (server link, launcher, lockdown)
and the QML UI. Exposed to QML as the context property `vortex`.

Threading model:
- ServerLink calls on_event from its own asyncio thread. We turn each event into a Qt
  signal; Qt delivers signals to QML on the GUI thread via queued connections, so QML
  code always runs on the main thread.
- QML calls the @Slot methods (login, launch, ...) on the GUI thread. Those must never
  block the GUI thread (a blocked request would freeze the UI), so each runs its own
  worker thread and reports back through a signal.
"""
from __future__ import annotations

import logging
import subprocess
import threading

from PySide6.QtCore import QObject, Signal, Slot, Property, QTimer

from vortex_client import peripherals
from vortex_client.activity import ActivityReporter
from vortex_client.config import ClientConfig, save_config
from vortex_client.launcher import Launcher
from vortex_client.link import ServerLink
from vortex_client.lockdown import Lockdown

log = logging.getLogger("vortex.native.controller")

EXIT_ADMIN = 0
EXIT_RESTART = 3


class Controller(QObject):
    # ---- events pushed to QML (safe to emit from any thread) ----
    linkChanged = Signal(bool, str)                 # online, error
    welcomeReceived = Signal("QVariant")            # snapshot
    sessionChanged = Signal("QVariant")             # session dict or None
    sessionEnded = Signal(str, str)                 # reason, message
    warned = Signal(int, int)                       # remaining_seconds, threshold
    messaged = Signal(str, str, str)                # title, body, level
    stationLockChanged = Signal(bool)               # locked by staff
    adminExitRequested = Signal()                   # Ctrl+Shift+Q
    peripheralsChanged = Signal("QVariant")

    # ---- results of QML-initiated actions ----
    loginResult = Signal(bool, str, str)            # ok, error, message
    registerResult = Signal(bool, str, str)         # ok, error, message
    launchResult = Signal(str, bool, str)           # name, ok, message
    adminExitResult = Signal(bool, str)             # ok, message
    launchStateChanged = Signal(str, str)           # name, state (starting/running/exited)

    infoChanged = Signal()                          # cafe/station/version property change
    shopChanged = Signal()                          # shop menu replaced (welcome / 'shop' push)
    eventsChanged = Signal()                        # events replaced (welcome / 'events' push)
    orderResult = Signal(bool, str, "QVariant")     # ok, message, order view (or None)

    def __init__(self, cfg: ClientConfig, app):
        super().__init__()
        self.cfg = cfg
        self._app = app
        self._exit_code = EXIT_RESTART
        self._exiting = False
        self._station = None
        self._server_config = {}
        self._session = None
        self.link = ServerLink(cfg, self._on_server_event)
        self.launcher = Launcher(_load_catalog(), self._on_launch_event)
        self.lockdown = Lockdown(cfg.kiosk and not cfg.debug, cfg.block_alt_tab_in_session, self._on_admin_escape)
        # reports "what is this PC doing right now" (foreground app + running games) to staff
        self.activity = ActivityReporter(self.link.send, self.launcher.running,
                                         self.launcher.catalog, is_active=lambda: self._session is not None)
        # shop menu + events are managed in the admin panel and arrive with `welcome`
        # (then live via 'shop' / 'events' pushes); product pictures are served from
        # serverHttp + image_url
        self._shop: list = []
        self._events: list = []
        self._media_base = "/media"
        # periodic peripheral refresh for the account card
        self._periph_timer = QTimer(self)
        self._periph_timer.setInterval(15000)
        self._periph_timer.timeout.connect(self._emit_peripherals)

    # ------------------------------------------------------------ startup / properties
    def start(self, window_title: str) -> None:
        self.lockdown.find_window(window_title)
        self.lockdown.start()
        self.launcher.start()
        self.activity.start()
        self.link.start()
        self._periph_timer.start()
        QTimer.singleShot(400, self._emit_peripherals)

    def _get_cafe(self):
        return self._server_config.get("cafe_name", "VORTEX")

    def _get_station(self):
        return (self._station or {}).get("name") or self.cfg.station_name or "STATION"

    def _get_version(self):
        from . import __version__
        return __version__

    def _get_kiosk(self):
        return bool(self.cfg.kiosk and not self.cfg.debug)

    cafeName = Property(str, _get_cafe, notify=infoChanged)
    stationName = Property(str, _get_station, notify=infoChanged)
    version = Property(str, _get_version, constant=True)
    kiosk = Property(bool, _get_kiosk, constant=True)

    def _get_currency(self):
        # cafe currency from the server's welcome config (e.g. "EGP"); shop prices use it
        return self._server_config.get("currency") or "EGP"

    currency = Property(str, _get_currency, notify=infoChanged)

    def _get_server_http(self):
        # HTTP origin of the server (ws:// -> http://, wss:// -> https://, path dropped);
        # QML loads product pictures from serverHttp + image_url
        from urllib.parse import urlsplit
        server = (self.cfg.server or "").strip()
        if "://" not in server:
            server = "ws://" + server
        parts = urlsplit(server)
        if not parts.netloc:
            return ""
        scheme = "https" if parts.scheme.lower() == "wss" else "http"
        return f"{scheme}://{parts.netloc}"

    serverHttp = Property(str, _get_server_http, constant=True)

    # ------------------------------------------------------------ server events (link thread)
    def _on_server_event(self, kind: str, msg: dict) -> None:
        try:
            if kind == "welcome":
                if msg.get("station_key"):
                    self.cfg.station_key = msg["station_key"]
                    save_config(self.cfg)
                self._station = msg.get("station")
                self._server_config = msg.get("config") or {}
                self._session = msg.get("session")
                self._shop = list(msg.get("shop") or [])
                self._events = list(msg.get("events") or [])
                self._media_base = msg.get("media_base") or "/media"
                self.infoChanged.emit()
                self.linkChanged.emit(True, "")
                self.welcomeReceived.emit(self._snapshot())
                self.shopChanged.emit()
                self.eventsChanged.emit()
                if self._session is None:
                    self._set_locked(True)
                else:
                    self._set_locked(False)
                self.sessionChanged.emit(self._session)
            elif kind == "shop":
                self._shop = list(msg.get("items") or [])
                self.shopChanged.emit()
            elif kind == "events":
                self._events = list(msg.get("events") or [])
                self.eventsChanged.emit()
            elif kind == "order_update":
                self._order_update(msg.get("order") or {})
            elif kind == "link":
                self.linkChanged.emit(False, self.link.last_error or "")
            elif kind == "rejected":
                self.linkChanged.emit(False, msg.get("message") or msg.get("code") or "rejected")
            elif kind == "session_update":
                self._session = msg.get("session")
                if self._session:
                    self._set_locked(False)
                self.sessionChanged.emit(self._session)
                if msg.get("event") == "topup" and self._session:
                    self.messaged.emit("Time added", "Staff added time to your session.", "info")
            elif kind == "session_ended":
                self._session = None
                self.launcher.kill_all()
                self._set_locked(True)
                self.sessionChanged.emit(None)
                self.sessionEnded.emit(msg.get("reason") or "ended", msg.get("message") or "Session ended.")
            elif kind == "warning":
                self.warned.emit(int(msg.get("remaining_seconds", 0)), int(msg.get("threshold", 0)))
            elif kind == "message":
                self.messaged.emit(msg.get("title") or "", msg.get("body") or "", msg.get("level") or "info")
            elif kind == "command":
                self._command(str(msg.get("name")))
        except Exception:
            log.exception("server event %s failed", kind)

    def _order_update(self, order: dict) -> None:
        """Staff marked one of our orders done / cancelled -> toast on the kiosk."""
        what = f"{order.get('product_name') or 'Order'} x{order.get('qty') or 1}"
        total = f"{self._get_currency()} {self.money(int(order.get('total') or 0))}"
        status = order.get("status")
        if status == "done":
            self.messaged.emit("Order delivered", f"{what} — {total} paid at the counter", "info")
        elif status == "cancelled":
            self.messaged.emit("Order cancelled", f"{what} — {total} was cancelled by the counter", "info")

    def _command(self, name: str) -> None:
        log.info("command from staff: %s", name)
        if name in ("lock", "unlock"):
            if self._station is not None:
                self._station["locked"] = name == "lock"
            self.stationLockChanged.emit(name == "lock")
        elif name == "restart":
            self.quit(EXIT_RESTART)
        elif name == "reboot":
            subprocess.Popen(["shutdown", "/r", "/t", "3", "/f"])
        elif name == "shutdown":
            subprocess.Popen(["shutdown", "/s", "/t", "3", "/f"])

    def _on_launch_event(self, name: str, state: str, extra: dict) -> None:
        self.launchStateChanged.emit(name, state)
        if state == "exited":
            self.lockdown.bring_to_front()

    def _on_admin_escape(self) -> None:
        self.adminExitRequested.emit()

    def _set_locked(self, locked: bool) -> None:
        self.lockdown.locked = locked
        if locked:
            self.lockdown.bring_to_front()

    def _emit_peripherals(self) -> None:
        try:
            self.peripheralsChanged.emit(peripherals.snapshot())
        except Exception:
            log.debug("peripherals snapshot failed", exc_info=True)

    def _snapshot(self) -> dict:
        return {
            "online": self.link.online,
            "station": self._station,
            "config": self._server_config,
            "session": self._session,
        }

    # ------------------------------------------------------------ QML-invokable actions
    def _in_thread(self, fn) -> None:
        threading.Thread(target=fn, daemon=True).start()

    @Slot(str, str)
    def login(self, login: str, password: str) -> None:
        def work():
            res = self.link.request({"type": "login", "login": login, "password": password})
            if res.get("ok") and res.get("session"):
                self._session = res["session"]
                self._set_locked(False)
                self.sessionChanged.emit(self._session)
            self.loginResult.emit(bool(res.get("ok")), res.get("error") or "", res.get("message") or "")
        self._in_thread(work)

    @Slot(str, str, str)
    def register(self, email: str, password: str, username: str) -> None:
        def work():
            res = self.link.request({"type": "register", "email": email, "password": password,
                                     "username": username or None})
            self.registerResult.emit(bool(res.get("ok")), res.get("error") or "", res.get("message") or "")
        self._in_thread(work)

    @Slot()
    def logout(self) -> None:
        def work():
            res = self.link.request({"type": "logout"})
            if not res.get("ok"):
                self._session = None
                self.launcher.kill_all()
                self._set_locked(True)
                self.sessionChanged.emit(None)
                self.sessionEnded.emit("logout", "Logged out.")
        self._in_thread(work)

    @Slot(str, str)
    def launch(self, kind: str, name: str) -> None:
        if not self._session:
            self.launchResult.emit(name, False, "Log in first.")
            return
        def work():
            res = self.launcher.launch(kind, name)
            if res.get("ok"):
                self.link.send({"type": "launch_report", "item": name, "kind": kind})
            self.launchResult.emit(name, bool(res.get("ok")), res.get("message") or "")
        self._in_thread(work)

    @Slot(str)
    def adminExit(self, pin: str) -> None:
        def work():
            if self.link.online:
                res = self.link.request({"type": "admin_exit", "pin": pin})
            else:
                ok = bool(self.cfg.local_exit_pin) and pin == self.cfg.local_exit_pin
                res = {"ok": ok, "message": "" if ok else "Server offline and no local PIN matches."}
            self.adminExitResult.emit(bool(res.get("ok")), res.get("message") or "")
            if res.get("ok"):
                QTimer.singleShot(0, lambda: self.quit(EXIT_ADMIN))
        self._in_thread(work)

    @Slot()
    def localExpired(self) -> None:
        if self.link.online:
            return
        self._session = None
        self.launcher.kill_all()
        self._set_locked(True)
        self.sessionChanged.emit(None)
        self.sessionEnded.emit("expired", "Time is up. Top up at the counter.")

    @Slot(result="QVariant")
    def snapshot(self):
        return self._snapshot()

    _GENRE = {"fps": "FPS", "moba": "MOBA", "rpg": "RPG", "action": "Action", "sports": "Sports",
              "media": "Media", "social": "Social", "creative": "Creative",
              "browsers": "Browser", "launchers": "Launcher"}

    @staticmethod
    def _platform(entry: dict) -> str:
        target = (entry.get("launch") or entry.get("exe") or "").lower()
        for needle, label in (("steam://", "Steam"), ("epicgames", "Epic"), ("riot", "Riot"),
                              ("origin://", "EA"), ("electronic arts", "EA"), ("ea desktop", "EA"),
                              ("battlenet://", "Battle.net"), ("discord://", "Discord"),
                              ("spotify", "Spotify"), ("tg://", "Telegram")):
            if needle in target:
                return label
        return "PC" if entry.get("exe") else ""

    @classmethod
    def _list(cls, bucket: dict):
        out = []
        for name, entry in bucket.items():
            if name.startswith("_"):
                continue
            entry = entry if isinstance(entry, dict) else {}
            cat = entry.get("cat", "")
            genre = cls._GENRE.get(cat, cat.upper() if cat else "")
            plat = cls._platform(entry)
            sub = " · ".join(x for x in (genre, plat) if x)
            out.append({"name": name, "cat": cat, "sub": sub})
        return out

    @Slot(result="QVariant")
    def games(self):
        return self._list(self.launcher.catalog.get("games", {}))

    @Slot(result="QVariant")
    def apps(self):
        return self._list(self.launcher.catalog.get("apps", {}))

    @Slot(result="QVariant")
    def shop(self):
        """Enabled products as the server sent them: [{id, name, category, price(minor), image_url, best, ...}]."""
        return list(self._shop)

    @Slot(result="QVariant")
    def events(self):
        """Events listed on the Events page (enabled + show_events), as the server sent them."""
        return [e for e in self._events if e.get("show_events")]

    @Slot(result="QVariant")
    def featured(self):
        """The Home banner event (first with show_home) or None -> banner hidden."""
        for e in self._events:
            if e.get("show_home"):
                return e
        return None

    @Slot(int, int)
    def order(self, product_id: int, qty: int) -> None:
        """Send an order to the counter; the server needs an active session on this station."""
        def work():
            res = self.link.request({"type": "order", "product_id": int(product_id), "qty": int(qty)})
            ok = bool(res.get("ok"))
            self.orderResult.emit(ok, res.get("message") or ("" if ok else "Order failed. Ask the counter."),
                                  res.get("order"))
        self._in_thread(work)

    @Slot(int, result=str)
    def money(self, minor: int) -> str:
        """Minor units -> display amount: 2500 -> "25", 2550 -> "25.50"."""
        minor = int(minor)
        whole, cents = divmod(abs(minor), 100)
        sign = "-" if minor < 0 else ""
        return f"{sign}{whole}" if cents == 0 else f"{sign}{whole}.{cents:02d}"

    @Slot(result=bool)
    def requestClose(self) -> bool:
        return self.request_close()

    @Slot(result="QVariant")
    def peripheralsNow(self):
        try:
            return peripherals.snapshot()
        except Exception:
            return {}

    # ------------------------------------------------------------ shutdown
    def quit(self, code: int = EXIT_ADMIN) -> None:
        if self._exiting:
            return
        self._exiting = True
        self._exit_code = code
        log.info("quitting with code %s", code)
        for stop in (self.lockdown.stop, self.link.stop, self.launcher.stop, self.activity.stop):
            try:
                stop()
            except Exception:
                pass
        self._app.exit(code)

    @property
    def exit_code(self) -> int:
        return self._exit_code

    def request_close(self) -> bool:
        """Return True to allow the window to close. Kiosk mode blocks it."""
        if self._exiting:
            return True
        if self.cfg.kiosk and not self.cfg.debug:
            return False
        self.quit(EXIT_ADMIN)
        return True


def _load_catalog() -> dict:
    """Reuse the web client's catalog.json if present, else the built-in defaults."""
    from vortex_client.config import DEFAULT_CATALOG
    import json
    from pathlib import Path
    here = Path(__file__).resolve().parent.parent          # client-native
    candidates = [here / "catalog.json", here.parent / "client" / "catalog.json"]
    for p in candidates:
        if p.exists():
            try:
                d = json.loads(p.read_text("utf-8"))
                d.setdefault("games", {})
                d.setdefault("apps", {})
                return d
            except ValueError:
                pass
    return json.loads(json.dumps(DEFAULT_CATALOG))
