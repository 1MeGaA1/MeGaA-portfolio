# Vortex

Gaming-cafe management software: a server for the counter PC and a locked kiosk client for
every gaming PC. Members buy time, log in on any station, launch games from inside the
kiosk, and the PC locks itself when the time is up. Staff run everything from a web admin
panel. Same idea as Gizmo or iCafeCloud, built in Python with the Vortex design.

```
Vortex/
├── server/      FastAPI + SQLite + WebSockets. Members, stations, sessions, pricing, sales.
│   ├── admin/   the staff panel (served at /admin/)
│   └── tests/   22 tests: time math, expiry, top-ups, warnings, WebSocket flows
├── client/      pywebview (WebView2) kiosk: lockdown, server link, game launcher
│   ├── ui/      the kiosk page (also served by the server at /kiosk/ for demos)
│   └── tools/   kiosk_setup.py (shell replacement), vendor_assets.py, demo_station
├── client-native/ PySide6 + QML kiosk (the one in use); reuses client/vortex_client
└── docs/        PLAN.md (5-step lifecycle), PROTOCOL.md, INSTALL.md, DEPLOY_WINDOWS_SERVER.md, PROGRESS.md
```

## Quick start (one PC, to see it working)

```
cd server  && pip install -r requirements.txt && run_server.bat
```
Open http://localhost:8787/admin/ → login **admin / admin** → *Members* → NEW MEMBER → sell time.

```
cd client  && pip install -r requirements.txt && python run_client.py
```
On the first run set `"kiosk": false, "fullscreen": false` in `client.json` to get a normal
window. Log in with the member you created. Top up from the admin panel and watch the timer
grow; press END on the station and watch the kiosk lock. Ctrl+Shift+Q + PIN `1234` exits.

No client PC handy? The kiosk page runs in any browser: http://localhost:8787/kiosk/index.html?station=DEMO

## Tests

```
cd server && python -m unittest discover -s tests -t . -v
cd client && python -m unittest discover -s tests -t . -v
```

## Deploying to a cafe

See `docs/DEPLOY_WINDOWS_SERVER.md` for the packaged server on Windows Server (no Python needed,
starts at boot) and `docs/INSTALL.md`: server on the counter PC, `client.json` per station, `catalog.json`
for the games installed on each PC, and `tools/kiosk_setup.py` to replace the Windows shell.

## Status

Version 1 covers the money path: stations, members, prepaid time wallets, server-enforced
sessions, top-ups, guest sessions, pricing, sales history, kiosk lock/login/timer/launch,
staff commands (message, lock, restart, reboot, shutdown), PIN exit.
Version 2 candidates: shop & food orders, tournaments/events, friends, points shop, QR login,
server-managed game library, cloud backup. The kiosk page already has the screens for most
of these; they are visual only until the server side exists.
