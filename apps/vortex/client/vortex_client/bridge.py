"""Methods the page can call as  window.pywebview.api.<name>(...)  (each returns a Promise)."""
from __future__ import annotations

import logging
from typing import Optional

from . import peripherals

log = logging.getLogger("vortex.bridge")


class Bridge:
    def __init__(self, app) -> None:
        self._app = app

    def get_state(self) -> dict:
        return self._app.snapshot()

    def login(self, login: str, password: str) -> dict:
        return self._app.login(login or "", password or "")

    def register(self, email: str, password: str, username: Optional[str] = None) -> dict:
        return self._app.register(email or "", password or "", username or None)

    def logout(self) -> dict:
        return self._app.logout()

    def launch(self, kind: str, name: str) -> dict:
        return self._app.launch(kind or "game", name or "")

    def admin_exit(self, pin: str) -> dict:
        return self._app.admin_exit(str(pin or ""))

    def local_expired(self) -> dict:
        return self._app.local_expired()

    def peripherals(self) -> dict:
        return peripherals.snapshot()

    def log(self, text: str) -> None:
        log.info("ui: %s", text)
