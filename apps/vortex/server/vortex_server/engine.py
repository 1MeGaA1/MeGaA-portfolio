"""The session engine: the ONE place that decides about time and money.

Time model = prepaid wallet.
    member.time_balance_seconds  is what the customer owns.
    A running session does not touch the wallet; remaining time is
        remaining = budget - elapsed
    where budget is the wallet (member session) or guest_seconds (guest).
    When the session ends, the used seconds are deducted once.
    A top-up during a session just grows the budget.
"""
from __future__ import annotations

import base64
import logging
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .auth import hash_password, new_station_key, verify_password
from .config import SEED_MEDIA_DIR, Settings
from .db import Database
from .ws import Hub

log = logging.getLogger("vortex.engine")


# --------------------------------------------------------------------------- time helpers
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(text: str) -> datetime:
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class EngineError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


SESSION_ENDED_MESSAGES = {
    "expired": "Your time is up. Top up at the counter to continue.",
    "logout": "You logged out. See you next time.",
    "admin": "Your session was ended by staff.",
    "station_lost": "Station disconnected.",
}

_STATION_SQL = (
    "SELECT s.*, g.name AS group_name, g.rate_per_hour AS rate_per_hour "
    "FROM stations s LEFT JOIN station_groups g ON g.id = s.group_id"
)

_ORDER_SQL = (
    "SELECT o.*, st.name AS station_name, m.username AS member_username "
    "FROM orders o JOIN stations st ON st.id = o.station_id LEFT JOIN members m ON m.id = o.member_id"
)

# --------------------------------------------------------------------------- shop & events
PRODUCT_CATEGORIES = ("drinks", "snacks", "meals")
EVENT_KINDS = ("event", "offer")
EVENT_STATUSES = ("live", "upcoming")
EVENT_CATS = ("live", "upcoming", "weekly", "weekend", "tournament", "offer")
ORDER_STATUSES = ("pending", "done", "cancelled")
MAX_ORDER_QTY = 10
MAX_IMAGE_BYTES = 4 * 1024 * 1024
IMAGE_EXTENSIONS = {"png": "png", "jpg": "jpg", "jpeg": "jpg", "webp": "webp"}

# (name, category, price in minor units, image slug, best) — seeded once, in this order
SEED_PRODUCTS = [
    ("Coca-Cola", "drinks", 2500, "cocacola", True),
    ("Pepsi", "drinks", 2500, "pepsi", False),
    ("Sprite", "drinks", 2500, "sprite", False),
    ("Water", "drinks", 1000, "water", False),
    ("Red Bull", "drinks", 6000, "redbull", True),
    ("Monster Energy", "drinks", 6000, "monster", False),
    ("Orange Juice", "drinks", 3500, "orangejuice", False),
    ("Iced Tea", "drinks", 3000, "icedtea", False),
    ("Lemonade", "drinks", 3000, "lemonade", False),
    ("Coffee", "drinks", 4000, "coffee", False),
    ("Doritos", "snacks", 3000, "doritos", True),
    ("Lay's", "snacks", 2000, "lays", False),
    ("Oreo", "snacks", 2000, "oreo", False),
    ("Snickers", "snacks", 2500, "snickers", True),
    ("M&M's", "snacks", 3000, "mms", False),
    ("Popcorn", "snacks", 3000, "popcorn", False),
    ("Mixed Nuts", "snacks", 4000, "nuts", False),
    ("Protein Bar", "snacks", 5000, "proteinbar", False),
    ("Pizza Slice", "meals", 6000, "pizza", True),
    ("Burger", "meals", 9000, "burger", False),
    ("Hot Dog", "meals", 5500, "hotdog", False),
    ("Fries", "meals", 4000, "fries", False),
    ("Sandwich", "meals", 6000, "sandwich", False),
    ("Ramen Bowl", "meals", 10000, "ramen", False),
]

SEED_EVENTS = [
    {"title": "VORTEX CUP 2026 · WEEK 3", "kind": "event", "game": "VALORANT · 5v5",
     "tag": "FLAGSHIP TOURNAMENT · REGISTRATION OPEN", "players": "256 players", "when": "Starts in 2h 15m",
     "prize": "EGP 5,000", "status": "upcoming", "cats": ["upcoming", "tournament"], "show_home": True},
    {"title": "Rocket League 3v3", "game": "Rocket League", "prize": "EGP 800", "when": "LIVE NOW",
     "status": "live", "cats": ["live"]},
    {"title": "CS2 1v1 Ladder", "game": "Counter-Strike 2", "prize": "EGP 500/week", "when": "ONGOING",
     "status": "live", "cats": ["live", "weekly"]},
    {"title": "Apex Duos Showdown", "game": "Apex Legends", "prize": "EGP 1,500", "when": "TOMORROW 8PM",
     "status": "upcoming", "cats": ["upcoming", "tournament"]},
    {"title": "FIFA Friday Night", "game": "FIFA 26", "prize": "EGP 300", "when": "FRI 9PM",
     "status": "upcoming", "cats": ["upcoming", "weekly"]},
    {"title": "Fortnite Solo Cup", "game": "Fortnite", "prize": "EGP 2,000", "when": "SAT 6PM",
     "status": "upcoming", "cats": ["upcoming", "tournament"]},
    {"title": "League Clash Weekend", "game": "League of Legends", "prize": "EGP 1,000", "when": "SUN 4PM",
     "status": "upcoming", "cats": ["upcoming", "weekend", "tournament"]},
    {"title": "HAPPY HOUR · 2 HOURS FOR EGP 100", "kind": "offer", "game": "", "tag": "SPECIAL OFFER",
     "when": "TODAY 2PM–6PM", "prize": "EGP 100", "status": "upcoming", "cats": ["offer"]},
]


