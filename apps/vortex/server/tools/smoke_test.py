"""End-to-end smoke test for a Vortex server.

Two modes:

* Package mode (default): starts the built VortexServer.exe (or `--source` for run_server.py)
  on a throwaway port with a temporary data folder, so nothing touches the real data/ folder.
* Live mode (`--url http://<server>:8787`): tests a server that is already running, e.g. the
  one deployed in the cafe. It logs in with the given staff credentials and LEAVES TEST DATA
  behind (station SMOKE-01, one guest session, one shop order and two sales) - fine on a fresh
  install, not on a live cafe with real history.

In both modes it walks the money path the way a cafe would: staff login, station connects,
guest session, shop order, order done -> sale recorded, session ended -> station locked.

    python tools/smoke_test.py                              # dist/VortexServer/VortexServer.exe
    python tools/smoke_test.py --source                     # run_server.py with this Python
    python tools/smoke_test.py --url http://192.168.1.104:8787 [--user admin --password admin]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent          # .../server
PORT = 8799
BASE = f"http://127.0.0.1:{PORT}"

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}  {detail}")


def http(method: str, path: str, body=None, token: str | None = None, raw: bool = False):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(req, data, timeout=15) as r:
            payload = r.read()
            return r.status, (payload if raw else json.loads(payload or b"null")), r.headers
    except urllib.error.HTTPError as e:
        payload = e.read()
        try:
            return e.code, json.loads(payload), e.headers
        except ValueError:
            return e.code, payload, e.headers


def wait_up(proc: subprocess.Popen | None, timeout: float = 40) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc is not None and proc.poll() is not None:
            return False
        try:
            status, body, _ = http("GET", "/health")
            if status == 200 and body.get("ok"):
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


async def station_flow(token: str, exit_pin: str) -> None:
    import websockets

    ws_url = BASE.replace("https://", "wss://").replace("http://", "ws://") + "/ws/station"
    async with websockets.connect(ws_url, open_timeout=15) as ws:
        await ws.send(json.dumps({"type": "hello", "station_name": "SMOKE-01", "station_key": "",
                                  "hostname": "smoke", "version": "test"}))
        welcome = json.loads(await asyncio.wait_for(ws.recv(), 15))
        check("station auto-registers and gets a welcome", welcome.get("type") == "welcome", str(welcome)[:200])
        check("welcome issues a station_key", bool(welcome.get("station_key")))
        shop = welcome.get("shop") or []
        check("welcome carries shop products with pictures", len(shop) > 0 and all(p.get("image_url") for p in shop),
              f"{len(shop)} products")
        check("welcome carries events", len(welcome.get("events") or []) > 0)
        check("welcome config has cafe name + currency",
              bool(welcome.get("config", {}).get("cafe_name")) and bool(welcome["config"].get("currency")))
        station_id = welcome["station"]["id"]
        if not shop:
            return

        # ordering without a session must be refused
        await ws.send(json.dumps({"type": "order", "req_id": 1, "product_id": shop[0]["id"], "qty": 1}))
        res = json.loads(await asyncio.wait_for(ws.recv(), 15))
        check("order without a session is refused", res.get("type") == "order_result" and res.get("ok") is False
              and res.get("error") == "no_session", str(res)[:200])

        # staff starts a guest session (1 hour package)
        status, pk, _ = http("GET", "/api/packages", token=token)
        pkg = next((p for p in pk["packages"] if p["seconds"] == 3600), pk["packages"][0])
        status, sess, _ = http("POST", f"/api/stations/{station_id}/session", {"package_id": pkg["id"]}, token)
        check("staff starts a guest session", status == 201 and sess.get("active") is True, str(sess)[:200])
        upd = json.loads(await asyncio.wait_for(ws.recv(), 15))
        check("station receives session_update", upd.get("type") == "session_update" and upd["session"]["kind"] == "guest",
              str(upd)[:200])
        check("session remaining ~= package seconds", abs(upd["session"]["remaining_seconds"] - pkg["seconds"]) <= 5)

        # kiosk orders 2 x first product
        prod = shop[0]
        await ws.send(json.dumps({"type": "order", "req_id": 2, "product_id": prod["id"], "qty": 2}))
        res = json.loads(await asyncio.wait_for(ws.recv(), 15))
        check("order accepted with an active session", res.get("ok") is True and res["order"]["total"] == 2 * prod["price"],
              str(res)[:200])
        order_id = res["order"]["id"]

        status, q, _ = http("GET", "/api/orders", token=token)
        check("order shows in the pending queue", any(o["id"] == order_id for o in q["orders"]))
        status, done, _ = http("POST", f"/api/orders/{order_id}/done", {}, token)
        check("staff marks the order done", status == 200 and done.get("status") == "done", str(done)[:200])
        upd = json.loads(await asyncio.wait_for(ws.recv(), 15))
        check("station receives order_update done", upd.get("type") == "order_update" and upd["order"]["status"] == "done")
        status, tx, _ = http("GET", "/api/transactions", token=token)
        check("shop sale recorded as a transaction",
              any(t["kind"] == "shop" and t["amount"] == 2 * prod["price"] for t in tx["transactions"]))
        status, dash, _ = http("GET", "/api/dashboard", token=token)
        check("dashboard revenue includes package + shop",
              (dash.get("revenue_today") or 0) >= pkg["price"] + 2 * prod["price"], str(dash)[:200])

        # staff ends the session -> kiosk locks
        status, ended, _ = http("DELETE", f"/api/stations/{station_id}/session", token=token)
        check("staff ends the session", status == 200 and ended.get("active") is False, str(ended)[:200])
        msg = json.loads(await asyncio.wait_for(ws.recv(), 15))
        check("station receives session_ended (lock)", msg.get("type") == "session_ended" and msg.get("reason") == "admin",
              str(msg)[:200])

        # staff exit PIN
        await ws.send(json.dumps({"type": "admin_exit", "req_id": 3, "pin": "0000"}))
        res = json.loads(await asyncio.wait_for(ws.recv(), 15))
        check("wrong exit PIN rejected", res.get("ok") is False)
        if exit_pin:
            await ws.send(json.dumps({"type": "admin_exit", "req_id": 4, "pin": exit_pin}))
            res = json.loads(await asyncio.wait_for(ws.recv(), 15))
            check(f"exit PIN {exit_pin} accepted", res.get("ok") is True)


def main() -> int:
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=str(HERE / "dist" / "VortexServer" / "VortexServer.exe"))
    ap.add_argument("--source", action="store_true", help="test run_server.py instead of the exe")
    ap.add_argument("--url", help="test an already-running server, e.g. http://192.168.1.104:8787 (leaves test data)")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="admin")
    ap.add_argument("--pin", default="1234", help="staff exit PIN to try ('' to skip)")
    ap.add_argument("--keep", action="store_true", help="keep the temp data folder (package mode)")
    args = ap.parse_args()

    live = bool(args.url)
    proc = None
    data_dir = None
    log = None
    if live:
        BASE = args.url.rstrip("/")
        print(f"testing live server: {BASE}")
    else:
        if args.source:
            cmd = [sys.executable, str(HERE / "run_server.py"), "--port", str(PORT)]
        else:
            if not Path(args.exe).exists():
                print(f"exe not found: {args.exe}  (run build_server.bat first, or use --source)")
                return 2
            cmd = [args.exe, "--port", str(PORT)]
        data_dir = Path(tempfile.mkdtemp(prefix="vortex-smoke-"))
        env = dict(os.environ, VORTEX_DATA_DIR=str(data_dir))
        print(f"starting: {' '.join(cmd)}\n  data dir: {data_dir}")
        log = open(data_dir / "stdout.txt", "w", encoding="utf-8")
        proc = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, cwd=str(Path(cmd[0]).parent))

    t0 = time.time()
    try:
        up = wait_up(proc, timeout=15 if live else 40)
        check(f"server answers /health within {time.time() - t0:.1f}s", up)
        if not up:
            if log:
                log.close()
                print((data_dir / "stdout.txt").read_text("utf-8")[-3000:])
            return 1

        status, body, _ = http("GET", "/health")
        check("health reports a version", bool(body.get("version")), str(body))
        status, page, _ = http("GET", "/admin/", raw=True)
        check("admin panel page served", status == 200 and b"admin.js" in page)
        status, body, _ = http("GET", "/", raw=True)
        check("/ redirects to the admin panel", status == 200 and b"admin.js" in body)

        status, body, _ = http("POST", "/api/auth/login", {"username": args.user, "password": "definitely-wrong"})
        check("wrong staff password rejected", status == 401)
        status, body, _ = http("POST", "/api/auth/login", {"username": args.user, "password": args.password})
        check(f"staff login {args.user} works", status == 200 and body.get("token"), str(body)[:200])
        if not body.get("token"):
            return 1
        token = body["token"]

        status, body, _ = http("GET", "/api/products", token=token)
        products = body.get("products", [])
        check("products present" if live else "24 seed products", status == 200 and (len(products) > 0 if live else len(products) == 24),
              f"{len(products)} products")
        img = next((p["image_url"] for p in products if p.get("image_url")), None)
        status, raw, headers = http("GET", img, raw=True) if img else (0, b"", {})
        check("product picture served from /media", status == 200 and raw[:8] == b"\x89PNG\r\n\x1a\n", f"{img} -> {status}")
        if not live:
            check("seed pictures copied into data/media", (data_dir / "media" / "products").exists()
                  and len(list((data_dir / "media" / "products").glob("*.png"))) == 24)
        status, body, _ = http("GET", "/api/events", token=token)
        check("events present" if live else "8 seed events", status == 200 and (len(body.get("events", [])) > 0 if live else len(body.get("events", [])) == 8))
        status, body, _ = http("GET", "/api/stations", token=token)
        if live:
            check("stations list readable", status == 200 and isinstance(body.get("stations"), list),
                  f"{len(body.get('stations', []))} stations")
        else:
            check("stations list empty on a fresh install", status == 200 and body.get("stations") == [])

        asyncio.run(station_flow(token, args.pin))

        status, body, _ = http("GET", "/api/stations", token=token)
        check("SMOKE-01 is now a registered station", any(s["name"] == "SMOKE-01" for s in body["stations"]))
        status, body, _ = http("GET", "/api/audit", token=token)
        check("audit log has entries", status == 200 and len(body.get("events", [])) > 3)

        if not live:
            check("server.log written in the data folder", (data_dir / "server.log").exists()
                  and (data_dir / "server.log").stat().st_size > 0)
            check("server.json created in the data folder", (data_dir / "server.json").exists())
            check("database created in the data folder", (data_dir / "vortex.db").exists())
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
            log.close()
            if failed:
                print("\n---- server output (tail) ----")
                print((data_dir / "stdout.txt").read_text("utf-8")[-2500:])
            if not args.keep:
                shutil.rmtree(data_dir, ignore_errors=True)

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
