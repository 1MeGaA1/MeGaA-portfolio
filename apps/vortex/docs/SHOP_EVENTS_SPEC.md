# Shop + Events — implementation contract

Goal (user request, 2026-09-09): the kiosk shop must be **orderable** (orders reach staff at the
counter), **products / prices / pictures are managed in the admin panel**, and **events are
controlled from the admin panel** (enable/disable, remove all from the client, "offer" type, and
choose whether an event shows on the client Home page banner and/or the Events page).

Three layers are built in parallel against THIS document. Do not invent shapes: if something is
missing here, pick the simplest option consistent with the existing code and note it in your report.

Owners (edit ONLY your area):
- **server**  : `server/vortex_server/**`, `server/tests/**`, `server/build_server.bat`
- **admin**   : `server/admin/**` (index.html, admin.js, admin.css)
- **client**  : `client-native/**` (vortex_native/, qml/, build_native.bat, tools/, shop.json)
The web client `client/` is NOT touched by anyone.

Conventions already in the codebase (follow them):
- Server: FastAPI + SQLite, no ORM. `Engine` methods raise `EngineError(code, message, status)`;
  REST returns `{"error": code, "message": text}` on failure. Staff routes use `Depends(require_staff)`.
  DB helpers: `db.query/one/execute/insert/scalar/transaction`. Audit with `engine.audit(staff_id, action, detail)`.
  Pushes: `hub.send_station(station_id, msg)`, `hub.broadcast_admin(msg)`, `engine.broadcast_stations()`.
  Schema lives in `db.py` `SCHEMA` (all `CREATE TABLE IF NOT EXISTS`, so adding tables is safe for
  existing databases). `seed_defaults()` runs at startup and must be idempotent.
- **Money is in MINOR units** everywhere (e.g. `2500` = 25.00 EGP): `packages.price`,
  `transactions.amount`, and now `products.price` / `orders.*`. The admin panel formats `/100`
  exactly like it does for packages; the client shows whole units (`EGP 25`) or 2 decimals when needed.
- No new pip dependencies. `python-multipart` is NOT installed → image upload is base64 JSON.
- Admin panel: vanilla JS SPA (`admin.js`): `api(path,{method,body})`, `showPage`, `loaders`,
  modal forms (see `packageForm`/`groupForm`), `toast()`, `fail()`, `esc()`, `$`/`$$`.
- QML gotcha: never put `;` right after a grouped block like `anchors { ... }` — next property on a new line.
- Native client reuses `vortex_client` (link/launcher); `Controller(QObject)` maps server events to Qt
  signals; blocking requests run on worker threads via `self._in_thread`.

---

## 1. Database (server) — add to `SCHEMA` in `db.py`

```sql
CREATE TABLE IF NOT EXISTS products (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    category   TEXT NOT NULL DEFAULT 'snacks',    -- 'drinks' | 'snacks' | 'meals'
    price      INTEGER NOT NULL DEFAULT 0,        -- MINOR units (2500 = 25.00)
    image      TEXT,                              -- media-relative path, e.g. 'products/cocacola.png'
    best       INTEGER NOT NULL DEFAULT 0,        -- 1 = shown in BEST SELLERS
    enabled    INTEGER NOT NULL DEFAULT 1,
    sort       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY,
    station_id   INTEGER NOT NULL REFERENCES stations(id),
    session_id   INTEGER REFERENCES sessions(id),
    member_id    INTEGER REFERENCES members(id),
    product_id   INTEGER REFERENCES products(id),
    product_name TEXT NOT NULL,                   -- snapshot at order time
    qty          INTEGER NOT NULL DEFAULT 1,
    unit_price   INTEGER NOT NULL DEFAULT 0,      -- snapshot, minor units
    total        INTEGER NOT NULL DEFAULT 0,      -- qty * unit_price
    status       TEXT NOT NULL DEFAULT 'pending', -- 'pending' | 'done' | 'cancelled'
    note         TEXT,
    staff_id     INTEGER REFERENCES staff(id),    -- who marked done/cancelled
    created_at   TEXT NOT NULL,
    updated_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'event',    -- 'event' | 'offer'
    game        TEXT NOT NULL DEFAULT '',         -- e.g. 'VALORANT · 5v5'
    tag         TEXT NOT NULL DEFAULT '',         -- small label, e.g. 'FLAGSHIP TOURNAMENT · REGISTRATION OPEN'
    players     TEXT NOT NULL DEFAULT '',         -- e.g. '256 players'
    when_text   TEXT NOT NULL DEFAULT '',         -- e.g. 'TOMORROW 8PM' / 'Starts in 2h 15m'
    prize       TEXT NOT NULL DEFAULT '',         -- free text, e.g. 'EGP 5,000'
    status      TEXT NOT NULL DEFAULT 'upcoming', -- 'live' | 'upcoming'
    cats        TEXT NOT NULL DEFAULT '',         -- comma list from: live,upcoming,weekly,weekend,tournament,offer
    enabled     INTEGER NOT NULL DEFAULT 1,
    show_home   INTEGER NOT NULL DEFAULT 0,       -- 1 = featured banner on client Home
    show_events INTEGER NOT NULL DEFAULT 1,       -- 1 = listed on client Events page
    sort        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
```
`transactions.kind` gains the value `'shop'` (comment only; no schema change).

