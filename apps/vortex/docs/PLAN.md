# Vortex — Gaming Cafe Management System

Project plan following the five-step problem-solving lifecycle:
**1. Analyze → 2. Plan → 3. Execute → 4. Test → 5. Update.**

Vortex is our own alternative to Gizmo and iCafeCloud: a server that owns members,
stations, sessions and money, plus a locked kiosk client on every gaming PC.

---

## 1. Analyze

### 1.1 What the product must do

A gaming cafe sells **time on PCs**. The software has to:

| Need | Who uses it | Where |
|---|---|---|
| Lock every PC until a paid session starts | customer | Client (kiosk) |
| Let a member log in and see their remaining time | customer | Client |
| Launch games and apps from inside the locked shell | customer | Client |
| End the session and re-lock the PC when time runs out | system | Server decides, client obeys |
| See every station live: free / in session / offline | cafe staff | Admin panel |
| Create members, sell time (top-up), start guest sessions | cafe staff | Admin panel |
| Set prices per station group and time packages | owner | Admin panel |
| Keep a record of every sale and session for reports | owner | Server database |

### 1.2 How the competitors are built (verified 2026-09-07)

- **Gizmo**: C#/.NET. Client UI is a Blazor web app hosted in a WPF window through WebView2.
  Server + manager are .NET. Source of the client UI is public (github.com/GAMP).
- **iCafeCloud**: native `iCafeMenu.exe` shell whose whole UI is HTML/CSS/JS files that cafe
  owners can edit; server side is hosted in the cloud.

Both share one pattern: **a web page for the UI, a native host for the lockdown.**

### 1.3 What already exists

- `index.html` — kiosk UI prototype (7.3k lines, all data faked).
- `Admin panel.html` — admin UI prototype (static).
- `CLAUDE_CODE_SPEC.md`, `../vortex-kiosk/` — an earlier Tauri/Rust plan and scaffold that
  was never built (no Rust toolchain on this machine). Its requirements doc and data models
  were reused as input here.

### 1.4 Constraints

- Windows 10/11 only. Dev machine is Windows 11 **Home**, so the lockdown must not depend on
  Assigned Access (Pro-only). Shell replacement + keyboard hook works on every edition.
- Cafe internet is unreliable → the server runs on the **LAN** (counter PC), not in the cloud.
- Kiosk shares the PC with games → keep RAM low. WebView2 (already installed with Windows)
  instead of Electron or a bundled Chromium.
- Every time-and-money decision is made on the **server**. The client never decides when a
  session ends; it only renders what the server tells it.
- Design system is fixed: only cyan `#00e5ff` + magenta `#ff3d9a` accents, fonts Rajdhani /
  Chakra Petch / JetBrains Mono, clipped corners, `// COMMENT` labels.

### 1.5 Decisions taken

| Decision | Choice | Why |
|---|---|---|
| Client host | **Python + WebView2** (pywebview) | Same architecture as Gizmo/iCafeCloud, in the language we already use. Reuses `index.html` as-is. |
| Server | **Python FastAPI + SQLite + WebSockets**, on the LAN | Zero infrastructure, one process, works offline. |
| Admin panel | The existing HTML, served by the server, wired to the REST API | Keeps the design, no build step. |
| Version 1 scope | Stations, members, server-enforced sessions, top-ups, pricing, client lock/login/timer/launch/lock-on-expiry | This is the money path. Everything else is decoration until this works. |
| Deferred to v2 | Shop & sales, events/tournaments, friends, points shop, QR login, server-managed game deployment, cloud sync | Not needed to run a cafe on day one. |

---

## 2. Plan

### 2.1 Architecture

```
                 LAN (cafe switch)
┌──────────────────────┐            ┌───────────────────────────────┐
│  Counter PC          │            │  Gaming PC  ×N                │
│  vortex-server       │◄──WS/HTTP──┤  vortex-client (Python)       │
│  ├─ FastAPI + SQLite │            │  ├─ pywebview → WebView2      │
│  ├─ session engine   │            │  │    └─ ui/index.html (Vortex)│
│  ├─ /api  (REST)     │            │  ├─ link.py   (WS to server)  │
│  ├─ /ws/station      │            │  ├─ lockdown.py (kbd hook,    │
│  ├─ /ws/admin        │            │  │     foreground guard)      │
│  └─ /admin (HTML)    │            │  ├─ launcher.py (games/apps)  │
└──────────────────────┘            │  └─ watchdog (restart loop)   │
        ▲                           └───────────────────────────────┘
        │ browser
   Staff / owner
```

