# Progress log

## 2026-09-07

**M1 · Server core — done.** `server/vortex_server/`: SQLite schema, session engine (prepaid
wallet model), staff auth, REST API, station + admin WebSockets. 22 tests pass
(`python -m unittest discover -s tests -t .` inside `server/`).

**M2 · Admin panel — in progress.** `server/admin/` rebuilt from the prototype's exact CSS,
now driven by `/api` and `/ws/admin`. Pages: Dashboard, Stations, Members, Pricing, Sales,
Settings. The prototype's Game Library and Offers pages are v2 and were left out.
The lucide icon CDN was replaced with inline SVG so the panel works with no internet.

**M2 · Admin panel — done.** Verified in the browser against the live server: staff login,
dashboard, station board with live countdown, guest session start with package picker,
member creation + top-up, pricing, sales, settings. Zero console errors.
Fix along the way: the station board only re-renders when data changes (not on every
5-second push), so buttons never vanish under the cursor.

**M3/M4 · Kiosk client — in progress.** `client/`: pywebview host + prototype page.

**M3 · Kiosk page wired — done.** `client/ui/index.html` (patched copy of the prototype) +
`client/ui/vortex-bridge.js`. Verified in a browser against the live server (the server
also serves the page at `/kiosk/` for demos): real login, real countdown from the member's
wallet, staff top-up appears instantly with a toast, launch overlay, staff END locks the PC
with the reason shown, Ctrl+Shift+Q → PIN dialog (wrong PIN rejected, right PIN exits).
Removed: demo credentials, the test exit button, the fake QR auto-login.

**M4 · Kiosk host — in progress.** `client/vortex_client/`: pywebview window, server link
(reconnecting WebSocket), launcher (spawn/track/kill by pid or process name), lockdown
(low-level keyboard hook + foreground guard), peripherals, bridge. `tools/kiosk_setup.py`
sets shell replacement / task manager policy / autostart per user. `docs/INSTALL.md` written.

**M4 · Kiosk host — done (windowed test).** Integration smoke test with the real pywebview
client on this PC (`kiosk: false`): came online in 2 s, received a staff message, exited with
code 3 on the staff RESTART command (the watchdog .bat restarts it). The keyboard hook and
foreground guard were deliberately not exercised on the dev machine; they run only with
`kiosk: true` on cafe PCs.

**M5 · Packaging & install — done.** `docs/INSTALL.md`, `client/tools/kiosk_setup.py`
(per-user shell replacement / Task Manager policy / autostart, all reversible),
`build_client.bat` + `build_server.bat` (PyInstaller). Fonts and 24 brand icons vendored
locally by `client/tools/vendor_assets.py`, so nothing depends on the internet at runtime.
Client unit tests: 6 green. Server: 22 green.

**Next (v2 ideas):** shop/orders, events, QR login, server-managed game catalog, cloud backup,
per-station idle timeout, receipts/reports export, staff roles.
Packaged client built with `build_client.bat` → `client/dist/VortexClient/` (45 MB, no Python
needed on the gaming PC) and smoke-tested the same way as the script version: online in 2 s,
message + restart commands OK.

## 2026-09-07 (later) — kiosk "File not found" fix

**Symptom:** the kiosk window showed WebView2's "File not found / ERR_FILE_NOT_FOUND" page.
**Root cause:** the client loaded `file:///…/index.html?kiosk=1`. WebView2 sets
`Source = Uri(url)`, and .NET's Uri treats the `?kiosk=1` query as part of the *local file
path*, so no such file exists. The earlier smoke test only checked the server WebSocket link,
never that the page itself rendered, so it slipped through.
**Fix:**
- Client loads a plain `file://` URL with no query string (`vortex_client/app.py`).
- Kiosk vs browser mode is detected from `window.chrome.webview` / `window.pywebview`
  (`ui/vortex-bridge.js`), with `?kiosk=0` to force browser mode and an 8 s fallback.
- Client uses a dedicated persistent WebView2 profile (`client/webview2-profile/`) via
  pywebview `storage_path`, so instances never collide on the shared global profile
  (that collision was what made repeated test runs hang with "Main window failed to start").
