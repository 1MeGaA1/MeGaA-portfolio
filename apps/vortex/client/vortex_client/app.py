"""VortexApp: the kiosk window plus everything wired around it."""
from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from typing import Any, Optional

import webview

from . import __version__, peripherals
from .bridge import Bridge
from .config import BASE_DIR, LOG_PATH, UI_DIR, load_catalog, load_config, save_config
from .launcher import Launcher
from .link import ServerLink
from .lockdown import Lockdown

log = logging.getLogger("vortex.app")

EXIT_ADMIN = 0        # run_client.bat stops looping
EXIT_RESTART = 3      # run_client.bat starts us again


def setup_logging(debug: bool) -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    fh = RotatingFileHandler(LOG_PATH, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)


class VortexApp:
    TITLE = "Vortex Kiosk"

    def __init__(self) -> None:
        self.cfg = load_config()
        setup_logging(self.cfg.debug)
        self.catalog = load_catalog()
        self.window: Any = None
        self.session: Optional[dict] = None
        self.station: Optional[dict] = None
        self.server_config: dict = {}
        self.exit_code = EXIT_RESTART
        self._exiting = False
        self._page_ready = threading.Event()
        self._push_q: "queue.Queue" = queue.Queue()
        self.link = ServerLink(self.cfg, self._on_server_event)
        self.launcher = Launcher(self.catalog, self._on_launch_event)
        self.lockdown = Lockdown(self.cfg.kiosk and not self.cfg.debug, self.cfg.block_alt_tab_in_session, self._on_admin_escape)

    # ------------------------------------------------------------ window
    def run(self) -> int:
        log.info("Vortex client %s starting; server=%s station=%s", __version__, self.cfg.server, self.cfg.station_name)
        kiosk = self.cfg.kiosk and not self.cfg.debug
        try:
            webview.settings["ALLOW_DOWNLOADS"] = False
            webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
        except Exception:
            pass
        self.window = webview.create_window(
            self.TITLE,
            # A plain file:// URL. Never append a query string here: .NET's Uri treats "?x=1"
            # as part of a file path and WebView2 shows ERR_FILE_NOT_FOUND. The page detects
            # kiosk mode through window.chrome.webview instead (see ui/vortex-bridge.js).
            url=(UI_DIR / "index.html").as_uri(),
            js_api=Bridge(self),
            fullscreen=self.cfg.fullscreen and not self.cfg.debug,
            frameless=kiosk,
            on_top=kiosk,
            easy_drag=False,
            background_color="#05050c",
            width=1280,
            height=800,
            min_size=(1024, 640),
            text_select=False,
        )
        self.window.events.loaded += self._on_page_loaded
        self.window.events.closing += self._on_closing
        # A dedicated, persistent WebView2 profile beside client.json: predictable, easy to
        # clear, and never shares the global pywebview folder with other apps or instances.
        profile = str(BASE_DIR / "webview2-profile")
        webview.start(self._after_start, gui="edgechromium", debug=self.cfg.debug,
                      private_mode=False, storage_path=profile)
        log.info("window closed, exit code %s", self.exit_code)
        return self.exit_code

    def _after_start(self) -> None:
        """Runs in a worker thread once the GUI loop is up."""
        threading.Thread(target=self._pusher, name="vortex-pusher", daemon=True).start()
        self.lockdown.find_window(self.TITLE)
        self.lockdown.start()
        self.launcher.start()
        self.link.start()

    def _pusher(self) -> None:
        """Drains UI pushes on a dedicated thread. evaluate_js is synchronous and can block
        (a slow or occluded WebView2), so it must never run on the link/receive thread — else
        one stuck push would stall every server event, including session_ended."""
        while not self._exiting:
            try:
                js = self._push_q.get(timeout=0.5)
            except queue.Empty:
                continue
            if js is None:
                break
            try:
                self.window.evaluate_js(js)
            except Exception as exc:
                log.debug("push eval failed: %s", exc)

    def _on_page_loaded(self) -> None:
        self._page_ready.set()
        # Prove the kiosk page really loaded (a wrong URL shows a WebView2 error page instead).
        try:
            url = self.window.get_current_url()
            info = self.window.evaluate_js("({title: document.title, bridge: !!window.Vortex, mode: window.Vortex && window.Vortex.mode})")
        except Exception as exc:
            url, info = "?", {"error": str(exc)}
        if isinstance(info, dict) and info.get("bridge"):
            log.info("page loaded: %s (%s) at %s", info.get("title"), info.get("mode"), url)
        else:
            log.error("PAGE FAILED TO LOAD: url=%s info=%s", url, info)
        self.push("state", self.snapshot())

    def _on_closing(self) -> bool:
        # pywebview CANCELS the close when this returns False.
        if self._exiting:
            return True                     # we initiated it (admin PIN / restart command) — allow
        if self.cfg.kiosk and not self.cfg.debug:
            log.info("close blocked: kiosk mode (use Ctrl+Shift+Q + staff PIN to exit)")
            return False                    # a customer must not be able to close the kiosk
        # Windowed / dev mode: the user closed the window on purpose. Allow it, and exit with
        # code 0 so run_client.bat's watchdog does NOT relaunch it.
        log.info("window closed by user; exiting")
        self.exit_code = EXIT_ADMIN
        self._exiting = True
        for stop in (self.lockdown.stop, self.link.stop, self.launcher.stop):
            try:
                stop()
            except Exception:
                pass
        return True

    def push(self, event: str, data: Optional[dict] = None) -> None:
        """Queue a UI update. Non-blocking on purpose — the actual (blocking) evaluate_js
        runs on the pusher thread, so a slow WebView2 never stalls the caller (usually the
        link receive thread)."""
        if not self.window:
            return
        js = "window.Vortex && window.Vortex._dispatch(%s, %s)" % (json.dumps(event), json.dumps(data or {}))
        self._push_q.put(js)

    def snapshot(self) -> dict:
        return {
            "online": self.link.online,
            "station": self.station,
            "config": self.server_config,
            "session": self.session,
            "client": {"station_name": self.cfg.station_name, "server": self.cfg.server,
                       "version": __version__, "kiosk": self.cfg.kiosk, "error": self.link.last_error},
            "peripherals": peripherals.snapshot(),
            "running": self.launcher.running(),
        }

    # ------------------------------------------------------------ server events
    def _set_locked(self, locked: bool) -> None:
        self.lockdown.locked = locked
        if locked:
            self.lockdown.bring_to_front()

    def _on_server_event(self, kind: str, msg: dict) -> None:
        try:
            if kind == "welcome":
                if msg.get("station_key"):
                    self.cfg.station_key = msg["station_key"]
                    save_config(self.cfg)
                    log.info("station key saved")
                self.station = msg.get("station")
                self.server_config = msg.get("config") or {}
                self.session = msg.get("session")
                self._set_locked(self.session is None)
                self.push("welcome", self.snapshot())
            elif kind == "link":
                self.push("link", {"online": False, "error": self.link.last_error})
            elif kind == "rejected":
                self.push("rejected", {"code": msg.get("code"), "message": msg.get("message")})
            elif kind == "session_update":
                self.session = msg.get("session")
                if self.session:
                    self._set_locked(False)
                self.push("session_update", {"session": self.session, "event": msg.get("event")})
            elif kind == "session_ended":
                self.session = None
                self.launcher.kill_all()
                self._set_locked(True)
                self.push("session_ended", {"reason": msg.get("reason"), "message": msg.get("message")})
            elif kind == "command":
                self._command(str(msg.get("name")))
            elif kind in ("warning", "message", "error"):
                self.push(kind, msg)
            else:
                log.debug("unhandled server event %s", kind)
        except Exception:
            log.exception("server event %s failed", kind)

    def _command(self, name: str) -> None:
        log.info("command from staff: %s", name)
        if name in ("lock", "unlock"):
            if self.station is not None:
                self.station["locked"] = name == "lock"
            self.push("station_locked", {"locked": name == "lock"})
        elif name == "restart":
            self.exit(EXIT_RESTART)
        elif name == "reboot":
            subprocess.Popen(["shutdown", "/r", "/t", "3", "/f"])
        elif name == "shutdown":
            subprocess.Popen(["shutdown", "/s", "/t", "3", "/f"])

    def _on_launch_event(self, name: str, state: str, extra: dict) -> None:
        self.push("launch", {"name": name, "state": state, **extra})
        if state == "exited":
            self.lockdown.bring_to_front()

    def _on_admin_escape(self) -> None:
        self.push("admin_exit_requested", {})

    # ------------------------------------------------------------ bridge operations
    def login(self, login: str, password: str) -> dict:
        res = self.link.request({"type": "login", "login": login, "password": password})
        if res.get("ok") and res.get("session"):
            self.session = res["session"]
            self._set_locked(False)
        return res

    def register(self, email: str, password: str, username: Optional[str]) -> dict:
        return self.link.request({"type": "register", "email": email, "password": password, "username": username})

    def logout(self) -> dict:
        res = self.link.request({"type": "logout"})
        # the server also pushes session_ended; if we are offline, lock locally
        if not res.get("ok"):
            self.session = None
            self.launcher.kill_all()
            self._set_locked(True)
        return res

    def local_expired(self) -> dict:
        """The page counted down to zero while the server was unreachable."""
        if self.link.online:
            return {"ok": True, "ignored": True}
        self.session = None
        self.launcher.kill_all()
        self._set_locked(True)
        return {"ok": True}

    def launch(self, kind: str, name: str) -> dict:
        if not self.session:
            return {"ok": False, "error": "no_session", "message": "Log in first."}
        res = self.launcher.launch(kind, name)
        if res.get("ok"):
            self.link.send({"type": "launch_report", "item": name, "kind": kind})
        return res

    def admin_exit(self, pin: str) -> dict:
        if self.link.online:
            res = self.link.request({"type": "admin_exit", "pin": pin})
        else:
            ok = bool(self.cfg.local_exit_pin) and pin == self.cfg.local_exit_pin
            res = {"ok": ok, "error": None if ok else "bad_pin",
                   "message": None if ok else "Server offline and no local PIN matches."}
        if res.get("ok"):
            log.warning("admin exit accepted")
            threading.Timer(0.4, lambda: self.exit(EXIT_ADMIN)).start()
        return res

    def exit(self, code: int) -> None:
        if self._exiting:
            return
        self.exit_code = code
        self._exiting = True
        log.info("exiting with code %s", code)
        # Arm the hard kill FIRST, before any teardown that might block or throw (e.g.
        # link.stop() runs on the link's own loop thread). os._exit ignores the GUI state,
        # so the watchdog can always restart the kiosk.
        t = threading.Timer(2.0, lambda: os._exit(self.exit_code))
        t.daemon = True
        t.start()
        for name, stop in (("lockdown", self.lockdown.stop), ("link", self.link.stop), ("launcher", self.launcher.stop)):
            try:
                stop()
            except Exception:
                log.exception("%s.stop() failed during exit", name)
        try:
            self.window.destroy()
        except Exception:
            pass


def main() -> None:
    app = VortexApp()
    code = app.run()
    time.sleep(0.2)
    sys.exit(code)
