# Vortex native client

A **fully native** kiosk client — PySide6 + Qt Quick (QML), GPU-rendered, **no web engine
and no HTML at all**. This is the alternative to `../client` (which renders the same UI as a
web page in WebView2, the way Gizmo and iCafe do). Both talk to the same Vortex server with
the same protocol; they reuse the same backend (`vortex_client`: server link, game launcher,
keyboard lockdown, config).

```
client-native/
├── run_native.py / run_native.bat     start it (bat = watchdog that relaunches on crash)
├── client.json                        per-station config (same shape as the web client)
├── catalog.json                       optional; else reuses ../client/catalog.json
├── fonts/                             Rajdhani, Chakra Petch, JetBrains Mono (TTF)
├── qml/                               the native UI (Theme, Login, Hub, components)
├── vortex_native/                     app.py (Qt entry) + controller.py (backend bridge)
└── tests/integration_smoke.py         drives the controller against a live server
```

## Run it

```
cd client-native
pip install -r requirements.txt
python run_native.py
```

First run writes `client.json`. For testing on your own PC set `"kiosk": false` and
`"fullscreen": false` so it's a normal, closable window. On cafe PCs set both `true`:
frameless, fullscreen, always-on-top, keyboard locked, exit only via Ctrl+Shift+Q + staff PIN.

## Build a standalone .exe

```
pip install pyinstaller
build_native.bat        ->  dist\VortexClientNative\   (copy to each PC, edit client.json)
```

## What it does (v1)

Splash → login / create account → hub (games + apps grid, live session timer, account panel
with peripheral status) → locks when the session ends or time runs out. Staff commands
(message, lock, restart, reboot, shutdown, top-up) work exactly as with the web client,
because the server and the backend are identical.

Verified: QML loads with no warnings; the controller drives login → session → staff top-up →
staff end → restart against a live server (`tests/integration_smoke.py`), and the real app
process connects and honours a staff restart (exit code 3 for the watchdog).
