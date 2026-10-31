"""WebSocket hub: which stations and admin screens are connected right now."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

log = logging.getLogger("vortex.ws")


class Hub:
    def __init__(self) -> None:
        self.stations: dict[int, WebSocket] = {}
        self.admins: set[WebSocket] = set()

    # -- stations ----------------------------------------------------------
    def is_station_online(self, station_id: int) -> bool:
        return station_id in self.stations

    def online_station_ids(self) -> set[int]:
        return set(self.stations)

    async def attach_station(self, station_id: int, ws: WebSocket) -> None:
        old = self.stations.get(station_id)
        if old is not None and old is not ws:
            # A second client claimed the same station: drop the stale socket.
            try:
                await old.send_json({"type": "error", "code": "replaced", "message": "Another client connected as this station."})
                await old.close(code=4001)
            except Exception:
                pass
        self.stations[station_id] = ws

    def detach_station(self, station_id: int, ws: WebSocket) -> None:
        if self.stations.get(station_id) is ws:
            self.stations.pop(station_id, None)

    async def send_station(self, station_id: int, message: dict[str, Any]) -> bool:
        ws = self.stations.get(station_id)
        if ws is None:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception as exc:  # socket died mid-send
            log.warning("station %s send failed: %s", station_id, exc)
            self.stations.pop(station_id, None)
            return False

    # -- admins ------------------------------------------------------------
    def attach_admin(self, ws: WebSocket) -> None:
        self.admins.add(ws)

    def detach_admin(self, ws: WebSocket) -> None:
        self.admins.discard(ws)

    async def broadcast_admin(self, message: dict[str, Any]) -> None:
        for ws in list(self.admins):
            try:
                await ws.send_json(message)
            except Exception:
                self.admins.discard(ws)
