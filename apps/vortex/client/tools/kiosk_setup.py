"""Turn a Windows user account into a Vortex kiosk (and back).

Run this ON THE GAMING PC, logged in as the account customers will use
(a standard, non-admin user such as "player"). Never run it on your own PC.

    python tools\\kiosk_setup.py status
    python tools\\kiosk_setup.py autostart --on     # start Vortex when this user logs in (safe first step)
    python tools\\kiosk_setup.py taskmgr --off      # disable Task Manager for this user
    python tools\\kiosk_setup.py shell --on         # replace the desktop (explorer.exe) with Vortex for this user
    python tools\\kiosk_setup.py shell --off        # undo
    python tools\\kiosk_setup.py all --on / --off   # everything above

Everything is per-user (HKCU) and reversible. Keep an admin account on the PC that you
never run this on, so you can always log in normally and undo it.
"""
from __future__ import annotations

import argparse
import os
import sys
import winreg
from pathlib import Path

CLIENT_DIR = Path(__file__).resolve().parent.parent
RUN_BAT = CLIENT_DIR / "run_client.bat"
WINLOGON = r"Software\Microsoft\Windows NT\CurrentVersion\Winlogon"
POLICIES_SYSTEM = r"Software\Microsoft\Windows\CurrentVersion\Policies\System"
STARTUP_DIR = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
STARTUP_BAT = STARTUP_DIR / "Vortex Kiosk.bat"


def _get(path: str, name: str):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def _set(path: str, name: str, value, kind=winreg.REG_SZ) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
        winreg.SetValueEx(key, name, 0, kind, value)


def _delete(path: str, name: str) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
    except OSError:
        pass


def shell(on: bool) -> None:
    if on:
        _set(WINLOGON, "Shell", f'cmd.exe /c "{RUN_BAT}"')
        print(f"Shell replaced for this user -> {RUN_BAT}\nLog out and back in to see it. Ctrl+Shift+Q + staff PIN exits Vortex;")
        print("after that run  shell --off  to get the desktop back.")
    else:
        _delete(WINLOGON, "Shell")
        print("Shell restored to explorer.exe for this user (takes effect at next login).")


def taskmgr(on: bool) -> None:
    if on:
        _delete(POLICIES_SYSTEM, "DisableTaskMgr")
        print("Task Manager enabled.")
    else:
        _set(POLICIES_SYSTEM, "DisableTaskMgr", 1, winreg.REG_DWORD)
        print("Task Manager disabled for this user.")


def autostart(on: bool) -> None:
    STARTUP_DIR.mkdir(parents=True, exist_ok=True)
    if on:
        STARTUP_BAT.write_text(f'@echo off\r\nstart "" /min cmd /c "{RUN_BAT}"\r\n', "utf-8")
        print(f"Autostart created: {STARTUP_BAT}")
    else:
        if STARTUP_BAT.exists():
            STARTUP_BAT.unlink()
        print("Autostart removed.")


def status() -> None:
    print(f"Client folder : {CLIENT_DIR}")
    print(f"User          : {os.environ.get('USERNAME')}")
    print(f"Shell         : {_get(WINLOGON, 'Shell') or 'explorer.exe (default)'}")
    print(f"Task Manager  : {'DISABLED' if _get(POLICIES_SYSTEM, 'DisableTaskMgr') == 1 else 'enabled'}")
    print(f"Autostart     : {'yes' if STARTUP_BAT.exists() else 'no'}")


def main() -> None:
    if sys.platform != "win32":
        sys.exit("Windows only.")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["status", "shell", "taskmgr", "autostart", "all"])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--on", action="store_true")
    group.add_argument("--off", action="store_true")
    args = parser.parse_args()
    if args.action == "status":
        status()
        return
    if not (args.on or args.off):
        sys.exit("Say --on or --off.")
    on = args.on
    if args.action in ("shell", "all"):
        shell(on)
    if args.action in ("taskmgr", "all"):
        taskmgr(not on)          # --on means "kiosk on" = task manager off
    if args.action in ("autostart", "all"):
        autostart(on)
    print()
    status()


if __name__ == "__main__":
    main()
