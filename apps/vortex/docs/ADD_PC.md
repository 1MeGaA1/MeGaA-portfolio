# Adding a gaming PC to Vortex

Works for a normal PC with its own Windows. (Diskless / CCBoot PCs need the station-key change
first; see PROGRESS.md 2026-09-13.)

## 1. Copy the client
1. Copy `Vortex\VortexClientNative-0.1.0.zip` to the PC (USB stick or network share).
2. Unzip it to `C:\Vortex\VortexClientNative\` (any path without spaces is fine).

## 2. Edit `client.json` (Notepad)
```json
"server": "ws://192.168.1.104:8787",   <- the Vortex server on the cafe LAN
"station_name": "PC-01",               <- a different name on every PC
"station_key": "",                     <- leave empty; the server fills it in
"kiosk": false,                        <- false while testing, true for customers
"fullscreen": false                    <- same
```
From outside the cafe network (over Tailscale) use `ws://<tailscale-ip>:8787` instead.

## 3. Start it
Double-click `run_native.bat`. Within a few seconds the PC appears under **STATIONS** in the
admin panel (`http://192.168.1.104:8787/admin/`) as FREE. Log in on the kiosk with a member
account, or start a GUEST session for it from the admin panel.

## 4. Games and apps on this PC
`_internal\catalog.json` says what every tile launches. Each entry needs the real path or
Steam/Epic/Riot link on this PC and the process name Vortex should watch:
```json
"Valorant": {"exe": "C:/Riot Games/Riot Client/RiotClientServices.exe",
             "args": ["--launch-product=valorant", "--launch-patchline=live"],
             "process": "VALORANT-Win64-Shipping.exe", "cat": "fps"}
```
Only titles that have icon art in the client are shown on the Games / Apps pages.

## 5. Lock it down for customers (after the test works)
1. Create a standard (non-admin) Windows user for customers, e.g. `player`, set it to log in
   automatically (`Win+R` -> `netplwiz`), keep your own admin account for maintenance.
2. In `client.json` set `"kiosk": true, "fullscreen": true`.
3. Logged in as `player`, put a shortcut to `run_native.bat` in the Startup folder
   (`Win+R` -> `shell:startup`) so Vortex opens at login.
4. Staff leave the kiosk with **Ctrl+Shift+Q** + the exit PIN (Settings in the admin panel).

## Troubleshooting
| Symptom | Check |
|---|---|
| Kiosk shows SERVER OFFLINE | `ping 192.168.1.104` from the PC; server running (`check_server.bat` on the server); `server` value starts with `ws://` |
| "exists but the key does not match" | Client was reinstalled. Admin panel -> Stations -> that PC -> RESET KEY, or delete the station and start the client again |
| Station shows but games do not start | `catalog.json` path/process wrong for this PC; see `client-native.log` next to the exe |