## 2. Media files (server)

- Media root: `Settings.media_dir` (new field) defaulting to `str(DATA_DIR / "media")`. Created at startup.
  `main.py` mounts it: `app.mount("/media", StaticFiles(directory=media_dir), name="media")`.
- Product pictures live under `<media_dir>/products/`. `products.image` stores the media-relative
  path (`products/<file>`); views expose `image_url = "/media/" + image` (or `null`).
- **Seed pictures** ship with the server in `server/vortex_server/seed_media/products/*.png`
  (already present: 24 PNGs + ATTRIBUTION.txt). On first seed (products table empty) copy them into
  `<media_dir>/products/` (skip files that already exist). When frozen, locate them via
  `Path(__file__).parent / "seed_media"`; `build_server.bat` must add
  `--add-data "vortex_server/seed_media;vortex_server/seed_media"`.
- Upload: `POST /api/products/{id}/image` body `{"filename": "photo.png", "data": "<base64>"}`.
  Accept png/jpg/jpeg/webp (by extension; also sniff PNG/JPEG magic bytes), decoded size ≤ 4 MB
  (else `EngineError("too_large", ..., 413)`), save as `products/<id>-<unix_ts>.<ext>`, delete the
  product's previous file if it was inside `<media_dir>/products/` and is not referenced by another
  product, update `products.image`, `audit(staff,"product.image",name)`, push shop to stations,
  return the product view. `DELETE /api/products/{id}/image` clears it (same cleanup).

## 3. JSON views

**Product** (`engine.product_view(row)`):
```json
{"id": 1, "name": "Coca-Cola", "category": "drinks", "price": 2500,
 "image": "products/cocacola.png", "image_url": "/media/products/cocacola.png",
 "best": true, "enabled": true, "sort": 0}
```
**Order** (`engine.order_view(row)`):
```json
{"id": 7, "station": {"id": 3, "name": "PC-01"}, "member": {"id": 2, "username": "mega"} | null,
 "session_id": 12, "product_id": 1, "product_name": "Coca-Cola", "qty": 2, "unit_price": 2500,
 "total": 5000, "status": "pending", "note": null, "created_at": "...", "updated_at": null}
```
**Event** (`engine.event_view(row)`) — note `when` (not `when_text`) and `cats` as a list:
```json
{"id": 1, "title": "VORTEX CUP 2026 · WEEK 3", "kind": "event", "game": "VALORANT · 5v5",
 "tag": "FLAGSHIP TOURNAMENT · REGISTRATION OPEN", "players": "256 players",
 "when": "Starts in 2h 15m", "prize": "EGP 5,000", "status": "upcoming",
 "cats": ["upcoming", "tournament"], "enabled": true, "show_home": true, "show_events": true, "sort": 0}
```

## 4. REST API (all under `/api`, staff auth via `require_staff`)

**Rename**: the existing audit-log route `GET /api/events` becomes **`GET /api/audit`** (same
response `{"events": [...]}`). The admin panel's dashboard "recent activity" must call `/audit`.

