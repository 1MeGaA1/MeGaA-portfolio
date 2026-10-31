"""Thin SQLite layer. One shared connection, a lock, explicit transactions.

No ORM on purpose: the schema is small and every query is readable SQL.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS staff (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    pin_hash      TEXT,
    role          TEXT NOT NULL DEFAULT 'admin',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS station_groups (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    rate_per_hour INTEGER NOT NULL DEFAULT 0,
    sort          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stations (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    key        TEXT NOT NULL UNIQUE,
    group_id   INTEGER REFERENCES station_groups(id) ON DELETE SET NULL,
    hostname   TEXT,
    ip         TEXT,
    last_seen  TEXT,
    locked     INTEGER NOT NULL DEFAULT 0,
    enabled    INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS members (
    id                   INTEGER PRIMARY KEY,
    email                TEXT NOT NULL UNIQUE COLLATE NOCASE,
    username             TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash        TEXT NOT NULL,
    tier                 TEXT NOT NULL DEFAULT 'BRONZE',
    time_balance_seconds INTEGER NOT NULL DEFAULT 0,
    points               INTEGER NOT NULL DEFAULT 0,
    enabled              INTEGER NOT NULL DEFAULT 1,
    created_at           TEXT NOT NULL,
    last_login_at        TEXT
);

CREATE TABLE IF NOT EXISTS packages (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    seconds  INTEGER NOT NULL,
    price    INTEGER NOT NULL,
    group_id INTEGER REFERENCES station_groups(id) ON DELETE SET NULL,
    enabled  INTEGER NOT NULL DEFAULT 1,
    sort     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    id            INTEGER PRIMARY KEY,
    station_id    INTEGER NOT NULL REFERENCES stations(id),
    member_id     INTEGER REFERENCES members(id),
    kind          TEXT NOT NULL,              -- 'member' | 'guest'
    started_at    TEXT NOT NULL,
    ended_at      TEXT,
    end_reason    TEXT,                       -- 'logout' | 'expired' | 'admin' | 'station_lost'
    guest_seconds INTEGER NOT NULL DEFAULT 0, -- prepaid budget for guest sessions
    seconds_used  INTEGER,
    started_by    TEXT NOT NULL DEFAULT 'client'
);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(station_id) WHERE ended_at IS NULL;

CREATE TABLE IF NOT EXISTS transactions (
    id         INTEGER PRIMARY KEY,
    kind       TEXT NOT NULL,                 -- 'topup' | 'guest_time' | 'adjust' | 'shop'
    member_id  INTEGER REFERENCES members(id),
    session_id INTEGER REFERENCES sessions(id),
    station_id INTEGER REFERENCES stations(id),
    package_id INTEGER REFERENCES packages(id),
    staff_id   INTEGER REFERENCES staff(id),
    seconds    INTEGER NOT NULL DEFAULT 0,
    amount     INTEGER NOT NULL DEFAULT 0,    -- money in minor units (e.g. piasters)
    note       TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tx_created ON transactions(created_at);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id       INTEGER PRIMARY KEY,
    at       TEXT NOT NULL,
    staff_id INTEGER,
    action   TEXT NOT NULL,
    detail   TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    category   TEXT NOT NULL DEFAULT 'snacks',    -- 'drinks' | 'snacks' | 'meals'
    price      INTEGER NOT NULL DEFAULT 0,        -- MINOR units (2500 = 25.00)
    image      TEXT,                              -- media-relative path, e.g. 'products/cocacola.png'
    best       INTEGER NOT NULL DEFAULT 0,        -- 1 = shown in BEST SELLERS
    enabled    INTEGER NOT NULL DEFAULT 1,
    sort       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY,
    station_id   INTEGER NOT NULL REFERENCES stations(id),
    session_id   INTEGER REFERENCES sessions(id),
    member_id    INTEGER REFERENCES members(id),
    product_id   INTEGER REFERENCES products(id),
    product_name TEXT NOT NULL,                   -- snapshot at order time
    qty          INTEGER NOT NULL DEFAULT 1,
    unit_price   INTEGER NOT NULL DEFAULT 0,      -- snapshot, minor units
    total        INTEGER NOT NULL DEFAULT 0,      -- qty * unit_price
    status       TEXT NOT NULL DEFAULT 'pending', -- 'pending' | 'done' | 'cancelled'
    note         TEXT,
    staff_id     INTEGER REFERENCES staff(id),    -- who marked done/cancelled
    created_at   TEXT NOT NULL,
    updated_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'event',    -- 'event' | 'offer'
    game        TEXT NOT NULL DEFAULT '',         -- e.g. 'VALORANT · 5v5'
    tag         TEXT NOT NULL DEFAULT '',         -- small label, e.g. 'FLAGSHIP TOURNAMENT · REGISTRATION OPEN'
    players     TEXT NOT NULL DEFAULT '',         -- e.g. '256 players'
    when_text   TEXT NOT NULL DEFAULT '',         -- e.g. 'TOMORROW 8PM' / 'Starts in 2h 15m'
    prize       TEXT NOT NULL DEFAULT '',         -- free text, e.g. 'EGP 5,000'
    status      TEXT NOT NULL DEFAULT 'upcoming', -- 'live' | 'upcoming'
    cats        TEXT NOT NULL DEFAULT '',         -- comma list from: live,upcoming,weekly,weekend,tournament,offer
    enabled     INTEGER NOT NULL DEFAULT 1,
    show_home   INTEGER NOT NULL DEFAULT 0,       -- 1 = featured banner on client Home
    show_events INTEGER NOT NULL DEFAULT 1,       -- 1 = listed on client Events page
    sort        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None -> autocommit; we issue BEGIN/COMMIT ourselves.
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        if self.path != ":memory:":
            self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    # -- basic helpers ---------------------------------------------------
    def execute(self, sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
        with self.lock:
            return self.conn.execute(sql, params)

    def insert(self, sql: str, params: tuple | list = ()) -> int:
        with self.lock:
            return int(self.conn.execute(sql, params).lastrowid)

    def query(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, params).fetchall()

    def one(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        with self.lock:
            return self.conn.execute(sql, params).fetchone()

    def scalar(self, sql: str, params: tuple | list = ()) -> Any:
        row = self.one(sql, params)
        return None if row is None else row[0]

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self.lock:
            self.conn.execute("BEGIN")
            try:
                yield
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise
            else:
                self.conn.execute("COMMIT")

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    # -- schema ----------------------------------------------------------
    def init_schema(self) -> None:
        with self.lock:
            self.conn.executescript(SCHEMA)
            version = self.scalar("SELECT version FROM schema_version")
            if version is None:
                self.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))

    # -- settings key/value ---------------------------------------------
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        value = self.scalar("SELECT value FROM settings WHERE key=?", (key,))
        return default if value is None else value

    def set_setting(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]
