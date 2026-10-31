"""FastAPI application factory: REST + station/admin WebSockets + admin panel."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import router as api_router
from .auth import TokenStore
from .config import ADMIN_DIR, Settings, load_settings
from .db import Database
from .engine import Engine, EngineError
from .protocol import handle_station_message
from .ws import Hub

log = logging.getLogger("vortex.server")


def _disks(data_dir: Path) -> list[dict]:
    """Fixed hard disks with total/used/free (GB). Windows: every ready local drive letter;
    elsewhere: the root filesystem. `data` marks the drive holding the Vortex database."""
    roots: list[Path] = []
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        mask = kernel32.GetLogicalDrives()
        for i in range(26):
            if mask & (1 << i):
                root = f"{chr(65 + i)}:\\"
                if kernel32.GetDriveTypeW(root) == 3:          # DRIVE_FIXED (no USB sticks, no DVD)
                    roots.append(Path(root))
    else:  # pragma: no cover
        roots.append(Path("/"))
    data_root = Path(data_dir.resolve().anchor) if data_dir.exists() else None
    out = []
    for root in roots:
        try:
            u = shutil.disk_usage(root)
        except OSError:  # pragma: no cover - drive not ready
            continue
        label = ""
        if os.name == "nt":
            buf = ctypes.create_unicode_buffer(261)
            if ctypes.windll.kernel32.GetVolumeInformationW(str(root), buf, 261, None, None, None, None, 0):
                label = buf.value
        total, free = u.total, u.free
        out.append({
            "drive": str(root).rstrip("\\/") or str(root), "label": label,
            "total_gb": round(total / 1e9, 1), "used_gb": round((total - free) / 1e9, 1), "free_gb": round(free / 1e9, 1),
            "used_pct": round((total - free) * 100 / total, 1) if total else 0.0,
            "low": free < 5e9 or (total and free / total < 0.05),
            "data": data_root is not None and Path(str(root)).anchor.lower() == str(data_root).lower(),
        })
    return out


def _lan_addresses() -> list[str]:
    """IPv4 addresses of this PC (minus loopback), for the status page."""
    addrs: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                addrs.add(ip)
    except socket.gaierror:
        pass
    return sorted(addrs)


async def _tick_loop(engine: Engine, interval: float) -> None:
    while True:
        try:
            await engine.tick()
        except Exception:  # never let the loop die
            log.exception("tick failed")
        await asyncio.sleep(interval)


def create_app(settings: Optional[Settings] = None, db: Optional[Database] = None) -> FastAPI:
    settings = settings or load_settings()
    db = db or Database(settings.db_path)
    db.init_schema()
    media_dir = Path(settings.media_dir)
    (media_dir / "products").mkdir(parents=True, exist_ok=True)   # before seeding: seed pictures land here
    hub = Hub()
    engine = Engine(db, settings, hub)
    seeded = engine.seed_defaults()
    if seeded:
        log.warning("first run: seeded defaults %s", seeded)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(_tick_loop(engine, settings.tick_seconds))
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="Vortex Server", version=__version__, lifespan=lifespan, docs_url="/api/docs", redoc_url=None)
    app.state.settings = settings
    app.state.db = db
    app.state.hub = hub
    app.state.engine = engine
    app.state.tokens = TokenStore(settings.token_ttl_hours * 3600)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],           # LAN tool; the kiosk page may be served from file://
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- uniform error bodies: {"error": code, "message": text}
    @app.exception_handler(EngineError)
    async def _engine_error(request: Request, exc: EngineError):
        return JSONResponse({"error": exc.code, "message": exc.message}, status_code=exc.status)

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            body = detail
        else:
            body = {"error": "http_error", "message": str(detail)}
        return JSONResponse(body, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    app.include_router(api_router)

    @app.get("/health")
    def health():
        return {"ok": True, "version": __version__, "server_time": engine.now_iso()}

    started_at = time.time()

    @app.get("/api/status")
    def status():
        """Public, non-sensitive self-check for the status page (/status): is everything OK?
        Each check is {"name", "ok", "detail"}; "ok" at the top is True only when all pass."""
        checks: list[dict] = []

        def add(name: str, ok: bool, detail: str) -> None:
            checks.append({"name": name, "ok": bool(ok), "detail": detail})

        # database
        try:
            db.scalar("SELECT COUNT(*) FROM staff")
            size = Path(settings.db_path).stat().st_size if settings.db_path != ":memory:" else 0
            add("Database", True, f"{settings.db_path}  ({size / 1e6:.1f} MB)")
        except Exception as exc:  # pragma: no cover - only on a broken install
            add("Database", False, f"cannot read the database: {exc}")
        # media folder
        try:
            products = list((media_dir / "products").glob("*"))
            add("Pictures folder", (media_dir / "products").is_dir(), f"{media_dir}  ({len(products)} files)")
        except Exception as exc:  # pragma: no cover
            add("Pictures folder", False, str(exc))
        # every hard disk on this PC (the data drive is flagged); low = under 5 GB or under 5 % free
        disks = _disks(Path(settings.db_path).parent if settings.db_path != ":memory:" else Path.cwd())
        low = [d for d in disks if d["low"]]
        if disks:
            add("Disk space", not low,
                ", ".join(f"{d['drive']} {d['free_gb']:.0f} GB free of {d['total_gb']:.0f}" for d in disks)
                if not low else "LOW: " + ", ".join(f"{d['drive']} {d['free_gb']:.1f} GB free" for d in low))
        else:  # pragma: no cover
            add("Disk space", False, "no disks found")
        # session engine loop alive? (tick stamps _last_tick every run)
        last_tick = getattr(engine, "_last_tick", None)
        age = (time.monotonic() - last_tick) if last_tick else None
        add("Session engine", age is not None and age < max(5.0, settings.tick_seconds * 5),
            "running" if age is not None and age < 5 else ("not started yet" if age is None else f"stalled {age:.0f}s"))
        # stations
        stations = engine.stations_view()
        online = [s for s in stations if s["online"]]
        add("Stations", True, f"{len(online)} of {len(stations)} online, {sum(1 for s in stations if s['status'] == 'in_session')} in session")
        add("Admin panel", ADMIN_DIR.exists(), "served at /admin/")

        return {
            "ok": all(c["ok"] for c in checks),
            "checks": checks,
            "version": __version__,
            "cafe_name": settings.cafe_name,
            "hostname": socket.gethostname(),
            "addresses": _lan_addresses(),
            "port": settings.port,
            "server_time": engine.now_iso(),
            "local_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": time.strftime("%Z"),
            "uptime_seconds": int(time.time() - started_at),
            "stations": [{"name": s["name"], "online": s["online"], "status": s["status"]} for s in stations],
            "disks": disks,
        }

    @app.get("/status")
    def status_page():
        return RedirectResponse("/admin/status.html")

    # ------------------------------------------------------------ station socket
    @app.websocket("/ws/station")
    async def ws_station(ws: WebSocket):
        await ws.accept()
        station_id: Optional[int] = None
        try:
            try:
                hello = await asyncio.wait_for(ws.receive_json(), timeout=20)
            except asyncio.TimeoutError:
                await ws.close(code=4000)
                return
            if not isinstance(hello, dict) or hello.get("type") != "hello":
                await ws.send_json({"type": "error", "code": "expected_hello", "message": "First message must be 'hello'."})
                await ws.close(code=4000)
                return
            client_ip = ws.client.host if ws.client else ""
            row, issued = engine.station_hello(
                hello.get("station_name") or "", hello.get("station_key") or "",
                hello.get("hostname") or "", client_ip,
            )
            station_id = int(row["id"])
            await hub.attach_station(station_id, ws)
            active = engine.active_session_row(station_id)
            welcome = {
                "type": "welcome",
                "station": engine.station_view(row, active, resolve_session=False),
                "session": engine.session_view(active) if active else None,
                "server_time": engine.now_iso(),
                "config": {
                    "cafe_name": settings.cafe_name,
                    "currency": settings.currency,
                    "heartbeat_seconds": 10,
                    "warn_thresholds": list(settings.warn_thresholds),
                },
                "shop": engine.products(include_disabled=False),
                "events": engine.events(include_disabled=False),
                "media_base": "/media",         # informational: views already carry image_url
                "version": __version__,
            }
            if issued:
                welcome["station_key"] = issued
            await ws.send_json(welcome)
            await engine.station_online(station_id)
            log.info("station %s connected from %s", row["name"], client_ip)

            while True:
                try:
                    msg = await ws.receive_json()
                except ValueError:
                    await ws.send_json({"type": "error", "code": "bad_json", "message": "Message was not valid JSON."})
                    continue
                if not isinstance(msg, dict):
                    continue
                await handle_station_message(engine, station_id, ws.send_json, msg)

        except WebSocketDisconnect:
            pass
        except EngineError as exc:
            with contextlib.suppress(Exception):
                await ws.send_json({"type": "error", "code": exc.code, "message": exc.message})
                await ws.close(code=4003)
        except Exception:
            log.exception("station socket crashed")
        finally:
            if station_id is not None:
                hub.detach_station(station_id, ws)
                with contextlib.suppress(Exception):
                    await engine.station_offline(station_id)
                log.info("station %s disconnected", station_id)

    # ------------------------------------------------------------ admin socket
    @app.websocket("/ws/admin")
    async def ws_admin(ws: WebSocket):
        token = ws.query_params.get("token")
        staff_id = app.state.tokens.resolve(token)
        if staff_id is None:
            await ws.close(code=4003)
            return
        await ws.accept()
        hub.attach_admin(ws)
        try:
            await ws.send_json({"type": "stations", "stations": engine.stations_view(), "server_time": engine.now_iso()})
            await ws.send_json({"type": "orders", "orders": engine.pending_orders()})
            while True:
                msg = await ws.receive_json()
                if isinstance(msg, dict) and msg.get("type") == "ping":
                    await ws.send_json({"type": "pong", "server_time": engine.now_iso()})
        except WebSocketDisconnect:
            pass
        except Exception:
            log.exception("admin socket crashed")
        finally:
            hub.detach_admin(ws)

    # ------------------------------------------------------------ static pages
    # The kiosk page is served too, so the customer UI can be demoed in any browser
    # (it then speaks the station protocol directly; launching is simulated).
    kiosk_dir = ADMIN_DIR.parent.parent / "client" / "ui"
    if kiosk_dir.exists():
        app.mount("/kiosk", StaticFiles(directory=str(kiosk_dir), html=True), name="kiosk")

    # product pictures (uploads + seed copies) live outside the bundle, next to the database
    app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

    if ADMIN_DIR.exists():
        app.mount("/admin", StaticFiles(directory=str(ADMIN_DIR), html=True), name="admin")

        @app.api_route("/", methods=["GET", "HEAD"])
        def root():
            return RedirectResponse("/admin/")

    return app
