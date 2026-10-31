"""ServerLink: one WebSocket to the Vortex server, kept alive from a background thread.

Reconnects forever with backoff. Requests (login, logout, ...) are matched to
replies by req_id; everything else the server pushes goes to `on_event`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import socket
import threading
from typing import Any, Callable, Optional

import websockets

from . import __version__
from .config import ClientConfig

log = logging.getLogger("vortex.link")

OFFLINE_REPLY = {"ok": False, "error": "offline", "message": "The Vortex server is offline. Ask the counter."}


class ServerLink:
    def __init__(self, cfg: ClientConfig, on_event: Callable[[str, dict], None]):
        self.cfg = cfg
        self.on_event = on_event
        self.online = False
        self.welcome: Optional[dict] = None
        self.last_error: Optional[str] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws: Any = None
        self._stop = False
        self._pending: dict[int, asyncio.Future] = {}
        self._req_id = 0
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self._thread = threading.Thread(target=self._thread_main, name="vortex-link", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop = True
        loop, ws = self._loop, self._ws
        if loop is None or ws is None:
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            # Called from the link's own loop thread (e.g. handling a 'restart' command):
            # scheduling onto the same loop with run_coroutine_threadsafe would deadlock.
            loop.create_task(ws.close())
        else:
            try:
                asyncio.run_coroutine_threadsafe(ws.close(), loop)
            except Exception:
                pass

    def _thread_main(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run())
        finally:
            self._loop.close()

    # ------------------------------------------------------------ requests
    def request(self, msg: dict, timeout: float = 10.0) -> dict:
        """Thread-safe request/response. Returns a dict, never raises."""
        loop, ws = self._loop, self._ws
        if not self.online or loop is None or ws is None:
            return dict(OFFLINE_REPLY)
        fut = asyncio.run_coroutine_threadsafe(self._request(msg, timeout), loop)
        try:
            return fut.result(timeout + 2)
        except Exception as exc:  # timeout or socket died mid-request
            log.warning("request %s failed: %s", msg.get("type"), exc)
            return {"ok": False, "error": "timeout", "message": "The server did not answer. Try again."}

    async def _request(self, msg: dict, timeout: float) -> dict:
        self._req_id += 1
        rid = self._req_id
        msg["req_id"] = rid
        fut: asyncio.Future = self._loop.create_future()
        self._pending[rid] = fut
        try:
            await self._ws.send(json.dumps(msg))
            return await asyncio.wait_for(fut, timeout)
        finally:
            self._pending.pop(rid, None)

    def send(self, msg: dict) -> None:
        """Fire-and-forget (launch reports, heartbeats from other threads)."""
        loop, ws = self._loop, self._ws
        if self.online and loop is not None and ws is not None:
            asyncio.run_coroutine_threadsafe(ws.send(json.dumps(msg)), loop)

    # ------------------------------------------------------------ the loop
    def _hello(self) -> dict:
        return {
            "type": "hello",
            "station_name": self.cfg.station_name,
            "station_key": self.cfg.station_key,
            "hostname": socket.gethostname(),
            "version": __version__,
        }

    async def _heartbeat(self, ws: Any, every: int) -> None:
        while True:
            await asyncio.sleep(max(3, every))
            await ws.send(json.dumps({"type": "heartbeat"}))

    async def _run(self) -> None:
        url = self.cfg.server.rstrip("/") + "/ws/station"
        backoff = 1.0
        while not self._stop:
            hb: Optional[asyncio.Task] = None
            try:
                log.info("connecting to %s", url)
                async with websockets.connect(url, open_timeout=8, ping_interval=20, ping_timeout=20, max_size=2 ** 20) as ws:
                    self._ws = ws
                    await ws.send(json.dumps(self._hello()))
                    first = json.loads(await asyncio.wait_for(ws.recv(), 15))
                    if first.get("type") != "welcome":
                        # Rejected (disabled station, key mismatch, ...). Fall through to the
                        # backoff sleep below — do NOT `continue`, which would skip it and hammer
                        # the server with reconnects as fast as the CPU allows.
                        self.last_error = first.get("message") or first.get("code") or "rejected"
                        log.error("server rejected us: %s", self.last_error)
                        self.on_event("rejected", first)
                        backoff = 10.0
                    else:
                        self.welcome = first
                        self.last_error = None
                        self.online = True
                        backoff = 1.0
                        self.on_event("welcome", first)
                        hb = asyncio.create_task(self._heartbeat(ws, int(first.get("config", {}).get("heartbeat_seconds", 10))))
                        async for raw in ws:
                            try:
                                msg = json.loads(raw)
                            except ValueError:
                                continue
                            if not isinstance(msg, dict):
                                continue
                            rid = msg.get("req_id")
                            if rid is not None and rid in self._pending:
                                fut = self._pending[rid]
                                if not fut.done():
                                    fut.set_result(msg)
                                continue
                            if msg.get("type") == "pong":
                                continue
                            self.on_event(str(msg.get("type", "unknown")), msg)
            except Exception as exc:
                self.last_error = str(exc) or exc.__class__.__name__
                log.warning("link down: %s", self.last_error)
            finally:
                if hb:
                    hb.cancel()
                was_online = self.online
                self.online = False
                self._ws = None
                for fut in list(self._pending.values()):
                    if not fut.done():
                        fut.set_result(dict(OFFLINE_REPLY))
                self._pending.clear()
                if was_online:
                    self.on_event("link", {"online": False})
            if self._stop:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 15.0)