- `exit()` now force-terminates after 3 s if `window.destroy()` is a no-op, so the watchdog
  can always restart the kiosk.
- `_on_page_loaded` logs the page title/bridge so a bad load is visible in `client.log`.
**Verified:** query-string URL reproduced (no bridge = error page); bridge mode-detection and
kiosk→pywebview.api routing covered by `client/tests/bridge_kiosk_test.js` (14/14, run from
`test_bridge.py`); restart→exit code 3 confirmed. Live foreground rendering can't be checked
in this occluded session, but the user's screenshot already proved the render path works —
only the path was wrong.

**Deeper root cause found + fixed (the real one):** `push()` called pywebview's *synchronous*
`evaluate_js` directly on the ServerLink receive thread. The `welcome` handler's push blocked
that thread (WebView2 is slow/occluded), so the receive loop never read another frame — no
`session_update`, no `command`, and critically no `session_ended` (the lock signal). Fix:
`push()` now enqueues; a dedicated `vortex-pusher` thread runs the blocking `evaluate_js`, so
the link thread never stalls. Also `link.stop()` is safe when called from its own loop thread,
and `exit()` arms an `os._exit` fallback first so a restart always terminates for the watchdog.
**Verified end-to-end on the packaged exe:** online in 3 s, staff message received, staff
`restart` received and logged, clean exit code 3 with `window closed`. Also confirmed live:
member session start → `in_session` → staff end. Server 22 tests + client 7 tests green.
Test database deleted so the next `run_server.bat` seeds a clean DB.

## 2026-09-07 (later) — "launcher won't close" fix

**Symptom:** closing the launcher window did nothing — it wouldn't close.
**Cause:** `_on_closing` returned `self._exiting`. pywebview CANCELS a close when the handler
returns False, and `_exiting` is False when the user clicks X, so the close was always
cancelled — in windowed mode too, not just kiosk mode.
**Fix (`vortex_client/app.py`):** block the close only in real kiosk mode (`kiosk` and not
`debug`); in windowed/dev mode allow it and exit with code 0 so the watchdog doesn't relaunch.
A close after our own exit() (admin PIN / restart) is always allowed.
**Verified:** 4 unit tests in `test_client.py` (windowed allows + code 0, kiosk blocks,
kiosk-debug allows, post-admin-exit allows) and a real WM_CLOSE test — the window now closes
and the process exits with code 0. Client suite: 11 tests green.

## 2026-09-07 (later) — native (non-web) client

User wanted a client "like iCafe and Gizmo" — a truly native app, not a web page. Built a
second client, `client-native/`, in **PySide6 + Qt Quick (QML)** — GPU-rendered native UI,
no WebView2, no HTML. Reuses the whole `vortex_client` backend (link, launcher, lockdown,
config, peripherals) unchanged via a `Controller(QObject)` that maps server events to Qt
signals (delivered to QML on the GUI thread) and runs blocking requests on worker threads.
Screens: Splash, Login/Register, Hub (games+apps grid, live timer, account+peripherals),
admin-PIN exit overlay, toast. Fonts: TTFs (Rajdhani/Chakra Petch/JetBrains Mono) loaded via
QFontDatabase. Verified: QML loads with zero warnings offscreen; controller integration test
(login→session→topup→end→restart) passes against the live server; the real app process
connects and honours a staff restart (exit 3); rendered PNGs of Login + Hub confirm the look.
Build: `build_native.bat` (PyInstaller). The web client stays as the alternative.

## 2026-09-07 (later) — accounts + new splash
- `server/tools/provision.py`: creates/updates a staff account (owner) + a demo member with
  time; sets the kiosk exit PIN. Ran it: admin panel `owner`/`vortex123`, exit PIN **3024**;
  demo member `demo@vortex.gg`/`demo123` with 5h. Built-in `admin`/`admin` still works.