Products
- `GET /products` → `{"products": [all, incl. disabled, ORDER BY sort, name]}`
- `POST /products` `{name, category?, price?, best?, enabled?, sort?}` → product (201). Validate:
  name non-empty; category in drinks/snacks/meals; price ≥ 0 int.
- `PATCH /products/{id}` any of the same fields → product
- `DELETE /products/{id}` → if any order references it: `enabled=0` (keep history) else hard delete. `{"ok": true}`
- `POST /products/{id}/image`, `DELETE /products/{id}/image` → product (see §2)

Orders
- `GET /orders?status=pending|done|cancelled|all&limit=200` → `{"orders": [...]}`. Default
  `pending`. Pending sorted oldest→newest (a queue); others newest→oldest.
- `POST /orders/{id}/done` → order. Sets status `done`, `staff_id`, `updated_at`, and inserts a
  `transactions` row: `kind='shop'`, `member_id`, `session_id`, `station_id`, `staff_id`,
  `seconds=0`, `amount=total`, `note=f"{product_name} x{qty}"`. So shop sales count in dashboard
  revenue / sales. Idempotent: if already done → return as is (409 `already_done` is also acceptable).
- `POST /orders/{id}/cancel` → order (status `cancelled`). Cancelling a done order is an error `not_pending` 409.
- Both push `{"type":"order_update","order":view}` to the order's station and broadcast the pending
  queue to admins (see §5).

Events
- `GET /events` → `{"events": [all, ORDER BY sort, id]}`
- `POST /events` `{title, kind?, game?, tag?, players?, when?, prize?, status?, cats?(list), enabled?, show_home?, show_events?, sort?}` → event (201)
- `PATCH /events/{id}` same fields → event
- `DELETE /events/{id}` → `{"ok": true}` (hard delete)
- `POST /events/disable-all` → `{"events": [...]}` (all `enabled=0`) — "remove all events from the client"
- `POST /events/enable-all` → `{"events": [...]}`
Every products/events mutation calls `audit(...)` and pushes to stations (§5).

Pydantic models to add in `models.py`: `ProductCreate`, `ProductUpdate`, `ProductImage(filename:str, data:str)`,
`EventCreate`, `EventUpdate` (cats: `Optional[list[str]]`).

## 5. WebSocket protocol

Station socket (`/ws/station`):
- `welcome` gains: `"shop": [enabled product views, ORDER BY sort, name]`,
  `"events": [enabled event views]`, `"media_base": "/media"` (informational; views already carry `image_url`).
- Server → station pushes (to ALL connected stations) whenever products/events change:
  `{"type":"shop","items":[enabled product views]}` and `{"type":"events","events":[enabled event views]}`.
  Implement `engine.push_shop()` / `engine.push_events()` (iterate `hub.stations`).
- Station → server: `{"type":"order","req_id":N,"product_id":ID,"qty":1}`.
  Requires an active session on that station (`no_session` 409 → `ok:false`), product must exist
  and be enabled (`not_found` 404), qty 1..10 (`invalid`). Creates a pending order
  (`member_id` from the session if any). Reply `{"type":"order_result","req_id":N,"ok":true,"order":view}`
  or `{"type":"order_result","req_id":N,"ok":false,"error":code,"message":text}`.
  Audit `kiosk.order` with `"<station>: <product> x<qty>"`.
- Server → station: `{"type":"order_update","order":view}` on done/cancel.

Admin socket (`/ws/admin`):
- On connect, after the initial `stations` message, also send `{"type":"orders","orders":[pending views]}`.
- `engine.broadcast_orders()` sends the same message to all admins whenever an order is created or
  its status changes.

Client `ServerLink` already routes any message with a matching `req_id` to the waiting request and
everything else to `on_event(type, msg)` — no link changes needed.

## 6. Seed data (idempotent, only when the table is empty)

