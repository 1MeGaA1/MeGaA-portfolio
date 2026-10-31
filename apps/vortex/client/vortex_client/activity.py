"""Report what this station is doing right now (foreground app + running games).

A tiny background thread samples the active window every few seconds and, when it
changes, sends an `activity` message to the server. The counter/admin panels show it
so staff can see at a glance what each PC is on. Windows-only detection via ctypes
(no extra dependency); on other platforms it degrades to "just the running list".
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Callable, Optional

log = logging.getLogger("vortex.activity")


def foreground_window() -> dict:
    """Return {"proc": <process.exe>, "title": <window title>} for the focused window."""
    if sys.platform != "win32":
        return {}
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {}
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = (buf.value or "").strip()
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc = ""
        try:
            import psutil
            proc = psutil.Process(pid.value).name()
        except Exception:
            proc = ""
        return {"proc": proc, "title": title}
    except Exception:
        log.debug("foreground_window failed", exc_info=True)
        return {}


class ActivityReporter:
    """Polls the foreground app + the launcher's running list and pushes changes."""

    def __init__(self, send: Callable[[dict], None], running_fn: Callable[[], list],
                 catalog: dict, is_active: Optional[Callable[[], bool]] = None,
                 interval: float = 3.0):
        self.send = send
        self.running_fn = running_fn
        self.catalog = catalog or {}
        self.is_active = is_active
        self.interval = interval
        self._own = os.path.basename(sys.executable or "").lower()  # our own window is not "activity"
        self._stop = False
        self._last: Optional[dict] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="vortex-activity", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop = True

    # ------------------------------------------------------------ sampling
    def _friendly(self, proc: str, title: str) -> Optional[str]:
        """Map a raw process name to a catalog game/app key when we can; else clean it up."""
        pl = (proc or "").lower()
        if not pl:
            return None
        for bucket in ("games", "apps"):
            for name, entry in (self.catalog.get(bucket) or {}).items():
                if name.startswith("_") or not isinstance(entry, dict):
                    continue
                ep = (entry.get("process") or "").lower()
                ex = os.path.basename(entry.get("exe") or "").lower()
                if pl == ep or (ex and pl == ex):
                    return name
        return proc[:-4] if pl.endswith(".exe") else proc

    def sample(self) -> dict:
        # Idle/locked PC: don't leak the lock screen as "activity".
        if self.is_active is not None and not self.is_active():
            return {"foreground": None, "title": "", "proc": "", "running": []}
        fg = foreground_window()
        proc, title = fg.get("proc", ""), fg.get("title", "")
        if proc and self._own and proc.lower() == self._own:
            proc, title = "", ""   # the customer is on the Vortex launcher itself, not an app
        running = []
        try:
            running = list(self.running_fn() or [])
        except Exception:
            running = []
        return {"foreground": self._friendly(proc, title), "title": title, "proc": proc, "running": running}

    def _run(self) -> None:
        while not self._stop:
            try:
                act = self.sample()
                if act != self._last:
                    self._last = act
                    try:
                        self.send({"type": "activity", **act})
                    except Exception:
                        log.debug("activity send failed", exc_info=True)
            except Exception:
                log.debug("activity sample failed", exc_info=True)
            time.sleep(self.interval)
