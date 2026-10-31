# Vortex station protocol

One WebSocket per kiosk: `ws://<server>:8787/ws/station`. Every frame is a JSON object with a
`type` field. Requests from the kiosk may carry a `req_id`; the matching reply echoes it.

The server is authoritative. The kiosk never decides when a session ends; it renders
`remaining_seconds` from the last `session_update` and counts down locally between updates.

## Kiosk → server

| type | fields | reply |
|---|---|---|
| `hello` | `station_name`, `station_key` (empty on first run), `hostname`, `version` | `welcome` or `error` + close |
| `heartbeat` | – | `pong { server_time }` |
| `login` | `req_id`, `login` (email or username), `password` | `login_result` |
| `register` | `req_id`, `email`, `password`, `username?` | `register_result` |
| `logout` | `req_id` | `logout_result` |
| `state` | `req_id` | `session_update` (session may be `null`) |
| `admin_exit` | `req_id`, `pin` | `admin_exit_result { ok }` |
| `launch_report` | `item`, `kind` | – (audit only) |

`hello` must be the first frame (20 s timeout). If the station is new and auto-register is on,
`welcome` includes `station_key`; the kiosk must save it and send it on every later `hello`.

## Server → kiosk

| type | fields | meaning |
|---|---|---|
| `welcome` | `station`, `session` (or `null`), `server_time`, `config { cafe_name, currency, heartbeat_seconds, warn_thresholds }`, `station_key?` | connection accepted; restore the session if one is running |
| `session_update` | `session`, `event?` (`"topup"`) | new/changed session; also every `resync_seconds` |
| `warning` | `remaining_seconds`, `threshold` | time running low (1800 / 600 / 300 / 60 s) |
| `session_ended` | `reason` (`expired`, `logout`, `admin`), `message`, `session` | lock the PC now |
| `message` | `title`, `body`, `level` | show a toast from staff |
| `command` | `name` = `lock`, `unlock`, `restart`, `shutdown`, `reboot` | obey |
| `error` | `code`, `message` | protocol or auth error |

## Session object

```json
{
  "id": 12, "kind": "member",
  "station": {"id": 1, "name": "PC-01", "group": "VIP"},
  "member": {"id": 3, "email": "nova@vortex.gg", "username": "nova_rider", "tier": "GOLD", "points": 0},
  "started_at": "2026-09-07T12:00:00Z", "ended_at": null, "end_reason": null,
  "budget_seconds": 3600, "elapsed_seconds": 600, "remaining_seconds": 3000,
  "active": true, "server_time": "2026-09-07T12:10:00Z"
}
```

`kind` is `member` (runs against the member's wallet) or `guest` (staff-started walk-in with
its own prepaid seconds).

## Admin socket

`ws://<server>:8787/ws/admin?token=<staff token>` pushes `{ "type": "stations", "stations": [...] }`
whenever anything changes and at least every 5 seconds. Send `{ "type": "ping" }` to keep alive.

## REST

Interactive docs: `http://<server>:8787/api/docs` (log in via `POST /api/auth/login`, then use the
`Bearer` token). Error bodies are always `{ "error": "<code>", "message": "<text>" }`.
