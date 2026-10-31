"""Station WebSocket protocol: what a kiosk may say, and what it gets back.

See docs/PROTOCOL.md for the message catalogue.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from .engine import Engine, EngineError

log = logging.getLogger("vortex.protocol")

Send = Callable[[dict[str, Any]], Awaitable[None]]


async def handle_station_message(engine: Engine, station_id: int, send: Send, msg: dict[str, Any]) -> None:
    kind = msg.get("type")
    req_id = msg.get("req_id")

    async def reply(result_type: str, **payload: Any) -> None:
        body = {"type": result_type, "req_id": req_id}
        body.update(payload)
        await send(body)

    try:
        if kind == "heartbeat":
            engine.touch_station(station_id)
            await send({"type": "pong", "server_time": engine.now_iso()})

        elif kind == "login":
            member = engine.authenticate_member(msg.get("login") or msg.get("email") or "", msg.get("password") or "")
            if member is None:
                await reply("login_result", ok=False, error="bad_credentials", message="Wrong email or password.")
                return
            session = await engine.start_session(station_id, member_id=member["id"], started_by="client")
            await reply("login_result", ok=True, session=session, member=engine.member_public(member))

        elif kind == "register":
            member = engine.create_member(msg.get("email") or "", msg.get("password") or "", msg.get("username"))
            engine.audit(None, "member.register.kiosk", member["username"])
            await reply("register_result", ok=True, member=member,
                        message="Account created. Ask the counter to add time, then log in.")

        elif kind == "logout":
            sess = engine.active_session_row(station_id)
            if sess is None:
                await reply("logout_result", ok=True, session=None)
            else:
                view = await engine.end_session(sess["id"], "logout")
                await reply("logout_result", ok=True, session=view)

        elif kind == "state":
            sess = engine.active_session_row(station_id)
            await reply("session_update", session=engine.session_view(sess) if sess else None)

        elif kind == "admin_exit":
            staff = engine.verify_exit_pin(str(msg.get("pin") or ""))
            station = engine.station_row(station_id)
            if staff is None:
                engine.audit(None, "kiosk.exit.denied", station["name"] if station else "")
                await reply("admin_exit_result", ok=False, error="bad_pin", message="Wrong PIN.")
            else:
                engine.audit(staff["id"], "kiosk.exit", station["name"] if station else "")
                await reply("admin_exit_result", ok=True)

        elif kind == "launch_report":
            station = engine.station_row(station_id)
            engine.audit(None, "kiosk.launch", f"{station['name'] if station else station_id}: {msg.get('item', '?')}")

        elif kind == "order":
            # Shop order from the kiosk: needs a running session; paid at the counter.
            order = await engine.create_order(station_id, msg.get("product_id"), msg.get("qty", 1), msg.get("note"))
            await reply("order_result", ok=True, order=order)

        elif kind == "activity":
            # Live "what is this PC doing right now" report: foreground app + open games.
            engine.set_activity(station_id, {
                "foreground": msg.get("foreground"),
                "title": msg.get("title"),
                "proc": msg.get("proc"),
                "running": msg.get("running"),
            })
            await engine.broadcast_stations()

        else:
            await reply("error", code="unknown_type", message=f"Unknown message type: {kind!r}")

    except EngineError as exc:
        result_type = {"login": "login_result", "register": "register_result", "logout": "logout_result",
                       "order": "order_result"}.get(kind, "error")
        await reply(result_type, ok=False, error=exc.code, message=exc.message)
