"""Request bodies for the REST API (pydantic)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class StaffLogin(BaseModel):
    username: str
    password: str


class StaffPasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class StaffPinChange(BaseModel):
    password: str
    pin: str = Field(min_length=4, max_length=12, pattern=r"^[0-9]+$")


class MemberCreate(BaseModel):
    email: str
    username: Optional[str] = None
    password: str = Field(min_length=4)
    tier: str = "BRONZE"


class MemberUpdate(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    tier: Optional[str] = None
    enabled: Optional[bool] = None
    password: Optional[str] = None
    points: Optional[int] = None


class TopUp(BaseModel):
    """Sell time. Either a package or custom seconds (+ optional explicit amount)."""
    package_id: Optional[int] = None
    seconds: Optional[int] = Field(default=None, ge=-86400 * 30, le=86400 * 30)
    amount: Optional[int] = Field(default=None, ge=0)
    note: str = ""


class StationCreate(BaseModel):
    name: str
    group_id: Optional[int] = None


class StationUpdate(BaseModel):
    name: Optional[str] = None
    group_id: Optional[int] = None
    enabled: Optional[bool] = None
    locked: Optional[bool] = None


class StationCommand(BaseModel):
    name: Literal["lock", "unlock", "restart", "shutdown", "reboot", "message"]
    title: str = ""
    body: str = ""
    level: Literal["info", "warn"] = "info"


class SessionStart(BaseModel):
    member_id: Optional[int] = None
    guest_minutes: Optional[int] = Field(default=None, ge=1, le=24 * 60)
    package_id: Optional[int] = None
    amount: Optional[int] = None


class GroupCreate(BaseModel):
    name: str
    rate_per_hour: int = Field(ge=0)


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    rate_per_hour: Optional[int] = Field(default=None, ge=0)


class PackageCreate(BaseModel):
    name: str
    seconds: int = Field(gt=0)
    price: int = Field(ge=0)
    group_id: Optional[int] = None
    sort: int = 0


class PackageUpdate(BaseModel):
    name: Optional[str] = None
    seconds: Optional[int] = Field(default=None, gt=0)
    price: Optional[int] = Field(default=None, ge=0)
    group_id: Optional[int] = None
    enabled: Optional[bool] = None
    sort: Optional[int] = None


class SettingsUpdate(BaseModel):
    cafe_name: Optional[str] = None
    currency: Optional[str] = None
    auto_register_stations: Optional[bool] = None
    min_session_seconds: Optional[int] = Field(default=None, ge=0)


class ProductCreate(BaseModel):
    """Prices are in MINOR units (2500 = 25.00), like packages."""
    name: str
    category: Literal["drinks", "snacks", "meals"] = "snacks"
    price: int = Field(default=0, ge=0)
    best: bool = False
    enabled: bool = True
    sort: Optional[int] = None      # omitted -> appended after the existing products


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[Literal["drinks", "snacks", "meals"]] = None
    price: Optional[int] = Field(default=None, ge=0)
    best: Optional[bool] = None
    enabled: Optional[bool] = None
    sort: Optional[int] = None


class ProductImage(BaseModel):
    """Picture upload: base64 JSON (no multipart support on the server)."""
    filename: str
    data: str


class EventCreate(BaseModel):
    title: str
    kind: Literal["event", "offer"] = "event"
    game: str = ""
    tag: str = ""
    players: str = ""
    when: str = ""
    prize: str = ""
    status: Literal["live", "upcoming"] = "upcoming"
    cats: Optional[list[str]] = None
    enabled: bool = True
    show_home: bool = False
    show_events: bool = True
    sort: Optional[int] = None      # omitted -> appended after the existing events


class EventUpdate(BaseModel):
    title: Optional[str] = None
    kind: Optional[Literal["event", "offer"]] = None
    game: Optional[str] = None
    tag: Optional[str] = None
    players: Optional[str] = None
    when: Optional[str] = None
    prize: Optional[str] = None
    status: Optional[Literal["live", "upcoming"]] = None
    cats: Optional[list[str]] = None
    enabled: Optional[bool] = None
    show_home: Optional[bool] = None
    show_events: Optional[bool] = None
    sort: Optional[int] = None
