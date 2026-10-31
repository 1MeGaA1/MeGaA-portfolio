"""client.json (connection + kiosk settings) and catalog.json (what this PC can launch)."""
from __future__ import annotations

import json
import socket
from dataclasses import asdict, dataclass
from pathlib import Path

import sys

if getattr(sys, "frozen", False):                     # PyInstaller build: config next to the exe, UI inside the bundle
    BASE_DIR = Path(sys.executable).resolve().parent
    UI_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR)) / "ui"
else:
    BASE_DIR = Path(__file__).resolve().parent.parent  # .../client
    UI_DIR = BASE_DIR / "ui"
CONFIG_PATH = BASE_DIR / "client.json"
CATALOG_PATH = BASE_DIR / "catalog.json"
LOG_PATH = BASE_DIR / "client.log"


@dataclass
class ClientConfig:
    server: str = "ws://127.0.0.1:8787"   # localhost by default; set to the counter PC on cafe stations, e.g. ws://192.168.1.10:8787
    station_name: str = ""                 # defaults to this PC's hostname
    station_key: str = ""                  # filled in automatically on first connect
    fullscreen: bool = True
    kiosk: bool = True                     # keyboard hook + foreground guard + always on top
    block_alt_tab_in_session: bool = False # True = customers cannot Alt+Tab even while playing
    local_exit_pin: str = ""               # emergency PIN that works when the server is offline
    debug: bool = False                    # windowed, dev tools, verbose log


def load_config() -> ClientConfig:
    cfg = ClientConfig()
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text("utf-8"))
        except ValueError:
            data = {}
        for key, value in data.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
    if not cfg.station_name:
        cfg.station_name = socket.gethostname()[:32]
    if not CONFIG_PATH.exists():
        save_config(cfg)
    return cfg


def save_config(cfg: ClientConfig) -> None:
    CONFIG_PATH.write_text(json.dumps(asdict(cfg), indent=2), "utf-8")


# Names must match the cards in ui/index.html (case-insensitive).
# Each entry is either  {"exe": "...", "args": [...]}  or  {"launch": "<uri>"}.
# "process" is the exe name to watch so Vortex knows when the game closes.
DEFAULT_CATALOG = {
    "_readme": "Edit paths for this PC. 'exe' launches a program, 'launch' opens a URI (steam://, riot, epic). "
               "'process' is the process name Vortex watches and kills when the session ends.",
    "games": {
        "Counter-Strike 2": {"launch": "steam://run/730", "process": "cs2.exe"},
        "Dota 2": {"launch": "steam://run/570", "process": "dota2.exe"},
        "Apex Legends": {"launch": "steam://run/1172470", "process": "r5apex.exe"},
        "GTA V": {"launch": "steam://run/271590", "process": "GTA5.exe"},
        "Elden Ring": {"launch": "steam://run/1245620", "process": "eldenring.exe"},
        "Valorant": {"exe": "C:/Riot Games/Riot Client/RiotClientServices.exe",
                     "args": ["--launch-product=valorant", "--launch-patchline=live"], "process": "VALORANT-Win64-Shipping.exe"},
        "League of Legends": {"exe": "C:/Riot Games/Riot Client/RiotClientServices.exe",
                              "args": ["--launch-product=league_of_legends", "--launch-patchline=live"], "process": "League of Legends.exe"},
        "Fortnite": {"launch": "com.epicgames.launcher://apps/Fortnite?action=launch&silent=true", "process": "FortniteClient-Win64-Shipping.exe"},
        "Rocket League": {"launch": "com.epicgames.launcher://apps/Sugar?action=launch&silent=true", "process": "RocketLeague.exe"},
        "Minecraft": {"exe": "C:/Program Files (x86)/Minecraft Launcher/MinecraftLauncher.exe", "process": "Minecraft.Windows.exe"},
    },
    "apps": {
        "Chrome": {"exe": "C:/Program Files/Google/Chrome/Application/chrome.exe", "process": "chrome.exe"},
        "Firefox": {"exe": "C:/Program Files/Mozilla Firefox/firefox.exe", "process": "firefox.exe"},
        "Discord": {"launch": "discord://", "process": "Discord.exe"},
        "Spotify": {"launch": "spotify:", "process": "Spotify.exe"},
        "Steam": {"launch": "steam://open/main", "process": "steam.exe"},
        "Epic Games": {"launch": "com.epicgames.launcher://store", "process": "EpicGamesLauncher.exe"},
        "Riot Client": {"exe": "C:/Riot Games/Riot Client/RiotClientServices.exe", "process": "RiotClientServices.exe"},
        "EA Play": {"exe": "C:/Program Files/Electronic Arts/EA Desktop/EA Desktop/EADesktop.exe", "process": "EADesktop.exe"},
        "Telegram": {"launch": "tg://", "process": "Telegram.exe"},
        "VLC": {"exe": "C:/Program Files/VideoLAN/VLC/vlc.exe", "process": "vlc.exe"},
        "YouTube": {"exe": "C:/Program Files/Google/Chrome/Application/chrome.exe", "args": ["--new-window", "https://youtube.com"], "process": "chrome.exe"},
        "Netflix": {"exe": "C:/Program Files/Google/Chrome/Application/chrome.exe", "args": ["--new-window", "https://netflix.com"], "process": "chrome.exe"},
        "Twitch": {"exe": "C:/Program Files/Google/Chrome/Application/chrome.exe", "args": ["--new-window", "https://twitch.tv"], "process": "chrome.exe"},
    },
}


def load_catalog() -> dict:
    if CATALOG_PATH.exists():
        try:
            data = json.loads(CATALOG_PATH.read_text("utf-8"))
            if isinstance(data, dict):
                data.setdefault("games", {})
                data.setdefault("apps", {})
                return data
        except ValueError:
            pass
    CATALOG_PATH.write_text(json.dumps(DEFAULT_CATALOG, indent=2), "utf-8")
    return json.loads(json.dumps(DEFAULT_CATALOG))
