"""End-to-end tests through HTTP and WebSockets with FastAPI's TestClient."""
from __future__ import annotations

import base64
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from vortex_server.config import Settings
from vortex_server.db import Database
from vortex_server.main import create_app

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\0" * 64


class ApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.media_dir = Path(tempfile.mkdtemp(prefix="vortex-media-"))
        settings = Settings(db_path=":memory:", media_dir=str(self.media_dir), tick_seconds=0.05)
        self.app = create_app(settings, Database(":memory:"))
        self.client = TestClient(self.app)
        self.client.__enter__()          # runs lifespan (tick loop)
        r = self.client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        self.assertEqual(r.status_code, 200, r.text)
        self.headers = {"Authorization": "Bearer " + r.json()["token"]}

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        shutil.rmtree(self.media_dir, ignore_errors=True)

    def test_status_page_and_checks(self) -> None:
        r = self.client.get("/api/status")            # public: no auth header
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["ok"], body["checks"])
        names = {c["name"] for c in body["checks"]}
        self.assertTrue({"Database", "Pictures folder", "Disk space", "Session engine", "Stations", "Admin panel"} <= names)
        self.assertNotIn("token", r.text)
        self.assertEqual(body["stations"], [])
        self.assertTrue(body["disks"], "at least one fixed disk")
        for d in body["disks"]:
            self.assertTrue(d["total_gb"] > 0 and 0 <= d["used_pct"] <= 100 and d["free_gb"] <= d["total_gb"], d)
        r = self.client.get("/status", follow_redirects=False)
        self.assertEqual(r.status_code, 307)
        self.assertEqual(r.headers["location"], "/admin/status.html")
        r = self.client.get("/admin/status.html")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"ALL SYSTEMS OK", r.content)

    def test_auth_required(self) -> None:
        r = self.client.get("/api/dashboard")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["error"], "unauthorized")
        r = self.client.post("/api/auth/login", json={"username": "admin", "password": "nope"})
        self.assertEqual(r.status_code, 401)

    def test_member_topup_and_station_login_over_websocket(self) -> None:
        r = self.client.post("/api/members", headers=self.headers,
                             json={"email": "nova@vortex.gg", "password": "secret", "username": "nova_rider"})
        self.assertEqual(r.status_code, 201, r.text)
        member_id = r.json()["id"]
        r = self.client.post(f"/api/members/{member_id}/topup", headers=self.headers, json={"seconds": 3600, "amount": 2000})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["member"]["time_balance_seconds"], 3600)

        with self.client.websocket_connect("/ws/station") as ws:
            ws.send_json({"type": "hello", "station_name": "PC-01", "station_key": "", "hostname": "DESK-1"})
            welcome = ws.receive_json()
            self.assertEqual(welcome["type"], "welcome")
            self.assertTrue(welcome["station_key"])            # auto-registered, key issued once
            self.assertIsNone(welcome["session"])

            r = self.client.get("/api/stations", headers=self.headers)
            station = r.json()["stations"][0]
            self.assertEqual(station["status"], "free")
            self.assertTrue(station["online"])

            ws.send_json({"type": "login", "req_id": 1, "login": "nova@vortex.gg", "password": "wrong"})
            res = ws.receive_json()
            self.assertEqual(res["type"], "login_result")
            self.assertFalse(res["ok"])
            self.assertEqual(res["error"], "bad_credentials")

            ws.send_json({"type": "login", "req_id": 2, "login": "nova@vortex.gg", "password": "secret"})
            # the engine pushes session_update first, then the login_result reply
            got = [ws.receive_json(), ws.receive_json()]
            kinds = sorted(m["type"] for m in got)
            self.assertEqual(kinds, ["login_result", "session_update"])
            result = next(m for m in got if m["type"] == "login_result")
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["session"]["remaining_seconds"], 3600)
            self.assertEqual(result["member"]["username"], "nova_rider")

            dash = self.client.get("/api/dashboard", headers=self.headers).json()
            self.assertEqual(dash["stations_in_session"], 1)

            # staff tops up while the customer is playing -> kiosk hears about it
            r = self.client.post(f"/api/stations/{station['id']}/session/topup", headers=self.headers, json={"seconds": 600})
            self.assertEqual(r.status_code, 200, r.text)
            update = ws.receive_json()
            self.assertEqual(update["type"], "session_update")
            self.assertEqual(update["event"], "topup")
            self.assertGreaterEqual(update["session"]["remaining_seconds"], 4190)

            # staff ends the session -> kiosk is told to lock
            r = self.client.delete(f"/api/stations/{station['id']}/session", headers=self.headers)
            self.assertEqual(r.status_code, 200, r.text)
            ended = ws.receive_json()
            self.assertEqual(ended["type"], "session_ended")
            self.assertEqual(ended["reason"], "admin")

            # PIN check for the kiosk escape
            ws.send_json({"type": "admin_exit", "req_id": 3, "pin": "0000"})
            self.assertFalse(ws.receive_json()["ok"])
            ws.send_json({"type": "admin_exit", "req_id": 4, "pin": "1234"})
            self.assertTrue(ws.receive_json()["ok"])

        # socket closed -> station shows offline
        station = self.client.get("/api/stations", headers=self.headers).json()["stations"][0]
        self.assertEqual(station["status"], "offline")

    def test_guest_session_from_admin_and_message_command(self) -> None:
        with self.client.websocket_connect("/ws/station") as ws:
            ws.send_json({"type": "hello", "station_name": "PC-02", "station_key": ""})
            ws.receive_json()
            station = self.client.get("/api/stations", headers=self.headers).json()["stations"][0]
            r = self.client.post(f"/api/stations/{station['id']}/session", headers=self.headers, json={"guest_minutes": 30})
            self.assertEqual(r.status_code, 201, r.text)
            self.assertEqual(r.json()["kind"], "guest")
            self.assertEqual(r.json()["remaining_seconds"], 1800)
            self.assertEqual(ws.receive_json()["type"], "session_update")

            r = self.client.post(f"/api/stations/{station['id']}/command", headers=self.headers,
                                 json={"name": "message", "title": "Hi", "body": "Pizza is here"})
            self.assertEqual(r.status_code, 200, r.text)
            msg = ws.receive_json()
            self.assertEqual(msg["type"], "message")
            self.assertEqual(msg["body"], "Pizza is here")

            sales = self.client.get("/api/transactions?today=true", headers=self.headers).json()["transactions"]
            self.assertEqual(sales[0]["kind"], "guest_time")
            self.assertEqual(sales[0]["amount"], 1000)

    def test_admin_websocket_receives_station_board(self) -> None:
        token = self.headers["Authorization"].split()[1]
        with self.client.websocket_connect(f"/ws/admin?token={token}") as admin_ws:
            first = admin_ws.receive_json()
            self.assertEqual(first["type"], "stations")
            queue = admin_ws.receive_json()
            self.assertEqual(queue, {"type": "orders", "orders": []})
            with self.client.websocket_connect("/ws/station") as ws:
                ws.send_json({"type": "hello", "station_name": "PC-03", "station_key": ""})
                ws.receive_json()
                board = admin_ws.receive_json()
                self.assertEqual(board["type"], "stations")
                self.assertEqual(board["stations"][0]["name"], "PC-03")
                self.assertTrue(board["stations"][0]["online"])

    def test_pricing_endpoints(self) -> None:
        r = self.client.get("/api/packages", headers=self.headers)
        self.assertEqual(len(r.json()["packages"]), 4)
        r = self.client.post("/api/packages", headers=self.headers, json={"name": "10 h", "seconds": 36000, "price": 15000})
        self.assertEqual(r.status_code, 201)
        r = self.client.get("/api/price?seconds=5400", headers=self.headers)
        self.assertEqual(r.json()["amount"], 3000)
        r = self.client.put("/api/settings", headers=self.headers, json={"cafe_name": "Test Cafe", "currency": "usd"})
        self.assertEqual(r.json()["currency"], "USD")

    def test_audit_route_replaces_events_for_activity(self) -> None:
        r = self.client.get("/api/audit", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["events"][0]["action"], "staff.login")
        self.assertEqual(r.json()["events"][0]["staff"], "admin")
        # /events is now the client-facing events table
        r = self.client.get("/api/events", headers=self.headers)
        self.assertEqual(len(r.json()["events"]), 8)
        self.assertEqual(r.json()["events"][0]["title"], "VORTEX CUP 2026 · WEEK 3")

    def test_products_api_and_picture_upload(self) -> None:
        r = self.client.get("/api/products", headers=self.headers)
        self.assertEqual(len(r.json()["products"]), 24)
        r = self.client.get("/media/products/cocacola.png")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.content[:8], PNG_BYTES[:8])

        r = self.client.post("/api/products", headers=self.headers, json={"name": "Tea", "category": "drinks", "price": 1500})
        self.assertEqual(r.status_code, 201, r.text)
        product = r.json()
        self.assertEqual((product["name"], product["price"], product["image_url"]), ("Tea", 1500, None))
        r = self.client.post("/api/products", headers=self.headers, json={"name": "Bad", "category": "toys"})
        self.assertEqual(r.status_code, 422)
        r = self.client.patch(f"/api/products/{product['id']}", headers=self.headers, json={"best": True, "price": 1700})
        self.assertEqual((r.json()["best"], r.json()["price"]), (True, 1700))

        data = base64.b64encode(PNG_BYTES).decode()
        r = self.client.post(f"/api/products/{product['id']}/image", headers=self.headers, json={"filename": "tea.png", "data": data})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["image_url"].startswith(f"/media/products/{product['id']}-"))
        r = self.client.get(r.json()["image_url"])
        self.assertEqual(r.status_code, 200)
        r = self.client.post(f"/api/products/{product['id']}/image", headers=self.headers, json={"filename": "tea.bmp", "data": data})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "invalid")
        r = self.client.delete(f"/api/products/{product['id']}/image", headers=self.headers)
        self.assertIsNone(r.json()["image_url"])
        r = self.client.delete(f"/api/products/{product['id']}", headers=self.headers)
        self.assertEqual(r.json(), {"ok": True})
        self.assertEqual(len(self.client.get("/api/products", headers=self.headers).json()["products"]), 24)

    def test_events_api_disable_all(self) -> None:
        r = self.client.post("/api/events", headers=self.headers,
                             json={"title": "Test Cup", "when": "MON 5PM", "cats": ["upcoming", "tournament"], "show_home": True})
        self.assertEqual(r.status_code, 201, r.text)
        event = r.json()
        self.assertEqual((event["when"], event["cats"], event["show_home"]), ("MON 5PM", ["upcoming", "tournament"], True))
        r = self.client.patch(f"/api/events/{event['id']}", headers=self.headers, json={"show_events": False, "status": "live"})
        self.assertEqual((r.json()["show_events"], r.json()["status"]), (False, "live"))

        r = self.client.post("/api/events/disable-all", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(len(r.json()["events"]), 9)
        self.assertFalse(any(e["enabled"] for e in r.json()["events"]))
        r = self.client.post("/api/events/enable-all", headers=self.headers)
        self.assertTrue(all(e["enabled"] for e in r.json()["events"]))
        r = self.client.delete(f"/api/events/{event['id']}", headers=self.headers)
        self.assertEqual(r.json(), {"ok": True})
        self.assertEqual(len(self.client.get("/api/events", headers=self.headers).json()["events"]), 8)

    def test_kiosk_order_flow(self) -> None:
        token = self.headers["Authorization"].split()[1]
        with self.client.websocket_connect("/ws/station") as ws:
            ws.send_json({"type": "hello", "station_name": "PC-04", "station_key": ""})
            welcome = ws.receive_json()
            self.assertEqual(welcome["media_base"], "/media")
            self.assertEqual(len(welcome["shop"]), 24)
            self.assertEqual(welcome["shop"][0]["image_url"], "/media/products/cocacola.png")
            self.assertEqual(len(welcome["events"]), 8)
            cola = welcome["shop"][0]

            # no session yet -> refused
            ws.send_json({"type": "order", "req_id": 1, "product_id": cola["id"], "qty": 1})
            res = ws.receive_json()
            self.assertEqual((res["type"], res["req_id"], res["ok"], res["error"]), ("order_result", 1, False, "no_session"))

            station = self.client.get("/api/stations", headers=self.headers).json()["stations"][0]
            r = self.client.post(f"/api/stations/{station['id']}/session", headers=self.headers, json={"guest_minutes": 30})
            self.assertEqual(r.status_code, 201, r.text)
            self.assertEqual(ws.receive_json()["type"], "session_update")

            with self.client.websocket_connect(f"/ws/admin?token={token}") as admin_ws:
                self.assertEqual(admin_ws.receive_json()["type"], "stations")
                self.assertEqual(admin_ws.receive_json()["orders"], [])

                ws.send_json({"type": "order", "req_id": 2, "product_id": cola["id"], "qty": 2})
                res = ws.receive_json()
                self.assertTrue(res["ok"], res)
                order = res["order"]
                self.assertEqual((order["product_name"], order["qty"], order["total"], order["status"]), ("Coca-Cola", 2, 5000, "pending"))
                self.assertIsNone(order["member"])
                pushed = admin_ws.receive_json()
                self.assertEqual(pushed["type"], "orders")
                self.assertEqual([o["id"] for o in pushed["orders"]], [order["id"]])

                r = self.client.get("/api/orders", headers=self.headers)
                self.assertEqual([o["id"] for o in r.json()["orders"]], [order["id"]])
                r = self.client.post(f"/api/orders/{order['id']}/done", headers=self.headers)
                self.assertEqual(r.status_code, 200, r.text)
                self.assertEqual(r.json()["status"], "done")
                update = ws.receive_json()
                self.assertEqual((update["type"], update["order"]["status"]), ("order_update", "done"))
                self.assertEqual(admin_ws.receive_json()["orders"], [])

            sales = self.client.get("/api/transactions?today=true", headers=self.headers).json()["transactions"]
            shop = [t for t in sales if t["kind"] == "shop"]
            self.assertEqual(len(shop), 1)
            self.assertEqual((shop[0]["amount"], shop[0]["note"], shop[0]["station"]), (5000, "Coca-Cola x2", "PC-04"))
            r = self.client.post(f"/api/orders/{order['id']}/cancel", headers=self.headers)
            self.assertEqual(r.status_code, 409)
            self.assertEqual(r.json()["error"], "not_pending")
            self.assertEqual(self.client.get("/api/orders?status=done", headers=self.headers).json()["orders"][0]["id"], order["id"])
            # bad qty from the kiosk
            ws.send_json({"type": "order", "req_id": 3, "product_id": cola["id"], "qty": 99})
            res = ws.receive_json()
            self.assertEqual((res["ok"], res["error"]), (False, "invalid"))
            # deleting a product that has orders keeps it (disabled) for history
            r = self.client.delete(f"/api/products/{cola['id']}", headers=self.headers)
            self.assertEqual(r.json(), {"ok": True})
            self.assertEqual(ws.receive_json()["type"], "shop")
            cola_now = next(p for p in self.client.get("/api/products", headers=self.headers).json()["products"] if p["id"] == cola["id"])
            self.assertFalse(cola_now["enabled"])


if __name__ == "__main__":
    unittest.main()
