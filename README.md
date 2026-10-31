# MeGaA — Portfolio

Projects I designed and built with AI pair-programming (Claude Code): real desktop apps,
a client/server system, and front-end sites. Most of the Python is standard-library
only, with Qt Quick (PySide6 / QML) for the native, GPU-drawn UIs.

## Desktop apps

| Project | What it is | Stack |
|---|---|---|
| [**Vortex**](apps/vortex/) | Gaming-cafe management system (like Gizmo / iCafeCloud). A counter server sells time to members, every gaming PC runs a locked kiosk that launches games and locks itself when time runs out, and staff manage it all from a web admin panel. Includes a shop, events, pricing groups, and a Windows Server deployment kit. | FastAPI, SQLite, WebSockets, PySide6/QML kiosk, pywebview, PyInstaller |
| [**MeGaA Clipper**](apps/megaa-clipper/) | Turns long videos into vertical short-form clips with word-by-word captions, hooks, zooms, razor edits and loudness-normalised renders. Local GPU transcription; optional Claude-picked viral moments. | Python stdlib engine, whisper.cpp, ffmpeg/NVENC, web UI + QML edition |
| [**MeGaADesk**](apps/megaadesk/) | Self-hosted remote desktop (like AnyDesk). End-to-end encrypted with a session password; a tiny relay on a VPS only forwards ciphertext. | Pure stdlib host + relay, PBKDF2 + HMAC-SHA256, QML viewer |
| [**GridPad**](apps/gridpad/) | A notepad laid out like a spreadsheet: free-text cells, sheets as tabs, keyboard-first, themes. Two engines: Qt Quick (GPU) and classic Qt Widgets. | PySide6, QML |

## Websites

| Project | What it is |
|---|---|
| [**Ozone Studios**](web/ozone-booking/) | Booking site and admin panel for a recording studio in Cairo: per-room calendars, time slots, beat store, WhatsApp hand-off. Firebase Auth + Firestore. |
| [**SEVENTYNINE**](web/aura-perfume/) | Monochrome luxury fragrance landing page. |
| [**Voyago / Auriga**](web/tourism-templates/) | Two travel and hospitality templates. |

## Screenshots

**Vortex**: the native kiosk client

![Vortex home](apps/vortex/docs/native_home.png)

![Vortex games](apps/vortex/docs/native_games.png)

**GridPad**: themes

![GridPad themes](apps/gridpad/tools/shots/themes.png)

## Running the projects

Each folder has its own README with setup steps. Quick versions:

```bash
# Vortex: server + admin panel at http://localhost:8787/admin/ (login admin / admin)
cd apps/vortex/server && pip install -r requirements.txt && python run_server.py

# MeGaADesk: host, relay and viewer
cd apps/megaadesk && python megaadesk.py --help

# GridPad
cd apps/gridpad && pip install -r requirements.txt && python gridpad_qml.py

# Websites: open the .html files, or
cd web/ozone-booking && python -m http.server 5174
```

## How I work

I plan each project with a five-step problem-solving lifecycle (analyze, plan, execute,
test, update), then build it iteratively with an AI coding agent: I make the product and
design decisions, the agent writes code, and I verify every feature with automated tests
and in the running app. Vortex's [PLAN.md](apps/vortex/docs/PLAN.md) and
[PROGRESS.md](apps/vortex/docs/PROGRESS.md) show that process end to end.