Products (`price` minor units; `image` = `products/<slug>.png`; `best` where marked):
```
drinks: Coca-Cola 2500 best cocacola | Pepsi 2500 pepsi | Sprite 2500 sprite | Water 1000 water |
        Red Bull 6000 best redbull | Monster Energy 6000 monster | Orange Juice 3500 orangejuice |
        Iced Tea 3000 icedtea | Lemonade 3000 lemonade | Coffee 4000 coffee
snacks: Doritos 3000 best doritos | Lay's 2000 lays | Oreo 2000 oreo | Snickers 2500 best snickers |
        M&M's 3000 mms | Popcorn 3000 popcorn | Mixed Nuts 4000 nuts | Protein Bar 5000 proteinbar
meals:  Pizza Slice 6000 best pizza | Burger 9000 burger | Hot Dog 5500 hotdog | Fries 4000 fries |
        Sandwich 6000 sandwich | Ramen Bowl 10000 ramen
```
`sort` = insertion order. Copy seed pictures as described in §2.

Events (all `enabled=1`, `show_events=1`; only the first has `show_home=1`):
```
1 event  "VORTEX CUP 2026 · WEEK 3"  game "VALORANT · 5v5" tag "FLAGSHIP TOURNAMENT · REGISTRATION OPEN"
         players "256 players" when "Starts in 2h 15m" prize "EGP 5,000" status upcoming cats upcoming,tournament  show_home=1
2 event  "Rocket League 3v3"    game "Rocket League"     prize "EGP 800"      when "LIVE NOW"     status live     cats live
3 event  "CS2 1v1 Ladder"       game "Counter-Strike 2"  prize "EGP 500/week" when "ONGOING"      status live     cats live,weekly
4 event  "Apex Duos Showdown"   game "Apex Legends"      prize "EGP 1,500"    when "TOMORROW 8PM" status upcoming cats upcoming,tournament
5 event  "FIFA Friday Night"    game "FIFA 26"           prize "EGP 300"      when "FRI 9PM"      status upcoming cats upcoming,weekly
6 event  "Fortnite Solo Cup"    game "Fortnite"          prize "EGP 2,000"    when "SAT 6PM"      status upcoming cats upcoming,tournament
7 event  "League Clash Weekend" game "League of Legends" prize "EGP 1,000"    when "SUN 4PM"      status upcoming cats upcoming,weekend,tournament
8 offer  "HAPPY HOUR · 2 HOURS FOR EGP 100" game "" tag "SPECIAL OFFER" when "TODAY 2PM–6PM" prize "EGP 100" status upcoming cats offer
```

## 7. Admin panel requirements

Add two nav items under `// MANAGE`: **SHOP** and **EVENTS** (same look as the others). Add the
page sections + loaders (`loaders.shop`, `loaders.events`) + titles.

**Shop page**
1. `// PENDING ORDERS` — a live queue fed by the admin socket `orders` message (also loaded via
   `GET /orders` when the page opens). Row: station name · user (member username or GUEST) ·
   `product ×qty` · total (formatted like other money) · time · buttons **DONE** (→ `/orders/{id}/done`)
   and **CANCEL** (→ `/orders/{id}/cancel`). Empty state "NO PENDING ORDERS". Show the pending count
   in the nav item as a small badge when > 0 (optional but nice). Re-render on each `orders` push
   without losing a button under the cursor (fingerprint like `renderStations`).
2. `// PRODUCTS` table: picture thumbnail (40px, `image_url`, placeholder box if none) · name ·
   category · price · BEST · ENABLED · actions **EDIT**, **PICTURE**, **DELETE**. Button
   **+ ADD PRODUCT**. Edit/Add = modal form: name, category (select drinks/snacks/meals), price
   (decimal in cafe currency, stored ×100), best (checkbox), enabled (checkbox).
   **PICTURE** = file input (`accept="image/*"`); resize client-side with a canvas to fit 512×512
   (keep aspect, PNG), then `POST /products/{id}/image {filename, data:<base64 without the data: prefix>}`;
   show a preview; also a "remove picture" action.
3. Optional: `// ORDER HISTORY` (last 50 done/cancelled) below.

**Events page**: table: title · kind (EVENT/OFFER pill) · game · when · prize · status (LIVE/UPCOMING pill) ·
ENABLED · HOME · EVENTS (three toggle switches/checkboxes that PATCH immediately) · actions **EDIT**, **DELETE**.
Buttons **+ ADD EVENT** and **DISABLE ALL** (confirm) and **ENABLE ALL**. Add/Edit modal: title, kind (select),
game, tag, players, when, prize, status (select), cats (checkboxes: live, upcoming, weekly, weekend,
tournament, offer), enabled, show_home ("show on Home banner"), show_events ("show on Events page").

