# Installing Vortex in a cafe

Two parts: **the server** on the counter PC, **the client** on every gaming PC.
Both need Python 3.12 (https://python.org, tick "Add to PATH" during setup).

---

## 1. Server (counter PC)

**Packaged (recommended, no Python on the server):** build `serveruild_server.bat` on the dev
PC, copy `server\dist\VortexServer\` to the server and follow `docs/DEPLOY_WINDOWS_SERVER.md`
(firewall, start-at-boot, health check). **From source** (dev machine):

```
cd Vortex\server
pip install -r requirements.txt
run_server.bat
```

The console prints the admin address, e.g. `http://192.168.1.10:8787/admin/`.
Open it on the counter PC (or any PC on the cafe network).

- First login: **admin / admin**, exit PIN **1234**. Change both in *Settings* before opening day.
- Data lives in `server\data\vortex.db` (SQLite). Back that file up.
- Set your prices in *Pricing*: hourly rate per station group, plus packages ("2 hours = 38 EGP").
- Let the server start with Windows: put a shortcut to `run_server.bat` in the counter PC's
  Startup folder (`Win+R` → `shell:startup`).
- Allow port **8787** through Windows Firewall on the counter PC (Windows asks the first time;
  choose *Private networks*).

Interactive API docs: `http://<server>:8787/api/docs`. Protocol details: `docs/PROTOCOL.md`.

---

## 2. Client (each gaming PC)

```
copy the Vortex\client folder to C:\Vortex\client
cd C:\Vortex\client
pip install -r requirements.txt
python run_client.py
```

The first run creates `client.json`. Edit it:

```json
{
  "server": "ws://192.168.1.10:8787",   <- the counter PC
  "station_name": "PC-01",              <- what staff see in the admin panel
  "kiosk": true,                        <- keyboard hook + foreground guard + always on top
  "fullscreen": true,
  "local_exit_pin": "",                 <- optional emergency PIN that works even if the server is down
  "debug": false
}
```

Start it again. The station appears in *Stations* on the admin panel automatically
(auto-register, on by default). The server issues a `station_key` and the client stores it
in `client.json`; if you ever reinstall the client, click **⋯ → RESET KEY** on that station.

### Games and apps: `catalog.json`

The cards in the kiosk are fixed; `catalog.json` says what each one starts *on this PC*:

```json
"Counter-Strike 2": {"launch": "steam://run/730", "process": "cs2.exe"},
"Chrome": {"exe": "C:/Program Files/Google/Chrome/Application/chrome.exe", "process": "chrome.exe"}
```

- `launch` opens a URI (Steam, Epic, Riot, Discord, Spotify…). `exe` starts a program directly.
- `process` is the executable name Vortex watches, so it knows when the game closes and can
  close it when the session ends.

### Testing on your own PC first

Set `"kiosk": false, "fullscreen": false` in `client.json`: Vortex runs as a normal window
with no keyboard hook, so you can try everything safely. Set them back to `true` on the cafe PCs.

---

## 3. Locking the PC down (cafe PCs only)

Vortex blocks Win keys, Alt+Tab (while locked), Alt+F4 and Ctrl+Shift+Esc by itself.
Ctrl+Alt+Del cannot be blocked by any program, so also do this on each gaming PC:

1. Create a **standard (non-admin) Windows user** for customers, e.g. `player`, and keep your
   own admin account for maintenance. Set `player` to log in automatically
   (`Win+R` → `netplwiz`, untick "Users must enter a user name and password").
2. Log in as `player` and run, from `C:\Vortex\client`:
   ```
   python tools\kiosk_setup.py autostart --on     start Vortex at login (do this first, test it)
   python tools\kiosk_setup.py taskmgr --off      no Task Manager for this user
   python tools\kiosk_setup.py shell --on         Vortex replaces the desktop for this user
   ```
   `shell --on` means there is no explorer/taskbar at all for `player`; only Vortex and the
   games it launches. `python tools\kiosk_setup.py status` shows the current state and every
   step has an `--off` to undo it.
3. Leaving the kiosk: press **Ctrl+Shift+Q** and type the staff exit PIN (set in
   Settings on the admin panel). `run_client.bat` restarts Vortex automatically whenever it
   dies for any other reason.

Windows 10/11 **Pro** users can additionally use *Assigned Access* (Settings → Accounts →
Other users → Set up a kiosk) pointing at `run_client.bat`; on **Home** editions the steps above
are the way.

---

## 4. Daily use (staff)

| Task | Where |
|---|---|
| Sell time to a member | Members → TOP UP (or click the member's name on the station board) |
| Walk-in customer without an account | Stations → START → GUEST, pick a package |
| Add time while someone is playing | Stations → TOP UP on that row |
| Kick / end a session | Stations → END |
| Send a message to a PC | Stations → MSG |
| Restart / reboot / shut down a PC | Stations → ⋯ |
| Stop customers logging in on a PC | Stations → LOCK |
| See today's money | Dashboard, or Sales for the full list |

Members create their own accounts on any station (CREATE ACCOUNT) and then ask the counter
to add time; staff can also create accounts from the admin panel.

---

## 5. Troubleshooting

- **Station shows OFFLINE**: the client is not running or cannot reach the server. Check
  `client.json` → `server`, that the server is running, and the firewall on the counter PC.
- **"Station 'PC-01' exists but the key does not match"**: the client was reinstalled.
  Stations → ⋯ → RESET KEY, put the new key in `client.json`, or delete the station and let
  it re-register.
- **Kiosk says SERVER OFFLINE but a session was running**: the customer keeps their time; the
  timer counts down locally and the PC locks at zero. The session ends on the server when it
  reconnects or when staff end it.
- **Logs**: `server` console output; `client\client.log` on each PC.