- Native splash redesigned (user asked for "bolder animated"): glowing counter-rotating
  cyan/magenta rings + pulsing core, live status steps (Connecting → Authenticating →
  Loading library → Ready) tied to the real link state (amber "SERVER OFFLINE · RETRYING"
  when it can't reach the server), animated progress bar. Loads zero-warning; PNG in docs.

## 2026-09-07 (later) — "native login/PIN not working" = wrong server address
Root cause: a client.json I'd written pointed the native launcher at the placeholder
`ws://192.168.1.10:8787` instead of the user's local server, so it never connected — and
login + exit PIN both need a live connection, so both silently failed. Fixed client.json to
`ws://127.0.0.1:8787` (code default was already localhost). Also: `owner`/`vortex123` is a
STAFF (admin-panel) account and is correctly rejected on the launcher, which authenticates
MEMBERS — use `demo@vortex.gg`/`demo123` there. Added a connection indicator to the native
login screen (green CONNECTED / amber SERVER OFFLINE) and a local fallback exit PIN in
client.json. Live-verified on the native client: connects, demo login (5h), owner rejected,
PIN 0000 rejected, PIN 3024 accepted.

## 2026-09-07 (later) — full web parity in the native client
Ported every web-client screen/feature into the native QML client:
- Full hub top nav: Home, Games, Apps, Shop, Games Currency, Events + Friends menu, Settings
  menu (change username / change password / preferences), user menu (log out), session timer
  chip, status bar.
- Home: featured event banner, Recently Used, Launchers, account sidebar (session bar, points
  + recharge, peripheral status, contact admin).
- Games/Apps: category chips (from catalog `cat`) + live search, launch tiles.
- Shop: best sellers + category filters + buy → charged-to-session toast.
- Games Currency: game selector + balance + top-up packs.
- Events: tournament cards (live/upcoming) with filters + join/register.
- Overlays: message friend, add friend, change username (updates avatar/name live), change
  password, preferences (toggles). All match the web's local/toast behaviour.
New QML: Content (data singleton), FilterChips, ShopCard, CurrencyCard, EventCard,
ModalOverlay, AccountCard, HomePage, GamesPage (games+apps), ShopPage, CurrencyPage,
EventsPage; Hub rewritten. Native `catalog.json` adds `cat` per entry for the filters.
Loads zero-warning; every page rendered to docs/native_*.png. Web client untouched.

## 2026-09-07 (later) — native theme beautified
The native client looked flat next to the web. Ran a 4-agent design workflow (ultracode) that
produced: richer Theme.qml (per-game cover gradients coverA/coverB, glow() helper, glass tokens,
neon-dim/faint colours), a gradient+glow GameTile (brand gradient covers, watermark initial,
clipped corner, bottom scrim, hover neon halo), HubBackground.qml (grid + drifting particles +
faint vortex glows), a glowing VxButton (layered neon halo + additive MultiEffect bloom + gradient
face) and a glowing SectionLabel. Integrated + HubBackground behind the hub. Loads zero-warning;
re-rendered — game tiles now show real brand-colour covers, buttons bloom, background has depth.

## 2026-09-07 (later) — page transitions + friends menu redesign
- Nav pages now animate: replaced the StackLayout with a PageSlot container — each page parks
  left/right of the current one and slides to centre + fades in when selected (direction-aware,
  ~280ms). Confirmed via a mid-transition grab.
- Friends menu rebuilt to match the original web design: header with "N online · M offline" +
  "+ ADD", ONLINE/OFFLINE sections, coloured avatar circles (magenta/cyan/green/amber), full
  status lines ("● Playing Valorant" etc.), MESSAGE buttons; offline rows dimmed. Content.friends
  updated to the web's exact set.

## 2026-09-08 — native tiles matched to web (brand logos + subtitles)
User: web UI looked better. Compared them — the web game/app cards show real brand LOGOS and a
genre·platform subtitle; native showed a plain letter. Fixed: fetched 20 simpleicons brand SVGs
(white) to client-native/qml/icons/; Theme.iconFor(name) maps names→icon; GameTile shows the
logo (letter fallback for the ~5 games with no public logo) + a subtitle line; controller
games()/apps() now return `sub` = "Genre · Platform" (platform derived from the launch/exe).
Tiles enlarged. Loads zero-warning; Games/Apps now show CS/Valorant/Fortnite/League/Dota/
Rockstar/EA logos and Chrome/Discord/Spotify/Steam/Epic/etc. — matches/beats the web.

## 2026-09-08 — native exe packaging fixed
Discovered the packaged native exe was crashing (0xC0000409): PyInstaller doesn't scan .qml
files, so the QtQuick QML modules (QtQuick/Controls.Basic/Layouts/Shapes) weren't bundled →
crash on QML load. Also the shared vortex_client backend wasn't bundled (ModuleNotFoundError).
Fix: build with `--collect-all PySide6` (bundles all QML modules) + `--paths ..\client`
(bundles vortex_client), then `tools/prune_dist.py` strips unused Qt (WebEngine/Quick3D/Pdf/
docs) → ~335 MB. Logos converted SVG→PNG (Qt loads PNG natively, no qsvg plugin). MultiEffect
removed from VxButton/HubBackground (the layered glow already carries the look). Verified: exe
online in 1s. build_native.bat updated with the full recipe. (Source `python run_native.py`
was always fine — this only affected the packaged exe.)

## 2026-09-08 — counter (front-desk) panel + reconnect fix
User's native client was flooding the server with reconnects, all rejected "This station is
disabled." Cause: PC-01 was soft-disabled earlier (delete_station keeps stations that have
session history and just sets enabled=0). Re-enabled it via the API. Also fixed a real bug in
the shared backend `client/vortex_client/link.py`: on a *rejection* the reconnect loop did
`continue`, which skips the `sleep(backoff)` and hammered the server every ~2 ms. Rewrote the
welcome/reject branch as if/else so a rejection falls through to the 10 s→15 s backoff. 11
client tests green. (This is the shared backend the native client reuses, not the web UI.)