Dashboard: change the recent-activity call from `/events` to `/audit`. Keep everything else working.

## 8. Native client requirements (`client-native`)

`vortex_native/controller.py`
- Store `self._shop: list`, `self._events: list`, `self._media_base: str` from `welcome`; update on
  `shop` / `events` pushes; emit new signals `shopChanged()` and `eventsChanged()` after updates
  (and once after welcome).
- Slots: `shop()` → enabled products (as received); `events()` → events with `show_events`;
  `featured()` → first event with `show_home` (or `null`/None); `order(productId:int, qty:int)` →
  runs `link.request({"type":"order","product_id":..,"qty":..})` on a worker thread and emits
  `orderResult(bool ok, str message, "QVariant" order)`.
- Property `serverHttp` (str, constant): the HTTP origin derived from `cfg.server`
  (`ws://` → `http://`, `wss://` → `https://`, strip any path). Client image source =
  `vortex.serverHttp + item.image_url`.
- Handle `order_update`: emit `messaged(title, body, "info")` — e.g. done → ("Order delivered",
  "Coca-Cola x1 — EGP 25 paid at the counter"), cancelled → ("Order cancelled", "...").
- Money formatting helper exposed to QML: `@Slot(int, result=str) money(minor)` → `"25"` when whole,
  else `"25.50"`; QML shows `vortex.currency + " " + vortex.money(price)`.
- Remove the shop.json loader (`_load_shop`, `self._shop = _load_shop()`), delete
  `client-native/shop.json`, remove `--add-data "shop.json;."` from `build_native.bat`, delete
  `client-native/qml/shop/` (pictures now come from the server), and point
  `client-native/tools/make_shop_images.py` `OUT` at `../server/vortex_server/seed_media/products`
  (i.e. `Path(__file__).resolve().parents[2] / "server" / "vortex_server" / "seed_media" / "products"`).

QML
- `ShopPage.qml`: model from `vortex.shop()`, refreshed on `vortex.shopChanged`; header text
  "ORDER HERE · PAY AT THE COUNTER"; **BUY** opens a small confirm dialog (product picture, name,
  qty − / + from 1..10, total) with **ORDER** → `vortex.order(id, qty)`; on `orderResult`:
  ok → `notify("Order sent to the counter · <name> ×<qty> · <currency> <total>")`, else `notify(message)`.
  Empty state "SHOP IS EMPTY" when no products. `ShopCard.qml`: image source `vortex.serverHttp + image_url`
  (letter fallback if none), price via `vortex.money`.
- `EventsPage.qml` + `EventCard.qml`: model from `vortex.events()`, refreshed on `vortex.eventsChanged`;
  use `title` (was `name`); an `offer` kind gets the amber accent and the tag "OFFER"; empty state
  "NO EVENTS RIGHT NOW" when the list is empty (this is what "remove all events from the client" looks like).
- `HomePage.qml`: featured banner bound to `vortex.featured()` (fields tag/title/game/players/when/prize);
  when it is null the banner is hidden (`visible:false`, takes no space). Refresh on `eventsChanged`.
- `Content.qml`: remove `featured` and `events` (keep `shopCats`, `eventCats`, friends, currency…).
- Keep the existing look (Theme tokens, SectionLabel, VxButton, FilterChips, ModalOverlay if useful).

## 9. Verification (each owner runs what applies; report results)

- Server: `cd server && python -m unittest discover -s tests -t .` — add tests: product CRUD + view,
  order requires active session, order done → `transactions` row kind `shop` with amount=total,
  events disable-all, `/audit` route, welcome contains `shop`/`events`.
- Client: `cd client-native && python -c "..."` offscreen QML load with zero warnings (see
  `tests/` and the scratch grab scripts for the pattern), `python -m py_compile` on changed .py.
- Admin: `node --check server/admin/admin.js`.
- End-to-end (done by the integrator after all three land): throwaway server on :8788 with a temp
  `VORTEX_DATA_DIR`, fake station → welcome has 24 products with `image_url` + 8 events; staff
  starts a session; station sends `order` → admin `GET /orders` shows it → `POST done` → transaction
  exists and station receives `order_update`; admin panel Shop/Events pages exercised in a browser.
