# Deploying the Vortex server on Windows Server 2022

The server is one self-contained folder (`VortexServer\`). Nothing else is installed on the
server PC: no Python, no database engine, no web server. The gaming PCs talk to it over the
cafe LAN on TCP port 8787.

```
Vortex\server\build_server.bat          -> Vortex\server\dist\VortexServer\     (build on the dev PC)
copy that folder to the server           -> C:\Vortex\VortexServer\               (any path works)
```

---

## 1. Build the package (dev PC)

```
cd Vortex\server
build_server.bat
```

Output: `dist\VortexServer\` (~38 MB; `Vortex\VortexServer-0.1.0.zip` is the same folder zipped). It contains `VortexServer.exe`, the admin panel, the
seed product pictures, and the deploy kit (`*.bat` + `README-DEPLOY.txt`). Test the exact
package you are about to ship:

```
python tools\smoke_test.py
```

It starts the exe on port 8799 with a throwaway data folder and walks the money path
(staff login, station connects, guest session, shop order, sale recorded, session ended).
Expect `35 passed, 0 failed`.

## 2. Copy to the server

Copy the whole `dist\VortexServer` folder to the server, e.g. `C:\Vortex\VortexServer\`.
Use a USB stick, a network share, or RDP clipboard. Do **not** put it on the Desktop of a
user account that might be deleted; `C:\Vortex\` is a good home.

The folder must stay writable: the server creates `data\` next to the exe on first run
(database, pictures, log, settings).

## 3. First start (as Administrator)

Right-click each file → **Run as administrator**:

| Step | File | What it does |
|---|---|---|
| 1 | `open_firewall.bat` | Inbound rule "Vortex Server", TCP 8787, all profiles. Without it the gaming PCs see the server as OFFLINE. |
| 2 | `install_autostart.bat` | Task Scheduler task "Vortex Server": runs `serve_forever.bat` at every boot as SYSTEM (no login needed) and starts it right away. `serve_forever.bat` restarts the exe 5 s after any crash. |
| 3 | `check_server.bat` | Prints RUNNING + the LAN address, opens the admin panel. |

Log in at `http://localhost:8787/admin/` with **admin / admin**. Go to **Settings** and change
the password and the kiosk exit PIN (default 1234) before the cafe opens.

**Is everything OK?** Open `http://<server-ip>:8787/status` from any PC or phone on the network
(no login). It shows a big green ALL SYSTEMS OK, or in red which check failed and why: database,
pictures folder, disk space, session engine, stations online, admin panel; plus the server's
addresses, local time and uptime. It refreshes every 5 s and turns red if the server stops answering.

Day to day: `check_server.bat` (status), `stop_server.bat`, `start_server.bat`,
`uninstall_autostart.bat` (removes the boot task). All in the same folder.

## 4. Fix the server's IP

The cafe server (hostname `<server-name>`) was deployed on 2026-09-13 to `C:\Vortex\VortexServer\`
over Tailscale (`<tailscale-ip>`, SSH as Administrator with `~/.ssh/cafe_server`). Its LAN
address was `192.168.1.104` by DHCP at the time; reserve it in the router or set it static.
Time zone was set to Egypt Standard Time (it was Pacific after install), which matters for
"today's" revenue and session times.


Gaming PCs find the server by IP, so it must not change. Either set a static IP on the
server's network adapter (Settings → Network → Ethernet → IP assignment → Manual) or reserve
its MAC address in the router's DHCP. `check_server.bat` prints the address to use.

## 5. Point the gaming PCs at it

On every gaming PC, in the client's `client.json`:

```json
"server": "ws://192.168.1.10:8787",
"station_name": "PC-01"
```

(use the server's real IP, and a different `station_name` per PC). Start the client; the
station appears under **Stations** in the admin panel within a few seconds. Details in
`docs/INSTALL.md` §2–3.

## 6. Test from the server itself

1. `check_server.bat` → STATUS: RUNNING.
2. Admin panel → **Members** → NEW MEMBER → TOP UP 1 hour.
3. From a gaming PC (or a second PC on the LAN with the client), log in as that member:
   the timer runs, the PC unlocks. **Stations** shows it IN SESSION with a live countdown.
4. Stations → TOP UP → the kiosk shows "Time added". Stations → END → the kiosk locks.
5. Kiosk → Shop → order something → **Shop** page in the admin panel shows it in PENDING
   ORDERS → DONE → the kiosk gets "Order delivered" and **Sales** lists the sale.
6. Reboot the server. Wait a minute, run `check_server.bat`: it must say RUNNING without
   anyone logging in.

No client PC yet? Unzip `Vortex\VortexClientNative-0.1.0.zip` on any LAN PC (or on the
server itself), set `"server"` in its `client.json`, and run `run_native.bat`: it runs in a
normal window (`"kiosk": false`) and behaves exactly like a cafe PC. `README-CLIENT.txt` inside
explains the two fields to edit.

### Automated test of a running server

From the dev PC (or any PC with Python and the repo), against the deployed server:

```
cd Vortex\server
python tools\smoke_test.py --url http://<server-ip>:8787 --user admin --password admin --pin 1234
```

Expect `31 passed`. It leaves test data behind (station SMOKE-01, one guest session, one shop
order, two sales), so run it right after install, before real customers. To start clean again:
`stop_server.bat`, delete `dataortex.db*`, `start_server.bat` (products and events reseed).

## 7. Backups and updates

- **Backup**: stop the server (`stop_server.bat`), copy the `data\` folder somewhere safe,
  start it again. `data\vortex.db` is the whole cafe (members, money, sessions);
  `data\media\` holds product pictures.
- **Update**: build a new `dist\VortexServer`, stop the server, replace every file **except
  the `data\` folder**, start it again. The database schema is additive (new tables and
  columns are created on start), so old data keeps working.
- **Move to another PC**: copy the folder including `data\`, run steps 3–4 there, and change
  the IP in every `client.json`.

## 8. Troubleshooting

| Symptom | Check |
|---|---|
| `check_server.bat` says NOT RUNNING | `data\server.log` (last lines). "Port 8787 is already in use" = a second copy is running; `stop_server.bat` then `start_server.bat`. |
| Gaming PCs show SERVER OFFLINE | `ping <server-ip>` from the gaming PC; firewall rule present (`open_firewall.bat`); `client.json` has `ws://` and the right IP and port. |
| Admin panel drops to the login screen | The server restarted; staff tokens live in memory. Log in again. |
| Task exists but the server is not up after boot | Task Scheduler → Task Scheduler Library → "Vortex Server" → History tab. The task runs from the folder it was installed in; if you moved the folder, run `install_autostart.bat` again. |
| Windows Server shows the old admin panel after an update | Hard-refresh the browser (Ctrl+F5). |

Server settings (`data\server.json`): `port`, `cafe_name`, `currency`, `auto_register_stations`,
`token_ttl_hours`. Restart the server after editing.
