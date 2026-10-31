"""Server settings, loaded from data/server.json (created on first run)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import sys

if getattr(sys, "frozen", False):                         # PyInstaller build: data next to the exe, admin inside the bundle
    BASE_DIR = Path(sys.executable).resolve().parent
    ADMIN_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR)) / "admin"
else:
    BASE_DIR = Path(__file__).resolve().parent.parent      # .../server
    ADMIN_DIR = BASE_DIR / "admin"
DATA_DIR = Path(os.environ.get("VORTEX_DATA_DIR", BASE_DIR / "data"))
SEED_MEDIA_DIR = Path(__file__).resolve().parent / "seed_media"   # shipped product pictures (also inside the bundle)


@dataclass
class Settings:
    host: str = "0.0.0.0"
    port: int = 8787
    db_path: str = str(DATA_DIR / "vortex.db")
    media_dir: str = str(DATA_DIR / "media")   # product pictures etc., served at /media
    cafe_name: str = "Vortex Gaming Center"
    currency: str = "EGP"
    auto_register_stations: bool = True      # new PCs may join by name on first connect
    token_ttl_hours: int = 12                # staff login token lifetime
    tick_seconds: float = 1.0                # session engine loop
    resync_seconds: int = 30                 # push a fresh session_update this often
    warn_thresholds: list[int] = field(default_factory=lambda: [1800, 600, 300, 60])
    min_session_seconds: int = 60            # cannot start with less time than this
    debug: bool = False


def load_settings(path: Path | None = None) -> Settings:
    """Read data/server.json, creating it with defaults when missing."""
    path = path or (DATA_DIR / "server.json")
    settings = Settings()
    if path.exists():
        data = json.loads(path.read_text("utf-8"))
        for key, value in data.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(settings), indent=2), "utf-8")
    return settings


def save_settings(settings: Settings, path: Path | None = None) -> None:
    path = path or (DATA_DIR / "server.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), "utf-8")