def sniff_image_ext(data: bytes) -> Optional[str]:
    """Return 'png' / 'jpg' / 'webp' from the magic bytes, or None when it is not an image we accept."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


class Engine:
    def __init__(self, db: Database, settings: Settings, hub: Hub, clock: Callable[[], datetime] = utcnow):
        self.db = db
        self.settings = settings
        self.hub = hub
        self.clock = clock
        self._warned: dict[int, Optional[int]] = {}    # session_id -> last threshold warned
        self._resync_at: dict[int, float] = {}         # session_id -> monotonic time of last push
        self._last_admin_push = 0.0
        self._activity: dict[int, dict] = {}           # station_id -> live foreground/running report

    # ------------------------------------------------------------------ basics
    def now(self) -> datetime:
        return self.clock()

    def now_iso(self) -> str:
        return iso(self.now())

    def audit(self, staff_id: Optional[int], action: str, detail: str = "") -> None:
        self.db.insert(
            "INSERT INTO audit_log (at, staff_id, action, detail) VALUES (?,?,?,?)",
            (self.now_iso(), staff_id, action, detail),
        )

    def recent_events(self, limit: int = 50) -> list[dict]:
        rows = self.db.query(
            "SELECT a.*, s.username AS staff FROM audit_log a LEFT JOIN staff s ON s.id = a.staff_id "
            "ORDER BY a.id DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ seeding
    def seed_defaults(self) -> dict[str, Any]:
        """First-run data so the cafe can start clicking immediately."""
        created: dict[str, Any] = {}
        if not self.db.scalar("SELECT COUNT(*) FROM staff"):
            self.db.insert(
                "INSERT INTO staff (username, password_hash, pin_hash, role, created_at) VALUES (?,?,?,?,?)",
                ("admin", hash_password("admin"), hash_password("1234"), "admin", self.now_iso()),
            )
            created["staff"] = "admin / admin  (exit PIN 1234)"
        if not self.db.scalar("SELECT COUNT(*) FROM station_groups"):
            self.db.insert("INSERT INTO station_groups (name, rate_per_hour, sort) VALUES (?,?,?)", ("Regular", 2000, 0))
            self.db.insert("INSERT INTO station_groups (name, rate_per_hour, sort) VALUES (?,?,?)", ("VIP", 3000, 1))
            created["groups"] = ["Regular", "VIP"]
        if not self.db.scalar("SELECT COUNT(*) FROM packages"):
            for sort, (name, secs, price) in enumerate(
                [("30 min", 1800, 1000), ("1 hour", 3600, 2000), ("2 hours", 7200, 3800), ("5 hours", 18000, 9000)]
            ):
                self.db.insert("INSERT INTO packages (name, seconds, price, sort) VALUES (?,?,?,?)", (name, secs, price, sort))
            created["packages"] = 4
        # Seed the demo menu / events ONCE per database (a settings flag, not "table is empty"),
        # so staff deleting every product or event does not bring the demo set back on restart.
        if self.db.get_setting("seeded_products") is None:
            if not self.db.scalar("SELECT COUNT(*) FROM products"):
                self._copy_seed_media()
                for sort, (name, category, price, slug, best) in enumerate(SEED_PRODUCTS):
                    self.db.insert(
                        "INSERT INTO products (name, category, price, image, best, enabled, sort, created_at) "
                        "VALUES (?,?,?,?,?,1,?,?)",
                        (name, category, price, f"products/{slug}.png", 1 if best else 0, sort, self.now_iso()),
                    )
                created["products"] = len(SEED_PRODUCTS)
            self.db.set_setting("seeded_products", "1")
        if self.db.get_setting("seeded_events") is None:
            if not self.db.scalar("SELECT COUNT(*) FROM events"):
                for sort, event in enumerate(SEED_EVENTS):
                    self._insert_event(dict(event, sort=sort))
                created["events"] = len(SEED_EVENTS)
            self.db.set_setting("seeded_events", "1")
        # persisted settings override the json defaults
        for key in ("cafe_name", "currency"):
            value = self.db.get_setting(key)
            if value is not None:
                setattr(self.settings, key, value)
        for key in ("auto_register_stations",):
            value = self.db.get_setting(key)
            if value is not None:
                setattr(self.settings, key, value == "1")
        value = self.db.get_setting("min_session_seconds")
        if value is not None:
            self.settings.min_session_seconds = int(value)
        return created

    # ------------------------------------------------------------------ staff
    def staff_row(self, staff_id: int) -> Optional[sqlite3.Row]:
        return self.db.one("SELECT * FROM staff WHERE id=?", (staff_id,))

    @staticmethod
    def staff_view(row: sqlite3.Row) -> dict:
        return {"id": row["id"], "username": row["username"], "role": row["role"], "has_pin": bool(row["pin_hash"])}

    def staff_login(self, username: str, password: str) -> Optional[sqlite3.Row]:
        row = self.db.one("SELECT * FROM staff WHERE username=?", (username.strip(),))
        if row and verify_password(password, row["password_hash"]):
            return row
        return None

    def staff_change_password(self, staff_id: int, current: str, new: str) -> None:
        row = self.staff_row(staff_id)
        if not row or not verify_password(current, row["password_hash"]):
            raise EngineError("bad_password", "Current password is wrong.", 403)
        self.db.execute("UPDATE staff SET password_hash=? WHERE id=?", (hash_password(new), staff_id))
        self.audit(staff_id, "staff.password")

    def staff_set_pin(self, staff_id: int, password: str, pin: str) -> None:
        row = self.staff_row(staff_id)
        if not row or not verify_password(password, row["password_hash"]):
            raise EngineError("bad_password", "Password is wrong.", 403)
        self.db.execute("UPDATE staff SET pin_hash=? WHERE id=?", (hash_password(pin), staff_id))
        self.audit(staff_id, "staff.pin")

    def verify_exit_pin(self, pin: str) -> Optional[sqlite3.Row]:
        """The kiosk admin-escape PIN. Any staff member's PIN works."""
        for row in self.db.query("SELECT * FROM staff WHERE pin_hash IS NOT NULL"):
            if verify_password(pin, row["pin_hash"]):
                return row
        return None

    # ------------------------------------------------------------------ groups & packages
    def groups(self) -> list[dict]:
        return [dict(r) for r in self.db.query("SELECT * FROM station_groups ORDER BY sort, name")]

    def group_row(self, group_id: Optional[int]) -> Optional[sqlite3.Row]:
        if group_id is None:
            return None
        return self.db.one("SELECT * FROM station_groups WHERE id=?", (group_id,))

    def create_group(self, name: str, rate_per_hour: int) -> dict:
        name = name.strip()
        if not name:
            raise EngineError("invalid", "Group name is required.")
        if self.db.one("SELECT 1 FROM station_groups WHERE name=?", (name,)):
            raise EngineError("exists", "A group with that name already exists.", 409)
        gid = self.db.insert("INSERT INTO station_groups (name, rate_per_hour) VALUES (?,?)", (name, rate_per_hour))
        return dict(self.group_row(gid))

    def update_group(self, group_id: int, **fields: Any) -> dict:
        row = self.group_row(group_id)
        if not row:
            raise EngineError("not_found", "Group not found.", 404)
        sets, params = [], []
        for key in ("name", "rate_per_hour", "sort"):
            if fields.get(key) is not None:
                sets.append(f"{key}=?")
                params.append(fields[key])
        if sets:
            params.append(group_id)
            self.db.execute(f"UPDATE station_groups SET {', '.join(sets)} WHERE id=?", params)
        return dict(self.group_row(group_id))

    def delete_group(self, group_id: int) -> None:
        if not self.group_row(group_id):
            raise EngineError("not_found", "Group not found.", 404)
        self.db.execute("DELETE FROM station_groups WHERE id=?", (group_id,))

    def packages(self, include_disabled: bool = True) -> list[dict]:
        sql = "SELECT * FROM packages" + ("" if include_disabled else " WHERE enabled=1") + " ORDER BY sort, seconds"
        return [dict(r) for r in self.db.query(sql)]

    def package_row(self, package_id: Optional[int]) -> Optional[sqlite3.Row]:
        if package_id is None:
            return None
        return self.db.one("SELECT * FROM packages WHERE id=?", (package_id,))

    def create_package(self, name: str, seconds: int, price: int, group_id: Optional[int] = None, sort: int = 0) -> dict:
        if group_id is not None and not self.group_row(group_id):
            raise EngineError("not_found", "Group not found.", 404)
        pid = self.db.insert(
            "INSERT INTO packages (name, seconds, price, group_id, sort) VALUES (?,?,?,?,?)",
            (name.strip(), seconds, price, group_id, sort),
        )
        return dict(self.package_row(pid))

    def update_package(self, package_id: int, **fields: Any) -> dict:
        if not self.package_row(package_id):
            raise EngineError("not_found", "Package not found.", 404)
        sets, params = [], []
        for key in ("name", "seconds", "price", "group_id", "enabled", "sort"):
            if key in fields and fields[key] is not None:
                sets.append(f"{key}=?")
                params.append(int(fields[key]) if key == "enabled" else fields[key])
        if sets:
            params.append(package_id)
            self.db.execute(f"UPDATE packages SET {', '.join(sets)} WHERE id=?", params)
        return dict(self.package_row(package_id))

    def delete_package(self, package_id: int) -> None:
        if not self.package_row(package_id):
            raise EngineError("not_found", "Package not found.", 404)
        # keep history intact: transactions reference packages, so soft-delete
        self.db.execute("UPDATE packages SET enabled=0 WHERE id=?", (package_id,))

    def price_for_seconds(self, seconds: int, group_id: Optional[int]) -> int:
        """Custom time at the group's hourly rate (falls back to the first group)."""
        group = self.group_row(group_id)
        if group is None:
            group = self.db.one("SELECT * FROM station_groups ORDER BY sort, id LIMIT 1")
        rate = group["rate_per_hour"] if group else 0
        return int(round(seconds * rate / 3600.0))

    def _resolve_sale(self, package_id: Optional[int], seconds: Optional[int], amount: Optional[int],
                      group_id: Optional[int]) -> tuple[int, int, Optional[int]]:
        """Return (seconds, amount, package_id) for a sale request."""
        if package_id is not None:
            pkg = self.package_row(package_id)
            if not pkg or not pkg["enabled"]:
                raise EngineError("not_found", "Package not found.", 404)
            return int(pkg["seconds"]), int(pkg["price"] if amount is None else amount), int(pkg["id"])
        if seconds is None or seconds == 0:
            raise EngineError("invalid", "Choose a package or enter minutes.")
        amt = self.price_for_seconds(seconds, group_id) if amount is None else int(amount)
        return int(seconds), max(0, amt), None

    # ------------------------------------------------------------------ members
    def member_row(self, member_id: Optional[int]) -> Optional[sqlite3.Row]:
        if member_id is None:
            return None
        return self.db.one("SELECT * FROM members WHERE id=?", (member_id,))

    def member_view(self, row: sqlite3.Row) -> dict:
        active = self.member_active_session(row["id"])
        station = self.station_row(active["station_id"]) if active else None
        return {
            "id": row["id"],
            "email": row["email"],
            "username": row["username"],
            "tier": row["tier"],
            "time_balance_seconds": row["time_balance_seconds"],
            "points": row["points"],
            "enabled": bool(row["enabled"]),
            "created_at": row["created_at"],
            "last_login_at": row["last_login_at"],
            "active_station": station["name"] if station else None,
        }

    @staticmethod
    def member_public(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "email": row["email"],
            "username": row["username"],
            "tier": row["tier"],
            "points": row["points"],
        }

    def list_members(self, q: str = "", limit: int = 200) -> list[dict]:
        if q:
            like = f"%{q.strip()}%"
            rows = self.db.query(
                "SELECT * FROM members WHERE email LIKE ? OR username LIKE ? ORDER BY id DESC LIMIT ?",
                (like, like, limit),
            )
        else:
            rows = self.db.query("SELECT * FROM members ORDER BY id DESC LIMIT ?", (limit,))
        return [self.member_view(r) for r in rows]

    def create_member(self, email: str, password: str, username: Optional[str] = None, tier: str = "BRONZE") -> dict:
        email = (email or "").strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise EngineError("invalid_email", "Enter a valid email address.")
        if len(password or "") < 4:
            raise EngineError("weak_password", "Password must be at least 4 characters.")
        if self.db.one("SELECT 1 FROM members WHERE email=?", (email,)):
            raise EngineError("email_exists", "An account with that email already exists.", 409)
        base = (username or email.split("@")[0]).strip().lower()
        base = "".join(ch for ch in base if ch.isalnum() or ch in "._-") or "player"
        candidate, n = base, 1
        while self.db.one("SELECT 1 FROM members WHERE username=?", (candidate,)):
            if username:
                raise EngineError("username_exists", "That username is taken.", 409)
            n += 1
            candidate = f"{base}{n}"
        mid = self.db.insert(
            "INSERT INTO members (email, username, password_hash, tier, created_at) VALUES (?,?,?,?,?)",
            (email, candidate, hash_password(password), (tier or "BRONZE").upper(), self.now_iso()),
        )
        return self.member_view(self.member_row(mid))

    def update_member(self, member_id: int, **fields: Any) -> dict:
        row = self.member_row(member_id)
        if not row:
            raise EngineError("not_found", "Member not found.", 404)
        sets, params = [], []
        if fields.get("email"):
            email = fields["email"].strip().lower()
            other = self.db.one("SELECT id FROM members WHERE email=? AND id<>?", (email, member_id))
            if other:
                raise EngineError("email_exists", "Email already used by another member.", 409)
            sets.append("email=?"); params.append(email)
        if fields.get("username"):
            uname = fields["username"].strip()
            other = self.db.one("SELECT id FROM members WHERE username=? AND id<>?", (uname, member_id))
            if other:
                raise EngineError("username_exists", "Username already taken.", 409)
            sets.append("username=?"); params.append(uname)
        if fields.get("tier"):
            sets.append("tier=?"); params.append(fields["tier"].upper())
        if fields.get("enabled") is not None:
            sets.append("enabled=?"); params.append(1 if fields["enabled"] else 0)
        if fields.get("password"):
            sets.append("password_hash=?"); params.append(hash_password(fields["password"]))
        if fields.get("points") is not None:
            sets.append("points=?"); params.append(int(fields["points"]))
        if sets:
            params.append(member_id)
            self.db.execute(f"UPDATE members SET {', '.join(sets)} WHERE id=?", params)
        return self.member_view(self.member_row(member_id))

    def authenticate_member(self, login: str, password: str) -> Optional[sqlite3.Row]:
        login = (login or "").strip()
        row = self.db.one("SELECT * FROM members WHERE email=? OR username=?", (login, login))
        if row and row["enabled"] and verify_password(password, row["password_hash"]):
            return row
        return None

    def member_transactions(self, member_id: int, limit: int = 100) -> list[dict]:
        rows = self.db.query(
            "SELECT t.*, p.name AS package_name, s.username AS staff, st.name AS station "
            "FROM transactions t LEFT JOIN packages p ON p.id=t.package_id "
            "LEFT JOIN staff s ON s.id=t.staff_id LEFT JOIN stations st ON st.id=t.station_id "
            "WHERE t.member_id=? ORDER BY t.id DESC LIMIT ?",
            (member_id, limit),
        )
        return [dict(r) for r in rows]

    def member_sessions(self, member_id: int, limit: int = 50) -> list[dict]:
        rows = self.db.query("SELECT * FROM sessions WHERE member_id=? ORDER BY id DESC LIMIT ?", (member_id, limit))
        return [self.session_view(r) for r in rows]

    # ------------------------------------------------------------------ stations
    def station_row(self, station_id: int) -> Optional[sqlite3.Row]:
        return self.db.one(_STATION_SQL + " WHERE s.id=?", (station_id,))

    def station_view(self, row: sqlite3.Row, session: Optional[sqlite3.Row] = None, resolve_session: bool = True) -> dict:
        if session is None and resolve_session:
            session = self.active_session_row(row["id"])
        online = self.hub.is_station_online(row["id"])
        if not online:
            status = "offline"
        elif session is not None:
            status = "in_session"
        elif row["locked"]:
            status = "locked"
        else:
            status = "free"
        return {
            "id": row["id"],
            "name": row["name"],
            "group_id": row["group_id"],
            "group": row["group_name"],
            "rate_per_hour": row["rate_per_hour"],
            "hostname": row["hostname"],
            "ip": row["ip"],
            "last_seen": row["last_seen"],
            "online": online,
            "locked": bool(row["locked"]),
            "enabled": bool(row["enabled"]),
            "status": status,
            "session": self.session_view(session) if session is not None else None,
            "activity": self._activity.get(row["id"]) if online else None,
        }

    def stations_view(self) -> list[dict]:
        rows = self.db.query(_STATION_SQL + " ORDER BY s.name")
        active = {r["station_id"]: r for r in self.db.query("SELECT * FROM sessions WHERE ended_at IS NULL")}
        return [self.station_view(r, active.get(r["id"]), resolve_session=False) for r in rows]

    def create_station(self, name: str, group_id: Optional[int] = None) -> dict:
        name = name.strip()
        if not name:
            raise EngineError("invalid", "Station name is required.")
        if self.db.one("SELECT 1 FROM stations WHERE name=?", (name,)):
            raise EngineError("exists", "A station with that name already exists.", 409)
        if group_id is None:
            first = self.db.one("SELECT id FROM station_groups ORDER BY sort, id LIMIT 1")
            group_id = first["id"] if first else None
        key = new_station_key()
        sid = self.db.insert(
            "INSERT INTO stations (name, key, group_id, created_at) VALUES (?,?,?,?)",
            (name, key, group_id, self.now_iso()),
        )
        view = self.station_view(self.station_row(sid))
        view["key"] = key   # shown once, at creation time
        return view

    def update_station(self, station_id: int, **fields: Any) -> dict:
        if not self.station_row(station_id):
            raise EngineError("not_found", "Station not found.", 404)
        sets, params = [], []
        if fields.get("name"):
            name = fields["name"].strip()
            if self.db.one("SELECT 1 FROM stations WHERE name=? AND id<>?", (name, station_id)):
                raise EngineError("exists", "A station with that name already exists.", 409)
            sets.append("name=?"); params.append(name)
        if "group_id" in fields and fields["group_id"] is not None:
            if not self.group_row(fields["group_id"]):
                raise EngineError("not_found", "Group not found.", 404)
            sets.append("group_id=?"); params.append(fields["group_id"])
        for flag in ("enabled", "locked"):
            if fields.get(flag) is not None:
                sets.append(f"{flag}=?"); params.append(1 if fields[flag] else 0)
        if sets:
            params.append(station_id)
            self.db.execute(f"UPDATE stations SET {', '.join(sets)} WHERE id=?", params)
        return self.station_view(self.station_row(station_id))

    def reset_station_key(self, station_id: int) -> str:
        if not self.station_row(station_id):
            raise EngineError("not_found", "Station not found.", 404)
        key = new_station_key()
        self.db.execute("UPDATE stations SET key=? WHERE id=?", (key, station_id))
        return key

    def delete_station(self, station_id: int) -> None:
        if not self.station_row(station_id):
            raise EngineError("not_found", "Station not found.", 404)
        if self.active_session_row(station_id):
            raise EngineError("station_busy", "End the session on this station first.", 409)
        if self.db.one("SELECT 1 FROM sessions WHERE station_id=? LIMIT 1", (station_id,)):
            # keep history: disable instead of delete
            self.db.execute("UPDATE stations SET enabled=0 WHERE id=?", (station_id,))
        else:
            self.db.execute("DELETE FROM stations WHERE id=?", (station_id,))

    def station_hello(self, name: str, key: str, hostname: str = "", ip: str = "") -> tuple[sqlite3.Row, Optional[str]]:
        """Authenticate (or auto-register) a kiosk. Returns (row, key_issued)."""
        name = (name or hostname or "").strip()[:64]
        key = (key or "").strip()
        row = self.db.one(_STATION_SQL + " WHERE s.key=?", (key,)) if key else None
        issued: Optional[str] = None
        if row is None:
            if not name:
                raise EngineError("invalid", "Station name is required.", 400)
            by_name = self.db.one(_STATION_SQL + " WHERE s.name=?", (name,))
            if by_name is not None:
                raise EngineError("station_key_mismatch",
                                  f"Station '{name}' exists but the key does not match. Reset its key in the admin panel.", 403)
            if not self.settings.auto_register_stations:
                raise EngineError("unknown_station", f"Station '{name}' is not registered and auto-register is off.", 403)
            view = self.create_station(name)
            issued = view["key"]
            row = self.station_row(view["id"])
            self.audit(None, "station.auto_register", name)
        if not row["enabled"]:
            raise EngineError("station_disabled", "This station is disabled.", 403)
        self.db.execute(
            "UPDATE stations SET hostname=?, ip=?, last_seen=? WHERE id=?",
            (hostname[:64], ip[:64], self.now_iso(), row["id"]),
        )
        return self.station_row(row["id"]), issued

    def touch_station(self, station_id: int) -> None:
        self.db.execute("UPDATE stations SET last_seen=? WHERE id=?", (self.now_iso(), station_id))

    async def station_online(self, station_id: int) -> None:
        self.touch_station(station_id)
        await self.broadcast_stations()

    async def station_offline(self, station_id: int) -> None:
        self.touch_station(station_id)
        self._activity.pop(station_id, None)
        await self.broadcast_stations()

    def set_activity(self, station_id: int, data: dict) -> None:
        """Store a station's live 'what is it doing right now' report (foreground app + running)."""
        self._activity[station_id] = {
            "foreground": (str(data.get("foreground"))[:80] if data.get("foreground") else None),
            "title": str(data.get("title") or "")[:120],
            "proc": str(data.get("proc") or "")[:64],
            "running": [str(x)[:60] for x in (data.get("running") or [])][:12],
            "at": self.now_iso(),
        }

    async def station_command(self, station_id: int, name: str, staff_id: Optional[int] = None, **extra: Any) -> dict:
        row = self.station_row(station_id)
        if not row:
            raise EngineError("not_found", "Station not found.", 404)
        if name in ("lock", "unlock"):
            self.db.execute("UPDATE stations SET locked=? WHERE id=?", (1 if name == "lock" else 0, station_id))
        if name == "message":
            payload = {"type": "message", "title": extra.get("title") or "Message from staff",
                       "body": extra.get("body") or "", "level": extra.get("level") or "info"}
        else:
            payload = {"type": "command", "name": name}
        delivered = await self.hub.send_station(station_id, payload)
        self.audit(staff_id, f"station.{name}", row["name"])
        await self.broadcast_stations()
        if not delivered and name not in ("lock", "unlock"):
            raise EngineError("station_offline", "Station is offline; command not delivered.", 409)
        return {"delivered": delivered, "station": self.station_view(self.station_row(station_id))}

    # ------------------------------------------------------------------ sessions
    def active_session_row(self, station_id: int) -> Optional[sqlite3.Row]:
        return self.db.one("SELECT * FROM sessions WHERE station_id=? AND ended_at IS NULL", (station_id,))

    def member_active_session(self, member_id: int) -> Optional[sqlite3.Row]:
        return self.db.one("SELECT * FROM sessions WHERE member_id=? AND ended_at IS NULL", (member_id,))

    def session_row(self, session_id: int) -> Optional[sqlite3.Row]:
        return self.db.one("SELECT * FROM sessions WHERE id=?", (session_id,))

    def session_budget(self, sess: sqlite3.Row, member: Optional[sqlite3.Row] = None) -> int:
        if sess["kind"] == "member":
            member = member or self.member_row(sess["member_id"])
            return int(member["time_balance_seconds"]) if member else 0
        return int(sess["guest_seconds"])

    def session_view(self, sess: sqlite3.Row, member: Optional[sqlite3.Row] = None) -> dict:
        if member is None and sess["member_id"] is not None:
            member = self.member_row(sess["member_id"])
        station = self.station_row(sess["station_id"])
        now = self.now()
        started = parse_iso(sess["started_at"])
        end = parse_iso(sess["ended_at"]) if sess["ended_at"] else now
        elapsed = max(0, int((end - started).total_seconds()))
        if sess["ended_at"]:
            budget = int(sess["seconds_used"] or 0)
            remaining = 0
        else:
            budget = self.session_budget(sess, member)
            remaining = budget - elapsed
        return {
            "id": sess["id"],
            "kind": sess["kind"],
            "station": {"id": station["id"], "name": station["name"], "group": station["group_name"]} if station else None,
            "member": self.member_public(member) if member is not None else None,
            "started_at": sess["started_at"],
            "ended_at": sess["ended_at"],
            "end_reason": sess["end_reason"],
            "seconds_used": sess["seconds_used"],
            "budget_seconds": budget,
            "elapsed_seconds": elapsed,
            "remaining_seconds": max(0, remaining),
            "active": sess["ended_at"] is None,
            "server_time": iso(now),
        }

    def _prime_warnings(self, session_id: int, remaining: int) -> None:
        """Do not fire a warning immediately for a session that starts short;
        only fire the next threshold below the current remaining time."""
        higher = [t for t in self.settings.warn_thresholds if t >= remaining]
        self._warned[session_id] = min(higher) if higher else None

    async def start_session(self, station_id: int, *, member_id: Optional[int] = None,
                            guest_seconds: int = 0, package_id: Optional[int] = None,
                            amount: Optional[int] = None, started_by: str = "client",
                            staff_id: Optional[int] = None) -> dict:
        station = self.station_row(station_id)
        if not station or not station["enabled"]:
            raise EngineError("not_found", "Station not found.", 404)
        if self.active_session_row(station_id):
            raise EngineError("station_busy", "This station already has a running session.", 409)
        if station["locked"] and started_by == "client":
            raise EngineError("station_locked", "This station is locked by staff.", 403)

        member = None
        tx: Optional[tuple[int, int, Optional[int]]] = None
        if member_id is not None:
            member = self.member_row(member_id)
            if not member or not member["enabled"]:
                raise EngineError("not_found", "Member not found.", 404)
            other = self.member_active_session(member_id)
            if other:
                other_station = self.station_row(other["station_id"])
                raise EngineError("member_busy",
                                  f"This account is already logged in on {other_station['name'] if other_station else 'another station'}.", 409)
            budget = int(member["time_balance_seconds"])
            kind = "member"
        else:
            secs, amt, pkg_id = self._resolve_sale(package_id, guest_seconds or None, amount, station["group_id"])
            if secs <= 0:
                raise EngineError("invalid", "Guest time must be positive.")
            budget = secs
            tx = (secs, amt, pkg_id)
            kind = "guest"
        if budget < self.settings.min_session_seconds:
            raise EngineError("no_time", "No time left on this account. Top up at the counter.", 402)

        now = self.now_iso()
        with self.db.transaction():
            sid = self.db.insert(
                "INSERT INTO sessions (station_id, member_id, kind, started_at, guest_seconds, started_by) "
                "VALUES (?,?,?,?,?,?)",
                (station_id, member_id, kind, now, budget if kind == "guest" else 0, started_by),
            )
            if member is not None:
                self.db.execute("UPDATE members SET last_login_at=? WHERE id=?", (now, member_id))
            if tx is not None:
                self.db.insert(
                    "INSERT INTO transactions (kind, session_id, station_id, package_id, staff_id, seconds, amount, note, created_at) "
                    "VALUES ('guest_time',?,?,?,?,?,?,?,?)",
                    (sid, station_id, tx[2], staff_id, tx[0], tx[1], "guest session", now),
                )
        self._prime_warnings(sid, budget)
        self._resync_at[sid] = time.monotonic()
        self.audit(staff_id, "session.start", f"{station['name']} {kind} {member['username'] if member else ''}".strip())
        view = self.session_view(self.session_row(sid), member)
        await self.hub.send_station(station_id, {"type": "session_update", "session": view})
        await self.broadcast_stations()
        return view

    async def end_session(self, session_id: int, reason: str, staff_id: Optional[int] = None,
                          message: Optional[str] = None) -> dict:
        sess = self.session_row(session_id)
        if not sess:
            raise EngineError("not_found", "Session not found.", 404)
        if sess["ended_at"]:
            return self.session_view(sess)
        member = self.member_row(sess["member_id"]) if sess["member_id"] else None
        now = self.now()
        elapsed = max(0, int((now - parse_iso(sess["started_at"])).total_seconds()))
        budget = self.session_budget(sess, member)
        used = max(0, min(elapsed, budget))
        with self.db.transaction():
            self.db.execute(
                "UPDATE sessions SET ended_at=?, end_reason=?, seconds_used=? WHERE id=?",
                (iso(now), reason, used, session_id),
            )
            if member is not None:
                self.db.execute(
                    "UPDATE members SET time_balance_seconds = MAX(0, time_balance_seconds - ?) WHERE id=?",
                    (used, member["id"]),
                )
        self._warned.pop(session_id, None)
        self._resync_at.pop(session_id, None)
        self._activity.pop(sess["station_id"], None)
        station = self.station_row(sess["station_id"])
        self.audit(staff_id, f"session.end.{reason}", f"{station['name'] if station else sess['station_id']} used {used}s")
        view = self.session_view(self.session_row(session_id))
        await self.hub.send_station(sess["station_id"], {
            "type": "session_ended",
            "reason": reason,
            "message": message or SESSION_ENDED_MESSAGES.get(reason, "Session ended."),
            "session": view,
        })
        await self.broadcast_stations()
        return view

    async def end_station_session(self, station_id: int, reason: str = "admin", staff_id: Optional[int] = None) -> dict:
        sess = self.active_session_row(station_id)
        if not sess:
            raise EngineError("no_session", "No running session on this station.", 404)
        return await self.end_session(sess["id"], reason, staff_id=staff_id)

    async def topup_member(self, member_id: int, *, package_id: Optional[int] = None, seconds: Optional[int] = None,
                           amount: Optional[int] = None, staff_id: Optional[int] = None, note: str = "",
                           station_id: Optional[int] = None) -> dict:
        member = self.member_row(member_id)
        if not member:
            raise EngineError("not_found", "Member not found.", 404)
        active = self.member_active_session(member_id)
        if station_id is None and active is not None:
            station_id = active["station_id"]
        station = self.station_row(station_id) if station_id else None
        secs, amt, pkg_id = self._resolve_sale(package_id, seconds, amount, station["group_id"] if station else None)
        if secs < 0 and member["time_balance_seconds"] + secs < 0:
            raise EngineError("invalid", "Cannot remove more time than the member has.")
        kind = "adjust" if secs < 0 else "topup"
        with self.db.transaction():
            self.db.execute("UPDATE members SET time_balance_seconds = time_balance_seconds + ? WHERE id=?", (secs, member_id))
            tx_id = self.db.insert(
                "INSERT INTO transactions (kind, member_id, session_id, station_id, package_id, staff_id, seconds, amount, note, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (kind, member_id, active["id"] if active else None, station_id, pkg_id, staff_id, secs, amt, note, self.now_iso()),
            )
        self.audit(staff_id, f"member.{kind}", f"{member['username']} {secs:+d}s {amt}")
        if active is not None:
            fresh = self.session_row(active["id"])
            view = self.session_view(fresh)
            self._prime_warnings(active["id"], view["remaining_seconds"])
            await self.hub.send_station(active["station_id"], {"type": "session_update", "session": view, "event": "topup"})
        await self.broadcast_stations()
        return {"member": self.member_view(self.member_row(member_id)),
                "transaction": dict(self.db.one("SELECT * FROM transactions WHERE id=?", (tx_id,)))}

    async def topup_session(self, session_id: int, *, package_id: Optional[int] = None, seconds: Optional[int] = None,
                            amount: Optional[int] = None, staff_id: Optional[int] = None, note: str = "") -> dict:
        sess = self.session_row(session_id)
        if not sess or sess["ended_at"]:
            raise EngineError("no_session", "Session is not running.", 404)
        if sess["kind"] == "member":
            return await self.topup_member(sess["member_id"], package_id=package_id, seconds=seconds, amount=amount,
                                           staff_id=staff_id, note=note, station_id=sess["station_id"])
        station = self.station_row(sess["station_id"])
        secs, amt, pkg_id = self._resolve_sale(package_id, seconds, amount, station["group_id"] if station else None)
        if sess["guest_seconds"] + secs <= 0:
            raise EngineError("invalid", "Cannot remove that much time.")
        with self.db.transaction():
            self.db.execute("UPDATE sessions SET guest_seconds = guest_seconds + ? WHERE id=?", (secs, session_id))
            tx_id = self.db.insert(
                "INSERT INTO transactions (kind, session_id, station_id, package_id, staff_id, seconds, amount, note, created_at) "
                "VALUES ('guest_time',?,?,?,?,?,?,?,?)",
                (session_id, sess["station_id"], pkg_id, staff_id, secs, amt, note, self.now_iso()),
            )
        self.audit(staff_id, "session.guest_topup", f"{station['name'] if station else ''} {secs:+d}s {amt}")
        view = self.session_view(self.session_row(session_id))
        self._prime_warnings(session_id, view["remaining_seconds"])
        await self.hub.send_station(sess["station_id"], {"type": "session_update", "session": view, "event": "topup"})
        await self.broadcast_stations()
        return {"session": view,
                "transaction": dict(self.db.one("SELECT * FROM transactions WHERE id=?", (tx_id,)))}

    def list_sessions(self, active_only: bool = False, limit: int = 100) -> list[dict]:
        sql = "SELECT * FROM sessions" + (" WHERE ended_at IS NULL" if active_only else "") + " ORDER BY id DESC LIMIT ?"
        return [self.session_view(r) for r in self.db.query(sql, (limit,))]

    def list_transactions(self, limit: int = 100, since: Optional[str] = None) -> list[dict]:
        sql = (
            "SELECT t.*, m.username AS member, p.name AS package_name, s.username AS staff, st.name AS station "
            "FROM transactions t LEFT JOIN members m ON m.id=t.member_id LEFT JOIN packages p ON p.id=t.package_id "
            "LEFT JOIN staff s ON s.id=t.staff_id LEFT JOIN stations st ON st.id=t.station_id "
        )
        params: list[Any] = []
        if since:
            sql += "WHERE t.created_at >= ? "
            params.append(since)
        sql += "ORDER BY t.id DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self.db.query(sql, params)]

    # ------------------------------------------------------------------ dashboard
    def local_day_start_iso(self) -> str:
        local = self.now().astimezone()
        start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        return iso(start)

    def dashboard(self) -> dict:
        stations = self.stations_view()
        since = self.local_day_start_iso()
        return {
            "cafe_name": self.settings.cafe_name,
            "currency": self.settings.currency,
            "server_time": self.now_iso(),
            "stations_total": len(stations),
            "stations_online": sum(1 for s in stations if s["online"]),
            "stations_in_session": sum(1 for s in stations if s["status"] == "in_session"),
            "stations_free": sum(1 for s in stations if s["status"] == "free"),
            "members_total": self.db.scalar("SELECT COUNT(*) FROM members") or 0,
            "members_today": self.db.scalar("SELECT COUNT(*) FROM members WHERE created_at >= ?", (since,)) or 0,
            "sessions_today": self.db.scalar("SELECT COUNT(*) FROM sessions WHERE started_at >= ?", (since,)) or 0,
            "revenue_today": self.db.scalar("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE created_at >= ?", (since,)) or 0,
            "seconds_sold_today": self.db.scalar("SELECT COALESCE(SUM(seconds),0) FROM transactions WHERE created_at >= ?", (since,)) or 0,
            "active_sessions": [s["session"] for s in stations if s["session"]],
        }

    # ------------------------------------------------------------------ settings
    def settings_view(self) -> dict:
        return {
            "cafe_name": self.settings.cafe_name,
            "currency": self.settings.currency,
            "auto_register_stations": self.settings.auto_register_stations,
            "min_session_seconds": self.settings.min_session_seconds,
            "warn_thresholds": list(self.settings.warn_thresholds),
        }

    def update_settings(self, staff_id: Optional[int], **fields: Any) -> dict:
        if fields.get("cafe_name") is not None:
            self.settings.cafe_name = fields["cafe_name"].strip() or self.settings.cafe_name
            self.db.set_setting("cafe_name", self.settings.cafe_name)
        if fields.get("currency") is not None:
            self.settings.currency = fields["currency"].strip().upper()[:6] or self.settings.currency
            self.db.set_setting("currency", self.settings.currency)
        if fields.get("auto_register_stations") is not None:
            self.settings.auto_register_stations = bool(fields["auto_register_stations"])
            self.db.set_setting("auto_register_stations", "1" if self.settings.auto_register_stations else "0")
        if fields.get("min_session_seconds") is not None:
            self.settings.min_session_seconds = int(fields["min_session_seconds"])
            self.db.set_setting("min_session_seconds", str(self.settings.min_session_seconds))
        self.audit(staff_id, "settings.update")
        return self.settings_view()

    # ------------------------------------------------------------------ shop: products
    def media_dir(self) -> Path:
        return Path(self.settings.media_dir)

    def _copy_seed_media(self) -> None:
        """First seed: put the shipped product pictures under <media_dir>/products (never overwrite)."""
        src = SEED_MEDIA_DIR / "products"
        dst = self.media_dir() / "products"
        if not src.is_dir():
            log.warning("seed media folder missing: %s", src)
            return
        dst.mkdir(parents=True, exist_ok=True)
        for file in src.iterdir():
            if file.is_file() and not (dst / file.name).exists():
                shutil.copyfile(file, dst / file.name)

    def product_row(self, product_id: Optional[int]) -> Optional[sqlite3.Row]:
        if product_id is None:
            return None
        return self.db.one("SELECT * FROM products WHERE id=?", (product_id,))

    @staticmethod
    def product_view(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "name": row["name"],
            "category": row["category"],
            "price": row["price"],
            "image": row["image"],
            "image_url": ("/media/" + row["image"]) if row["image"] else None,
            "best": bool(row["best"]),
            "enabled": bool(row["enabled"]),
            "sort": row["sort"],
        }

    def products(self, include_disabled: bool = True) -> list[dict]:
        sql = "SELECT * FROM products" + ("" if include_disabled else " WHERE enabled=1") + " ORDER BY sort, name"
        return [self.product_view(r) for r in self.db.query(sql)]

    @staticmethod
    def _check_product_fields(fields: dict) -> None:
        if "name" in fields and not fields["name"]:
            raise EngineError("invalid", "Product name is required.")
        if "category" in fields and fields["category"] not in PRODUCT_CATEGORIES:
            raise EngineError("invalid", f"Category must be one of {', '.join(PRODUCT_CATEGORIES)}.")
        if "price" in fields and fields["price"] < 0:
            raise EngineError("invalid", "Price cannot be negative.")

    async def create_product(self, name: str, category: str = "snacks", price: int = 0, best: bool = False,
                             enabled: bool = True, sort: Optional[int] = None, staff_id: Optional[int] = None) -> dict:
        fields = {"name": (name or "").strip(), "category": category, "price": int(price)}
        self._check_product_fields(fields)
        if sort is None:   # no position given: append to the end of the kiosk grid
            sort = int(self.db.scalar("SELECT COALESCE(MAX(sort), -1) + 1 FROM products") or 0)
        pid = self.db.insert(
            "INSERT INTO products (name, category, price, best, enabled, sort, created_at) VALUES (?,?,?,?,?,?,?)",
            (fields["name"], category, fields["price"], 1 if best else 0, 1 if enabled else 0, int(sort), self.now_iso()),
        )
        self.audit(staff_id, "product.create", fields["name"])
        await self.push_shop()
        return self.product_view(self.product_row(pid))

    async def update_product(self, product_id: int, staff_id: Optional[int] = None, **fields: Any) -> dict:
        row = self.product_row(product_id)
        if not row:
            raise EngineError("not_found", "Product not found.", 404)
        sets, params = [], []
        for key in ("name", "category", "price", "best", "enabled", "sort"):
            if fields.get(key) is None:
                continue
            value = fields[key]
            if key == "name":
                value = value.strip()
                self._check_product_fields({"name": value})
            elif key in ("best", "enabled"):
                value = 1 if value else 0
            else:
                value = int(value) if key != "category" else value
                self._check_product_fields({key: value})
            sets.append(f"{key}=?")
            params.append(value)
        if sets:
            params.append(product_id)
            self.db.execute(f"UPDATE products SET {', '.join(sets)} WHERE id=?", params)
        view = self.product_view(self.product_row(product_id))
        self.audit(staff_id, "product.update", view["name"])
        await self.push_shop()
        return view

    async def delete_product(self, product_id: int, staff_id: Optional[int] = None) -> None:
        row = self.product_row(product_id)
        if not row:
            raise EngineError("not_found", "Product not found.", 404)
        if self.db.one("SELECT 1 FROM orders WHERE product_id=? LIMIT 1", (product_id,)):
            # keep order history intact: disable instead of delete
            self.db.execute("UPDATE products SET enabled=0 WHERE id=?", (product_id,))
        else:
            self.db.execute("DELETE FROM products WHERE id=?", (product_id,))
            self._remove_product_file(row["image"])
        self.audit(staff_id, "product.delete", row["name"])
        await self.push_shop()

    def _remove_product_file(self, image: Optional[str]) -> None:
        """Delete an upload from disk, but only if it lives in media/products and no other product uses it."""
        if not image or not image.startswith("products/"):
            return
        if self.db.one("SELECT 1 FROM products WHERE image=? LIMIT 1", (image,)):
            return
        products_dir = (self.media_dir() / "products").resolve()
        path = (self.media_dir() / image).resolve()
        if path.parent != products_dir or not path.is_file():
            return
        try:
            path.unlink()
        except OSError as exc:
            log.warning("could not delete %s: %s", path, exc)

    async def set_product_image(self, product_id: int, filename: str, data: str, staff_id: Optional[int] = None) -> dict:
        row = self.product_row(product_id)
        if not row:
            raise EngineError("not_found", "Product not found.", 404)
        ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
        if ext not in IMAGE_EXTENSIONS:
            raise EngineError("invalid", "Picture must be a .png, .jpg, .jpeg or .webp file.")
        payload = (data or "").strip()
        if payload.startswith("data:"):          # tolerate a data: URL prefix
            payload = payload.split(",", 1)[-1]
        try:
            raw = base64.b64decode(payload, validate=True)
        except (ValueError, TypeError):
            raise EngineError("invalid", "Picture data is not valid base64.")
        if len(raw) > MAX_IMAGE_BYTES:
            raise EngineError("too_large", "Picture is larger than 4 MB.", 413)
        sniffed = sniff_image_ext(raw)
        if sniffed is None:
            raise EngineError("invalid", "File content is not a PNG, JPEG or WEBP picture.")
        products_dir = self.media_dir() / "products"
        products_dir.mkdir(parents=True, exist_ok=True)
        name = f"{product_id}-{int(self.now().timestamp())}.{sniffed}"
        image = f"products/{name}"
        (products_dir / name).write_bytes(raw)
        old = row["image"]
        self.db.execute("UPDATE products SET image=? WHERE id=?", (image, product_id))
        if old != image:
            self._remove_product_file(old)
        self.audit(staff_id, "product.image", row["name"])
        await self.push_shop()
        return self.product_view(self.product_row(product_id))

    async def clear_product_image(self, product_id: int, staff_id: Optional[int] = None) -> dict:
        row = self.product_row(product_id)
        if not row:
            raise EngineError("not_found", "Product not found.", 404)
        self.db.execute("UPDATE products SET image=NULL WHERE id=?", (product_id,))
        self._remove_product_file(row["image"])
        self.audit(staff_id, "product.image", f"{row['name']} (removed)")
        await self.push_shop()
        return self.product_view(self.product_row(product_id))

    # ------------------------------------------------------------------ shop: orders
    def order_row(self, order_id: int) -> Optional[sqlite3.Row]:
        return self.db.one(_ORDER_SQL + " WHERE o.id=?", (order_id,))

    @staticmethod
    def order_view(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "station": {"id": row["station_id"], "name": row["station_name"]},
            "member": {"id": row["member_id"], "username": row["member_username"]} if row["member_id"] is not None else None,
            "session_id": row["session_id"],
            "product_id": row["product_id"],
            "product_name": row["product_name"],
            "qty": row["qty"],
            "unit_price": row["unit_price"],
            "total": row["total"],
            "status": row["status"],
            "note": row["note"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_orders(self, status: str = "pending", limit: int = 200) -> list[dict]:
        """The pending queue is oldest first; history is newest first."""
        if status == "all":
            rows = self.db.query(_ORDER_SQL + " ORDER BY o.id DESC LIMIT ?", (limit,))
        elif status in ORDER_STATUSES:
            direction = "ASC" if status == "pending" else "DESC"
            rows = self.db.query(_ORDER_SQL + f" WHERE o.status=? ORDER BY o.id {direction} LIMIT ?", (status, limit))
        else:
            raise EngineError("invalid", "Status must be pending, done, cancelled or all.")
        return [self.order_view(r) for r in rows]

    def pending_orders(self) -> list[dict]:
        return self.list_orders("pending", 500)

    async def create_order(self, station_id: int, product_id: int, qty: int = 1, note: Optional[str] = None) -> dict:
        station = self.station_row(station_id)
        if not station:
            raise EngineError("not_found", "Station not found.", 404)
        sess = self.active_session_row(station_id)
        if sess is None:
            raise EngineError("no_session", "Log in or start a session before ordering.", 409)
        product = self.product_row(product_id)
        if not product or not product["enabled"]:
            raise EngineError("not_found", "Product not found.", 404)
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            raise EngineError("invalid", "Quantity must be a number.")
        if not 1 <= qty <= MAX_ORDER_QTY:
            raise EngineError("invalid", f"Quantity must be between 1 and {MAX_ORDER_QTY}.")
        note = (str(note).strip()[:200] or None) if note else None
        oid = self.db.insert(
            "INSERT INTO orders (station_id, session_id, member_id, product_id, product_name, qty, unit_price, total, note, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (station_id, sess["id"], sess["member_id"], product_id, product["name"], qty, product["price"],
             qty * int(product["price"]), note, self.now_iso()),
        )
        self.audit(None, "kiosk.order", f"{station['name']}: {product['name']} x{qty}")
        await self.broadcast_orders()
        return self.order_view(self.order_row(oid))

    async def set_order_status(self, order_id: int, status: str, staff_id: Optional[int] = None) -> dict:
        row = self.order_row(order_id)
        if not row:
            raise EngineError("not_found", "Order not found.", 404)
        if row["status"] == status:          # idempotent: done twice / cancelled twice is fine
            return self.order_view(row)
        if row["status"] != "pending":
            raise EngineError("not_pending", f"Order is already {row['status']}.", 409)
        now = self.now_iso()
        with self.db.transaction():
            self.db.execute("UPDATE orders SET status=?, staff_id=?, updated_at=? WHERE id=?", (status, staff_id, now, order_id))
            if status == "done":
                # a delivered order is a sale: it shows up in revenue like time sales do
                self.db.insert(
                    "INSERT INTO transactions (kind, member_id, session_id, station_id, staff_id, seconds, amount, note, created_at) "
                    "VALUES ('shop',?,?,?,?,0,?,?,?)",
                    (row["member_id"], row["session_id"], row["station_id"], staff_id, row["total"],
                     f"{row['product_name']} x{row['qty']}", now),
                )
        self.audit(staff_id, f"order.{status}", f"{row['station_name']}: {row['product_name']} x{row['qty']}")
        view = self.order_view(self.order_row(order_id))
        await self.hub.send_station(row["station_id"], {"type": "order_update", "order": view})
        await self.broadcast_orders()
        return view

    # ------------------------------------------------------------------ events (the client's Events page)
    def event_row(self, event_id: int) -> Optional[sqlite3.Row]:
        return self.db.one("SELECT * FROM events WHERE id=?", (event_id,))

    @staticmethod
    def event_view(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "title": row["title"],
            "kind": row["kind"],
            "game": row["game"],
            "tag": row["tag"],
            "players": row["players"],
            "when": row["when_text"],
            "prize": row["prize"],
            "status": row["status"],
            "cats": [c for c in row["cats"].split(",") if c],
            "enabled": bool(row["enabled"]),
            "show_home": bool(row["show_home"]),
            "show_events": bool(row["show_events"]),
            "sort": row["sort"],
        }

    def events(self, include_disabled: bool = True) -> list[dict]:
        sql = "SELECT * FROM events" + ("" if include_disabled else " WHERE enabled=1") + " ORDER BY sort, id"
        return [self.event_view(r) for r in self.db.query(sql)]

    @staticmethod
    def _event_columns(fields: dict) -> dict:
        """Validate + normalise incoming event fields into column values (only the keys present)."""
        out: dict[str, Any] = {}
        if "title" in fields:
            out["title"] = (fields["title"] or "").strip()
            if not out["title"]:
                raise EngineError("invalid", "Event title is required.")
        if "kind" in fields:
            if fields["kind"] not in EVENT_KINDS:
                raise EngineError("invalid", "Kind must be 'event' or 'offer'.")
            out["kind"] = fields["kind"]
        if "status" in fields:
            if fields["status"] not in EVENT_STATUSES:
                raise EngineError("invalid", "Status must be 'live' or 'upcoming'.")
            out["status"] = fields["status"]
        for key in ("game", "tag", "players", "prize"):
            if key in fields:
                out[key] = (fields[key] or "").strip()
        if "when" in fields:
            out["when_text"] = (fields["when"] or "").strip()
        if "cats" in fields:
            cats = [str(c).strip().lower() for c in (fields["cats"] or [])]
            bad = [c for c in cats if c not in EVENT_CATS]
            if bad:
                raise EngineError("invalid", f"Unknown category: {', '.join(bad)}.")
            out["cats"] = ",".join(dict.fromkeys(cats))   # de-duplicate, keep order
        for flag in ("enabled", "show_home", "show_events"):
            if flag in fields:
                out[flag] = 1 if fields[flag] else 0
        if "sort" in fields:
            out["sort"] = int(fields["sort"])
        return out

    def _insert_event(self, fields: dict) -> int:
        cols = self._event_columns(fields)
        cols["created_at"] = self.now_iso()
        names = ", ".join(cols)
        return self.db.insert(f"INSERT INTO events ({names}) VALUES ({', '.join('?' * len(cols))})", list(cols.values()))

    async def create_event(self, staff_id: Optional[int] = None, **fields: Any) -> dict:
        fields = {k: v for k, v in fields.items() if v is not None}
        fields.setdefault("title", "")
        if "sort" not in fields:   # no position given: append after the existing events
            fields["sort"] = int(self.db.scalar("SELECT COALESCE(MAX(sort), -1) + 1 FROM events") or 0)
        eid = self._insert_event(fields)
        view = self.event_view(self.event_row(eid))
        self.audit(staff_id, "event.create", view["title"])
        await self.push_events()
        return view

    async def update_event(self, event_id: int, staff_id: Optional[int] = None, **fields: Any) -> dict:
        if not self.event_row(event_id):
            raise EngineError("not_found", "Event not found.", 404)
        cols = self._event_columns({k: v for k, v in fields.items() if v is not None})
        if cols:
            params = list(cols.values()) + [event_id]
            self.db.execute(f"UPDATE events SET {', '.join(f'{k}=?' for k in cols)} WHERE id=?", params)
        view = self.event_view(self.event_row(event_id))
        self.audit(staff_id, "event.update", view["title"])
        await self.push_events()
        return view

    async def delete_event(self, event_id: int, staff_id: Optional[int] = None) -> None:
        row = self.event_row(event_id)
        if not row:
            raise EngineError("not_found", "Event not found.", 404)
        self.db.execute("DELETE FROM events WHERE id=?", (event_id,))
        self.audit(staff_id, "event.delete", row["title"])
        await self.push_events()

    async def set_all_events_enabled(self, enabled: bool, staff_id: Optional[int] = None) -> list[dict]:
        """'Remove all events from the client' (and the way back)."""
        self.db.execute("UPDATE events SET enabled=?", (1 if enabled else 0,))
        self.audit(staff_id, "event.enable_all" if enabled else "event.disable_all")
        await self.push_events()
        return self.events()

    # ------------------------------------------------------------------ pushes
    async def push_session(self, station_id: int) -> None:
        sess = self.active_session_row(station_id)
        if sess is not None:
            await self.hub.send_station(station_id, {"type": "session_update", "session": self.session_view(sess)})

    async def broadcast_stations(self) -> None:
        if not self.hub.admins:
            return
        self._last_admin_push = time.monotonic()
        await self.hub.broadcast_admin({"type": "stations", "stations": self.stations_view(), "server_time": self.now_iso()})

    async def _push_all_stations(self, message: dict) -> None:
        for station_id in list(self.hub.stations):
            await self.hub.send_station(station_id, message)

    async def push_shop(self) -> None:
        """Every connected kiosk gets the current (enabled) product list."""
        if self.hub.stations:
            await self._push_all_stations({"type": "shop", "items": self.products(include_disabled=False)})

    async def push_events(self) -> None:
        if self.hub.stations:
            await self._push_all_stations({"type": "events", "events": self.events(include_disabled=False)})

    async def broadcast_orders(self) -> None:
        """The counter screens get the whole pending queue on every change."""
        if self.hub.admins:
            await self.hub.broadcast_admin({"type": "orders", "orders": self.pending_orders()})

    # ------------------------------------------------------------------ the loop
    async def tick(self) -> None:
        """Runs every second: expire sessions, send warnings, resync clocks."""
        self._last_tick = time.monotonic()          # read by /api/status ("Session engine" check)
        thresholds = sorted(self.settings.warn_thresholds, reverse=True)
        for sess in self.db.query("SELECT * FROM sessions WHERE ended_at IS NULL"):
            member = self.member_row(sess["member_id"]) if sess["member_id"] is not None else None
            budget = self.session_budget(sess, member)
            elapsed = int((self.now() - parse_iso(sess["started_at"])).total_seconds())
            remaining = budget - elapsed
            if remaining <= 0:
                await self.end_session(sess["id"], "expired")
                continue
            last = self._warned.get(sess["id"])
            for th in thresholds:
                if remaining <= th and (last is None or last > th):
                    self._warned[sess["id"]] = th
                    await self.hub.send_station(sess["station_id"], {"type": "warning", "remaining_seconds": remaining, "threshold": th})
                    break
            mono = time.monotonic()
            if mono - self._resync_at.get(sess["id"], 0.0) >= self.settings.resync_seconds:
                self._resync_at[sess["id"]] = mono
                await self.hub.send_station(sess["station_id"], {"type": "session_update", "session": self.session_view(sess, member)})
        if self.hub.admins and time.monotonic() - self._last_admin_push >= 5:
            await self.broadcast_stations()
