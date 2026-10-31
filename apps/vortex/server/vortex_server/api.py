"""REST API used by the admin panel. All routes live under /api."""
from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .auth import TokenStore
from .engine import Engine, EngineError
from .models import (
    EventCreate, EventUpdate, GroupCreate, GroupUpdate, MemberCreate, MemberUpdate, PackageCreate, PackageUpdate,
    ProductCreate, ProductImage, ProductUpdate, SessionStart, SettingsUpdate, StaffLogin, StaffPasswordChange,
    StaffPinChange, StationCommand, StationCreate, StationUpdate, TopUp,
)

router = APIRouter(prefix="/api")


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": code, "message": message})


def get_engine(request: Request) -> Engine:
    return request.app.state.engine


def get_tokens(request: Request) -> TokenStore:
    return request.app.state.tokens


def bearer_token(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.query_params.get("token")


def require_staff(request: Request) -> sqlite3.Row:
    staff_id = get_tokens(request).resolve(bearer_token(request))
    if staff_id is None:
        raise api_error(401, "unauthorized", "Log in first.")
    row = get_engine(request).staff_row(staff_id)
    if row is None:
        raise api_error(401, "unauthorized", "Log in first.")
    return row


# ---------------------------------------------------------------- auth
@router.post("/auth/login")
def auth_login(body: StaffLogin, request: Request):
    engine, tokens = get_engine(request), get_tokens(request)
    row = engine.staff_login(body.username, body.password)
    if row is None:
        raise api_error(401, "bad_credentials", "Wrong username or password.")
    engine.audit(row["id"], "staff.login")
    return {"token": tokens.issue(row["id"]), "staff": engine.staff_view(row)}


@router.post("/auth/logout")
def auth_logout(request: Request, staff=Depends(require_staff)):
    get_tokens(request).revoke(bearer_token(request))
    return {"ok": True}


@router.get("/me")
def me(request: Request, staff=Depends(require_staff)):
    return {"staff": Engine.staff_view(staff), "settings": get_engine(request).settings_view()}


@router.post("/staff/password")
def staff_password(body: StaffPasswordChange, request: Request, staff=Depends(require_staff)):
    get_engine(request).staff_change_password(staff["id"], body.current_password, body.new_password)
    return {"ok": True}


@router.post("/staff/pin")
def staff_pin(body: StaffPinChange, request: Request, staff=Depends(require_staff)):
    get_engine(request).staff_set_pin(staff["id"], body.password, body.pin)
    return {"ok": True}


# ---------------------------------------------------------------- dashboard
@router.get("/dashboard")
def dashboard(request: Request, staff=Depends(require_staff)):
    return get_engine(request).dashboard()


@router.get("/audit")
def audit(request: Request, limit: int = Query(50, ge=1, le=500), staff=Depends(require_staff)):
    """Recent staff/kiosk activity (was GET /events before the events table existed)."""
    return {"events": get_engine(request).recent_events(limit)}


# ---------------------------------------------------------------- stations
@router.get("/stations")
def stations(request: Request, staff=Depends(require_staff)):
    return {"stations": get_engine(request).stations_view()}


@router.post("/stations", status_code=201)
def station_create(body: StationCreate, request: Request, staff=Depends(require_staff)):
    engine = get_engine(request)
    view = engine.create_station(body.name, body.group_id)
    engine.audit(staff["id"], "station.create", body.name)
    return view


@router.patch("/stations/{station_id}")
def station_update(station_id: int, body: StationUpdate, request: Request, staff=Depends(require_staff)):
    engine = get_engine(request)
    view = engine.update_station(station_id, **body.model_dump())
    engine.audit(staff["id"], "station.update", str(station_id))
    return view


@router.delete("/stations/{station_id}")
def station_delete(station_id: int, request: Request, staff=Depends(require_staff)):
    engine = get_engine(request)
    engine.delete_station(station_id)
    engine.audit(staff["id"], "station.delete", str(station_id))
    return {"ok": True}


@router.post("/stations/{station_id}/reset-key")
def station_reset_key(station_id: int, request: Request, staff=Depends(require_staff)):
    engine = get_engine(request)
    key = engine.reset_station_key(station_id)
    engine.audit(staff["id"], "station.reset_key", str(station_id))
    return {"key": key}


@router.post("/stations/{station_id}/command")
async def station_command(station_id: int, body: StationCommand, request: Request, staff=Depends(require_staff)):
    return await get_engine(request).station_command(
        station_id, body.name, staff_id=staff["id"], title=body.title, body=body.body, level=body.level
    )


@router.post("/stations/{station_id}/session", status_code=201)
async def station_session_start(station_id: int, body: SessionStart, request: Request, staff=Depends(require_staff)):
    engine = get_engine(request)
    if body.member_id is not None:
        return await engine.start_session(station_id, member_id=body.member_id, started_by="staff", staff_id=staff["id"])
    return await engine.start_session(
        station_id,
        guest_seconds=(body.guest_minutes or 0) * 60,
        package_id=body.package_id,
        amount=body.amount,
        started_by="staff",
        staff_id=staff["id"],
    )


@router.delete("/stations/{station_id}/session")
async def station_session_end(station_id: int, request: Request, staff=Depends(require_staff)):
    return await get_engine(request).end_station_session(station_id, "admin", staff_id=staff["id"])


@router.post("/stations/{station_id}/session/topup")
async def station_session_topup(station_id: int, body: TopUp, request: Request, staff=Depends(require_staff)):
    engine = get_engine(request)
    sess = engine.active_session_row(station_id)
    if sess is None:
        raise api_error(404, "no_session", "No running session on this station.")
    return await engine.topup_session(sess["id"], package_id=body.package_id, seconds=body.seconds,
                                      amount=body.amount, staff_id=staff["id"], note=body.note)


# ---------------------------------------------------------------- members
@router.get("/members")
def members(request: Request, q: str = "", limit: int = Query(200, ge=1, le=1000), staff=Depends(require_staff)):
    return {"members": get_engine(request).list_members(q, limit)}


@router.post("/members", status_code=201)
def member_create(body: MemberCreate, request: Request, staff=Depends(require_staff)):
    engine = get_engine(request)
    view = engine.create_member(body.email, body.password, body.username, body.tier)
    engine.audit(staff["id"], "member.create", view["username"])
    return view


@router.get("/members/{member_id}")
def member_get(member_id: int, request: Request, staff=Depends(require_staff)):
    engine = get_engine(request)
    row = engine.member_row(member_id)
    if row is None:
        raise api_error(404, "not_found", "Member not found.")
    return engine.member_view(row)


@router.patch("/members/{member_id}")
def member_update(member_id: int, body: MemberUpdate, request: Request, staff=Depends(require_staff)):
    engine = get_engine(request)
    view = engine.update_member(member_id, **body.model_dump())
    engine.audit(staff["id"], "member.update", view["username"])
    return view


@router.post("/members/{member_id}/topup")
async def member_topup(member_id: int, body: TopUp, request: Request, staff=Depends(require_staff)):
    return await get_engine(request).topup_member(
        member_id, package_id=body.package_id, seconds=body.seconds, amount=body.amount,
        staff_id=staff["id"], note=body.note,
    )


@router.get("/members/{member_id}/transactions")
def member_transactions(member_id: int, request: Request, staff=Depends(require_staff)):
    return {"transactions": get_engine(request).member_transactions(member_id)}


@router.get("/members/{member_id}/sessions")
def member_sessions(member_id: int, request: Request, staff=Depends(require_staff)):
    return {"sessions": get_engine(request).member_sessions(member_id)}


# ---------------------------------------------------------------- pricing
@router.get("/groups")
def groups(request: Request, staff=Depends(require_staff)):
    return {"groups": get_engine(request).groups()}


@router.post("/groups", status_code=201)
def group_create(body: GroupCreate, request: Request, staff=Depends(require_staff)):
    return get_engine(request).create_group(body.name, body.rate_per_hour)


@router.patch("/groups/{group_id}")
def group_update(group_id: int, body: GroupUpdate, request: Request, staff=Depends(require_staff)):
    return get_engine(request).update_group(group_id, **body.model_dump())


@router.delete("/groups/{group_id}")
def group_delete(group_id: int, request: Request, staff=Depends(require_staff)):
    get_engine(request).delete_group(group_id)
    return {"ok": True}


@router.get("/packages")
def packages(request: Request, staff=Depends(require_staff)):
    return {"packages": get_engine(request).packages()}


@router.post("/packages", status_code=201)
def package_create(body: PackageCreate, request: Request, staff=Depends(require_staff)):
    return get_engine(request).create_package(body.name, body.seconds, body.price, body.group_id, body.sort)


@router.patch("/packages/{package_id}")
def package_update(package_id: int, body: PackageUpdate, request: Request, staff=Depends(require_staff)):
    return get_engine(request).update_package(package_id, **body.model_dump())


@router.delete("/packages/{package_id}")
def package_delete(package_id: int, request: Request, staff=Depends(require_staff)):
    get_engine(request).delete_package(package_id)
    return {"ok": True}


@router.get("/price")
def price(request: Request, seconds: int = Query(..., ge=0), group_id: Optional[int] = None, staff=Depends(require_staff)):
    return {"seconds": seconds, "amount": get_engine(request).price_for_seconds(seconds, group_id)}


# ---------------------------------------------------------------- shop
@router.get("/products")
def products(request: Request, staff=Depends(require_staff)):
    return {"products": get_engine(request).products()}


@router.post("/products", status_code=201)
async def product_create(body: ProductCreate, request: Request, staff=Depends(require_staff)):
    return await get_engine(request).create_product(
        body.name, body.category, body.price, body.best, body.enabled, body.sort, staff_id=staff["id"]
    )


@router.patch("/products/{product_id}")
async def product_update(product_id: int, body: ProductUpdate, request: Request, staff=Depends(require_staff)):
    return await get_engine(request).update_product(product_id, staff_id=staff["id"], **body.model_dump())


@router.delete("/products/{product_id}")
async def product_delete(product_id: int, request: Request, staff=Depends(require_staff)):
    await get_engine(request).delete_product(product_id, staff_id=staff["id"])
    return {"ok": True}


@router.post("/products/{product_id}/image")
async def product_image_set(product_id: int, body: ProductImage, request: Request, staff=Depends(require_staff)):
    return await get_engine(request).set_product_image(product_id, body.filename, body.data, staff_id=staff["id"])


@router.delete("/products/{product_id}/image")
async def product_image_clear(product_id: int, request: Request, staff=Depends(require_staff)):
    return await get_engine(request).clear_product_image(product_id, staff_id=staff["id"])


@router.get("/orders")
def orders(request: Request, status: str = "pending", limit: int = Query(200, ge=1, le=1000), staff=Depends(require_staff)):
    return {"orders": get_engine(request).list_orders(status, limit)}


@router.post("/orders/{order_id}/done")
async def order_done(order_id: int, request: Request, staff=Depends(require_staff)):
    return await get_engine(request).set_order_status(order_id, "done", staff_id=staff["id"])


@router.post("/orders/{order_id}/cancel")
async def order_cancel(order_id: int, request: Request, staff=Depends(require_staff)):
    return await get_engine(request).set_order_status(order_id, "cancelled", staff_id=staff["id"])


# ---------------------------------------------------------------- events (client Events page / Home banner)
@router.get("/events")
def events(request: Request, staff=Depends(require_staff)):
    return {"events": get_engine(request).events()}


@router.post("/events", status_code=201)
async def event_create(body: EventCreate, request: Request, staff=Depends(require_staff)):
    return await get_engine(request).create_event(staff_id=staff["id"], **body.model_dump())


@router.post("/events/disable-all")
async def events_disable_all(request: Request, staff=Depends(require_staff)):
    return {"events": await get_engine(request).set_all_events_enabled(False, staff_id=staff["id"])}


@router.post("/events/enable-all")
async def events_enable_all(request: Request, staff=Depends(require_staff)):
    return {"events": await get_engine(request).set_all_events_enabled(True, staff_id=staff["id"])}


@router.patch("/events/{event_id}")
async def event_update(event_id: int, body: EventUpdate, request: Request, staff=Depends(require_staff)):
    return await get_engine(request).update_event(event_id, staff_id=staff["id"], **body.model_dump())


@router.delete("/events/{event_id}")
async def event_delete(event_id: int, request: Request, staff=Depends(require_staff)):
    await get_engine(request).delete_event(event_id, staff_id=staff["id"])
    return {"ok": True}


# ---------------------------------------------------------------- history
@router.get("/sessions")
def sessions(request: Request, active: bool = False, limit: int = Query(100, ge=1, le=1000), staff=Depends(require_staff)):
    return {"sessions": get_engine(request).list_sessions(active, limit)}


@router.get("/transactions")
def transactions(request: Request, limit: int = Query(100, ge=1, le=1000), since: Optional[str] = None,
                 today: bool = False, staff=Depends(require_staff)):
    engine = get_engine(request)
    if today:
        since = engine.local_day_start_iso()
    return {"transactions": engine.list_transactions(limit, since)}


# ---------------------------------------------------------------- settings
@router.get("/settings")
def settings_get(request: Request, staff=Depends(require_staff)):
    return get_engine(request).settings_view()


@router.put("/settings")
def settings_put(body: SettingsUpdate, request: Request, staff=Depends(require_staff)):
    return get_engine(request).update_settings(staff["id"], **body.model_dump())
