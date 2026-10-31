# MeGaA — Portfolio

Projects I designed and built with AI pair-programming (Claude Code): real desktop apps,
a client/server system, and front-end sites. Most of the Python is standard-library
only, with Qt Quick (PySide6 / QML) for the native, GPU-drawn UIs.

## Demo videos

Each video is the real app or site, recorded running (demo data, made-up names), then cut
with [HyperFrames](https://github.com/heygen-com/hyperframes). Click a preview to play the full video on the [portfolio page](https://1megaa1.github.io/MeGaA-portfolio/).

<table>
  <tr>
    <td width="50%"><b>Vortex</b>: gaming-cafe system<br>
      <a href="https://1megaa1.github.io/MeGaA-portfolio/#vortex"><img src="media/vortex-preview.gif" alt="Vortex demo"></a><br>
      <a href="https://1megaa1.github.io/MeGaA-portfolio/#vortex">▶ Watch (39 s)</a></td>
    <td width="50%"><b>MeGaA Clipper</b>: long video in, short clips out<br>
      <a href="https://1megaa1.github.io/MeGaA-portfolio/#clipper"><img src="media/clipper-preview.gif" alt="MeGaA Clipper demo"></a><br>
      <a href="https://1megaa1.github.io/MeGaA-portfolio/#clipper">▶ Watch (39 s)</a></td>
  </tr>
  <tr>
    <td width="50%"><b>GridPad</b>: a notepad laid out like a spreadsheet<br>
      <a href="https://1megaa1.github.io/MeGaA-portfolio/#gridpad"><img src="media/gridpad-preview.gif" alt="GridPad demo"></a><br>
      <a href="https://1megaa1.github.io/MeGaA-portfolio/#gridpad">▶ Watch (34 s)</a></td>
    <td width="50%"><b>Ozone Studios</b>: studio booking site<br>
      <a href="https://1megaa1.github.io/MeGaA-portfolio/#ozone"><img src="media/ozone-preview.gif" alt="Ozone Studios demo"></a><br>
      <a href="https://1megaa1.github.io/MeGaA-portfolio/#ozone">▶ Watch (34 s)</a></td>
  </tr>
  <tr>
    <td width="50%"><b>Voyago / Auriga</b>: travel and hotel templates<br>
      <a href="https://1megaa1.github.io/MeGaA-portfolio/#voyago-auriga"><img src="media/voyago-auriga-preview.gif" alt="Voyago and Auriga demo"></a><br>
      <a href="https://1megaa1.github.io/MeGaA-portfolio/#voyago-auriga">▶ Watch (35 s)</a></td>
    <td width="50%"></td>
  </tr>
</table>

## Desktop apps

| Project | What it is | Stack |
|---|---|---|
| [**Vortex**](apps/vortex/) | Gaming-cafe management system (like Gizmo / iCafeCloud). A counter server sells time to members, every gaming PC runs a locked kiosk that launches games and locks itself when time runs out, and staff manage it all from a web admin panel. Includes a shop, events, pricing groups, and a Windows Server deployment kit. | FastAPI, SQLite, WebSockets, PySide6/QML kiosk, pywebview, PyInstaller |
| [**MeGaA Clipper**](apps/megaa-clipper/) | Turns long videos into vertical short-form clips with word-by-word captions, hooks, zooms, razor edits and loudness-normalised renders. Local GPU transcription; optional Claude-picked viral moments. | Python stdlib engine, whisper.cpp, ffmpeg/NVENC, web UI + QML edition |
| [**GridPad**](apps/gridpad/) | A notepad laid out like a spreadsheet: free-text cells, sheets as tabs, keyboard-first, themes. Two engines: Qt Quick (GPU) and classic Qt Widgets. | PySide6, QML |

## Websites

| Project | What it is |
|---|---|
| [**Ozone Studios**](web/ozone-booking/) | Booking site and admin panel for a recording studio in Cairo: per-room calendars, time slots, beat store, WhatsApp hand-off. Firebase Auth + Firestore. [Live demo](https://1megaa1.github.io/MeGaA-portfolio/web/ozone-booking/index.html) |
| [**Voyago / Auriga**](web/tourism-templates/) | Two travel and hospitality templates. Live: [Voyago](https://1megaa1.github.io/MeGaA-portfolio/web/tourism-templates/1-voyago-trips.html) · [Auriga](https://1megaa1.github.io/MeGaA-portfolio/web/tourism-templates/2-auriga-suites.html) |

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