Then built the requested **Counter panel** — a staff front-desk screen. New self-contained page
`server/counter/index.html` served at `/counter/` (mounted in main.py next to /admin; pulls the
shared brand fonts + logo.mp4 from the /admin mount; shares the `vortex_token` login). It reuses
the existing REST + `/ws/admin` feed — no new server endpoints. Features: live station grid with
real-time status + client-side countdown, summary bar (online / in-session / free / today's
revenue), Start Session (member search or guest package/custom minutes), Add Time (quick
+15/+30/+60 + custom, via /session/topup), End Session (confirm), Member wallet top-up drawer,
Lock/Unlock + status filters, toasts, WebSocket live updates with auto-reconnect. Session is the
DOMINANT card state (a PC that drops mid-session still shows its running timer + an "⚠ PC OFFLINE
· time still counting" warning + END). Verified live in the browser end-to-end against the
running server: staff login, member search, guest 30-min start → card flip, +30 add-time (timer
+ today-revenue both updated), member 1 h wallet top-up (flowed into the member's active session
total), end-session, filters — zero console errors. 22 server tests green. run_server.py banner
now prints the /counter/ URL.

## 2026-09-08 (later) — counter panel removed; live activity in admin
User decided against a separate counter panel ("remove the counter panel i want only the admin
panel"). Deleted `server/counter/`, removed the /counter mount (main.py) and banner line
(run_server.py). Kept the useful part — **live "what is each PC doing right now"** — but only in
the admin panel. New shared backend `client/vortex_client/activity.py`: an ActivityReporter thread
reads the Windows foreground window (process + title via ctypes, no new dependency) plus the
launcher's running() list every 3s and sends a `{"type":"activity"}` message on change; it skips
our own window (so an idle customer shows "on the Vortex menu") and only reports during a session.
Wired into the native client's controller. Server stores it per-station (engine._activity, cleared
on session end / offline), exposes it in station_view, and rebroadcasts to admins; protocol.py
handles the `activity` message. Admin `admin.js` shows a green "▶ <app>" + "open: <games>" line
under the user in both the dashboard Active-Sessions table and the Stations page. Only the native
client reports (web client untouched). Verified end-to-end on a throwaway :8788 server with a fake
station (dashboard + stations both show ▶ Chrome / open: Discord, Steam). 22 server + 11 client
tests green.

## 2026-09-09 — real shop (pictures + EGP prices), icon polish, hover clip fix
Native client polish requested by the user:
- **Custom icons**: user supplied 20 full-colour neon-badge logos; downscaled to 256px into
  `client-native/qml/icons/` (Qt QImage, no new deps). Tiles now show the icon FULL-BLEED as the
  cover (GameTile) and are SQUARE (frame fits the icon). Only titles with real art are shown —
  the icons-only filter in GamesPage/HomePage hides letter-fallback titles AND anything still on an
  old white simpleicon (Counter-Strike, Red Dead, Firefox, Netflix, Twitch, VLC, Telegram, OBS).
- **Home**: event banner buttons side-by-side + banner taller (prize no longer overflows);
  Recently-Used and Launchers use fixed 200px square tiles (launchers no longer balloon);
  account card shows "Xh Ym used · Xh Ym left".
- **Hover clip fix**: a hovered tile lifts + glows past its bounds and the ScrollView clips at its
  edge, so flush tiles got cut. Padding is now INSIDE the ScrollView (Home content x:18; Games grid
  wrapped in a padded Item). Verified with scratchpad/grab_hover.py (QTest.mouseMove offscreen).
- **Real shop**: products moved out of QML into `client-native/shop.json` (name/cat/price/image/
  best — editable). Controller exposes `shop()` and a `currency` property (from the server's
  welcome config, fallback EGP). ShopCard shows a real product picture + "EGP <price>" + BUY;
  ShopPage header says PAY AT THE COUNTER and BUY confirms "… — please pay at the counter" (no
  ordering backend by user's choice). Pictures: `tools/make_shop_images.py` renders Twemoji SVGs
  (CC-BY 4.0, see qml/shop/ATTRIBUTION.txt) for foods/natural drinks and draws brand-coloured
  cans/bottle/bags/bar with QPainter for Coca-Cola, Pepsi, Sprite, Red Bull, Monster, Water,
  Doritos, Lay's, Protein Bar (24 PNGs, 256px). build_native.bat bundles shop.json.
  Verified: shop page renders all pictures + EGP prices, 0 QML warnings.
- Admin: `/ws/admin` 403 after a server restart (stale in-memory token) now drops cleanly to the
  login screen instead of looping (admin.js connectWS revalidates via /api/me when the socket
  never opened).

## 2026-09-09 (later) — real shop orders + admin-managed products/pictures/events
User: "the shop is just a view… I want to add this to the admin panel: adjust pricing, add items and
pictures; and control the events (remove all from the client, enable, make an offer, choose Home/any
page)". Built against a written contract, `docs/SHOP_EVENTS_SPEC.md`, by three parallel agents
(server / admin / client, disjoint file ownership) + two adversarial reviewers, then integrated.
- **Server**: new tables `products`, `orders`, `events` (schema additive, safe for existing DBs);
  `Settings.media_dir` (data/media) mounted at `/media`; 24 seed products (prices in MINOR units,
  2500 = 25.00) with pictures copied from `vortex_server/seed_media/products/` on first seed + 8 seed
  events (VORTEX CUP featured on Home, one "offer"); seeding is now flagged in `settings`
  (`seeded_products`/`seeded_events`) so deleting everything does not resurrect the demo set.
  REST: /products CRUD + base64 picture upload/delete (`{filename,data}`, png/jpg/webp sniffed,
  ≤4 MB), /orders (pending queue, done → `transactions` row kind `shop` so revenue counts, cancel),
  /events CRUD + disable-all/enable-all. The old audit-log route moved from `/events` to `/audit`.
  Station socket: welcome carries `shop`/`events`/`media_base`; `{"type":"order"}` needs an active
  session and replies `order_result`; `order_update` on done/cancel; `shop`/`events` pushed to all
  stations on any change. Admin socket also sends the pending `orders` queue live. New items without
  a `sort` append to the end. Tests: 32 (22 old + 10 new) green — one WebSocket-timing test is
  occasionally flaky (seen once in ~6 runs).
- **Admin panel**: SHOP page (live PENDING ORDERS queue with DONE/CANCEL + nav badge, PRODUCTS table
  with thumbnails/EDIT/PICTURE/DELETE, + ADD PRODUCT, picture upload resized to 512px in the browser,
  ORDER HISTORY) and EVENTS page (table with ENABLED / HOME / EVENTS toggles, EDIT/DELETE, + ADD
  EVENT incl. kind event/offer + categories, ENABLE ALL / DISABLE ALL). Polish: thumbnail
  cache-buster, toggle responses merge only the toggled flag.
- **Native client**: shop and events now come from the server (welcome + live pushes); product
  pictures load from `serverHttp + image_url`; BUY opens an ORDER dialog (qty 1–10, total) →
  order sent to the counter → toast, and "Order delivered / cancelled" toasts from staff actions;
  Events page uses server events (offer = amber CLAIM card; "NO EVENTS RIGHT NOW" when all are
  disabled); Home banner = the event flagged "show on Home", hidden entirely when none; added a
  WEEKEND chip. `shop.json` and `qml/shop/` removed (server owns them now).
- **Verified**: `scratchpad/e2e_shop.py` against a throwaway :8788 server → 38/38 (seed, welcome,
  order refused without session, order → queue → done → transaction + station update, price/event
  pushes, upload/serve/reject/remove, CRUD); offscreen client renders 0 QML warnings incl. the
  no-events state; admin Shop/Events pages driven in the browser. NOTE: the live server must be
  restarted to load this (it will seed products/events/media once); exes not rebuilt.

## 2026-09-10 — theme toning + UI icons
User: some colours "so bright, like JOIN NOW"; wanted an icon for friends etc. All filled accent
buttons share `qml/VxButton.qml`, so one change fixed JOIN NOW / ORDER / LOGIN / CLAIM / REGISTER:
resting glow 0.45→0.22 and hover 0.55→0.36, glow-layer alphas roughly halved, face gradient now
lighter(1.03)→darker(1.22) at rest (was 1.12→1.12) with a gentler hover, inner highlight 0.28→0.14.
Home banner border at 60% of the accent. ShopCard BUY hover is a cyan tint instead of a solid fill.
Icons: `qml/icons/ui/{friends,settings,chat}.png` drawn with QPainter (64px) in white + `_cyan` +
`_muted` variants (Image cannot be tinted without QtQuick.Effects, which the frozen build avoids);
Hub's `TopButton` gained an `icon` property (muted when idle, cyan when active) used by FRIENDS and
SETTINGS; the friends-list MESSAGE button carries the chat icon. Verified by offscreen renders
(Home with banner, Events, friends menu open): 0 QML warnings.

## 2026-09-12 — server package for Windows Server 2022
User installed Windows Server 2022 as the cafe server and wants Vortex ready on it. Made the
server a self-contained folder plus a deploy kit, and tested the exact package:
- `run_server.py`: logs to `data\server.log` (rotating, 5 MB x3) as well as the console, so a
  boot-started server can be diagnosed; "port already in use" exits with code 2 and a plain
  message instead of a traceback (the keep-alive loop stops instead of fighting for the port).
- `build_server.bat` fixed: it had never produced a build. `--collect-all fastapi/starlette/pydantic`
  pulled fastapi.cli -> typer -> rich -> IPython -> matplotlib/numpy/scipy/torch (gigabytes);
  now only uvicorn/websockets/anyio are collected and those chains are excluded. The kit in
  `server/deploy/` is copied next to the exe.
- Deploy kit (`server/deploy/`, shipped in `dist\VortexServer\`): `open_firewall.bat` (TCP 8787),
  `install_autostart.bat` (Task Scheduler task "Vortex Server", at boot as SYSTEM, running
  `serve_forever.bat` which restarts the exe after a crash), `check_server.bat` (health + LAN
  address + opens the panel), `start/stop/uninstall`, `README-DEPLOY.txt`.
- `tools/smoke_test.py`: starts the exe (or source) on :8799 with a temp data dir and walks the
  money path — login, seed data + pictures, station hello/auto-register, refused order without a
  session, guest session, order -> queue -> done -> transaction + station update, end -> lock,
  exit PIN, log/db/settings files. 35 checks.
- `docs/DEPLOY_WINDOWS_SERVER.md`: step-by-step for the server (build, copy, firewall, autostart,
  static IP, pointing the gaming PCs, test plan, backup/update, troubleshooting).
- Verified the kit for real (dev PC, temp data dir): NOT RUNNING / RUNNING + LAN address from
  `check_server.bat`; a second `serve_forever.bat` exits 2 and stops; killing the exe brings it
  back in 5 s; `data\server.log` written. Bugs found on the way: (1) uvicorn swallows the bind
  error and exits 1, so `run_server.py` now checks the port itself and exits 2; (2) `timeout`
  aborts when stdin is redirected → `ping -n N` sleeps; (3) cmd may not search the current
  folder for programs (`NoDefaultCurrentDirectoryInExePath`) → both keep-alive scripts use
  `"%~dp0<exe>"`. The very first build attempt (`--collect-all fastapi`) also kept running after
  a taskkill and wiped `dist\` mid-test — build one thing at a time.
- Native client rebuilt (`dist\VortexClientNative`, 348 MB) with the shop/events/theme work;
  packaged client verified against the packaged server (connects, auto-registers, online in the
  panel). Dist now ships a template `client.json` (kiosk off) + `README-CLIENT.txt`;
  `run_native_dist.bat` uses the full exe path and a ping sleep. Zips for copying:
  `Vortex\VortexServer-0.1.0.zip` (38 MB), `Vortex\VortexClientNative-0.1.0.zip`.

## 2026-09-13 — deployed to the cafe server (Windows Server 2022, over Tailscale)
The physical server (<server-name>, Tailscale <tailscale-ip>, LAN 192.168.1.104/DHCP) came up
with OpenSSH; key `~/.ssh/cafe_server` logs in as Administrator. Uploaded `VortexServer-0.1.0.zip`
(md5 verified), unpacked to `C:\Vortex\VortexServer\`, ran `open_firewall.bat` and
`install_autostart.bat` remotely (task "Vortex Server", SYSTEM, at boot, Running). Set the time
zone Pacific → Egypt Standard Time and restarted the task. Verified from the dev PC through
Tailscale: /health, admin login in the browser, the packaged native client connected as
DEV-PC-TAILSCALE and showed FREE/online on the Stations page, and `smoke_test.py --url` (new live
mode) passed 31/31 on the real server. Then wiped `dataortex.db*` and restarted so the cafe
starts from a clean seed (0 stations, 0 members, 24 products, 8 events; admin/admin, PIN 1234 —
still to be changed by the user). Left as advice: reserve/static the LAN IP; Tailscale traffic
is also allowed by the firewall rule (profile=any).

## 2026-09-13 (later) — status page + first real client test
- User tested the packaged native client on their own PC over Tailscale against the cafe server
  (station MY-PC, member mega/302481 with 2 h created for the test): connected, logged in, in
  session. `docs/ADD_PC.md` written (steps to add a normal PC; diskless still needs the key change).
- User asked "how do I know the server is working?": added public `GET /api/status` (six checks:
  database, pictures folder, disk space, session engine tick age, stations, admin panel; plus
  hostname, LAN addresses, local time/tz, uptime, station list — no secrets) and
  `admin/status.html` at `/status` (big green ALL SYSTEMS OK / red PROBLEM, refreshes every 5 s,
  red SERVER NOT RESPONDING when unreachable). Engine stamps `_last_tick`. Test added (33 tests).
  Rebuilt, smoke-tested (35/35), redeployed to the cafe server over SSH (data kept), verified over
  Tailscale. check_server.bat + README-DEPLOY mention the page.
- Status page now lists every fixed hard disk (`_disks()` in main.py: GetLogicalDrives +
  DRIVE_FIXED, label, total/used/free GB, used %, `low` = <5 GB or <5 %, `data` flag for the
  drive holding vortex.db) with a usage bar per drive; the Disk space check goes red on any low
  drive. Redeployed to the cafe server (C: 975 GB, D: 1 TB "New Volume"). On the server: Edge app
  window with the status page in the "vortex server" session, re-opened at logon by task
  "Vortex Status Screen"; desktop shortcuts Vortex Status / Vortex Admin Panel / Vortex Server Folder.