- **One WebSocket per station** (`/ws/station`). Login, logout, session updates, warnings,
  admin commands all travel on it. If it drops, the client shows "reconnecting" and keeps the
  last known session (grace period), then locks.
- **Admin panel** uses REST for actions and `/ws/admin` for the live station board.
- **Time model: prepaid time wallet.** A member owns `time_balance_seconds`. Staff sells time
  (a package or custom minutes at the group's hourly rate) → a `transaction` row. A session
  runs against the wallet: `remaining = balance − elapsed`. Top-ups during a session simply
  grow the wallet. When the session ends, the used seconds are deducted once. Guest sessions
  (walk-ins without an account) carry their own prepaid seconds.

### 2.2 Data model (SQLite)

| Table | Purpose |
|---|---|
| `staff` | admin logins (password hash + exit PIN hash) |
| `station_groups` | VIP / Regular…, `rate_per_hour` in minor currency units |
| `stations` | one row per PC: name, secret key, group, ip, last_seen, locked |
| `members` | customers: email, username, password hash, tier, `time_balance_seconds`, points |
| `packages` | sellable time bundles: name, seconds, price, optional group |
| `sessions` | station × member/guest, `started_at`, `ended_at`, `end_reason`, `seconds_used` |
| `transactions` | every sale/top-up/adjustment with seconds and amount |
| `settings` | cafe name, currency, auto-register stations… |
| `audit_log` | who did what |

### 2.3 Protocol (station WebSocket, JSON)

Client → server: `hello`, `heartbeat`, `login`, `register`, `logout`, `admin_exit`, `launch_report`.
Server → client: `welcome`, `session_update`, `warning`, `session_ended`, `message`, `command`
(`lock`, `unlock`, `restart`, `shutdown`, `reboot`), `error`.

Full message shapes are in `docs/PROTOCOL.md`.

### 2.4 Milestones

| # | Milestone | Done when |
|---|---|---|
| M1 | Server core | DB + engine + REST + WS run; unit tests for the time math pass |
| M2 | Admin panel wired | Dashboard, stations board, members, top-ups, packages work against the live server |
| M3 | Client UI wired | `index.html` logs in through the bridge, shows the real timer, ends on expiry — verified in a browser against the server |
| M4 | Kiosk host | pywebview window, keyboard hook, foreground guard, launcher, watchdog, admin PIN exit |
| M5 | Packaging & install | PyInstaller builds, `install` docs for server and stations, shell replacement script |

### 2.5 Repository layout

```
Desktop/Vortex/                      ← the application
├── docs/            PLAN.md, PROTOCOL.md, INSTALL.md, PROGRESS.md
├── server/          vortex_server/ (package), admin/ (panel), tests/, run_server.py
└── client/          vortex_client/ (package), ui/ (kiosk page + media), run_client.py

Desktop/Gaming Hub/Gaming Hub/       ← original prototype (reference, untouched)
    index.html, Admin panel.html, splash.mp4, logo.mp4, CLAUDE_CODE_SPEC.md
```

---

## 3. Execute

Progress log lives in `docs/PROGRESS.md`. Each milestone is built, run, and checked
before the next starts.

## 4. Test

- **Unit tests** (`server/tests/`, stdlib `unittest`): session time math, expiry, top-up
  during a session, guest sessions, wallet deduction, package pricing.
- **API tests** with FastAPI's `TestClient`: staff login, station hello/login over WS,
  admin commands, error codes.
- **Manual acceptance** with the real client on this machine talking to the local server:
  login → timer → top-up from admin → expiry → lock.

## 5. Update

After the first real-cafe trial: collect what staff actually click, tune warnings and
grace periods, then start v2 (shop, events, QR login, game deployment).
