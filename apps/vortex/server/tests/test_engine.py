"""Unit tests for the session engine: the time-and-money math.

Run:  python -m unittest discover -s tests -v   (from the server/ folder)
"""
from __future__ import annotations

import base64
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from vortex_server.config import Settings
from vortex_server.db import Database
from vortex_server.engine import Engine, EngineError
from vortex_server.ws import Hub

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\0" * 64      # enough for the magic-byte sniff


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


class RecordingHub(Hub):
    """Pretends every station is online and records what was sent to it."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[tuple[int, dict]] = []
        self.online: set[int] = set()

    def is_station_online(self, station_id: int) -> bool:
        return station_id in self.online

    async def send_station(self, station_id: int, message: dict) -> bool:
        self.sent.append((station_id, message))
        return station_id in self.online

    def messages(self, kind: str) -> list[dict]:
        return [m for _, m in self.sent if m.get("type") == kind]


class EngineTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.db = Database(":memory:")
        self.db.init_schema()
        self.media_dir = Path(tempfile.mkdtemp(prefix="vortex-media-"))
        self.settings = Settings(db_path=":memory:", media_dir=str(self.media_dir),
                                 warn_thresholds=[1800, 600, 300, 60], min_session_seconds=60)
        self.hub = RecordingHub()
        self.clock = FakeClock()
        self.engine = Engine(self.db, self.settings, self.hub, clock=self.clock)
        self.engine.seed_defaults()
        self.station = self.engine.create_station("PC-01")
        self.hub.online.add(self.station["id"])
        self.member = self.engine.create_member("nova@vortex.gg", "secret", "nova_rider")

    def tearDown(self) -> None:
        shutil.rmtree(self.media_dir, ignore_errors=True)

    async def topup(self, seconds: int, amount: int = 0) -> None:
        await self.engine.topup_member(self.member["id"], seconds=seconds, amount=amount)

    def product_named(self, name: str) -> dict:
        return next(p for p in self.engine.products() if p["name"] == name)

    # ------------------------------------------------------------ members & pricing
    def test_member_password_and_username(self) -> None:
        self.assertIsNotNone(self.engine.authenticate_member("nova@vortex.gg", "secret"))
        self.assertIsNotNone(self.engine.authenticate_member("nova_rider", "secret"))
        self.assertIsNone(self.engine.authenticate_member("nova@vortex.gg", "wrong"))
        auto = self.engine.create_member("second@vortex.gg", "secret")
        self.assertEqual(auto["username"], "second")
        with self.assertRaises(EngineError) as ctx:
            self.engine.create_member("nova@vortex.gg", "secret")
        self.assertEqual(ctx.exception.code, "email_exists")

    def test_price_for_custom_time_uses_group_rate(self) -> None:
        regular = self.engine.groups()[0]
        self.assertEqual(regular["rate_per_hour"], 2000)
        self.assertEqual(self.engine.price_for_seconds(3600, regular["id"]), 2000)
        self.assertEqual(self.engine.price_for_seconds(1800, regular["id"]), 1000)
        self.assertEqual(self.engine.price_for_seconds(0, regular["id"]), 0)

    async def test_topup_with_package_adds_seconds_and_records_sale(self) -> None:
        one_hour = next(p for p in self.engine.packages() if p["seconds"] == 3600)
        result = await self.engine.topup_member(self.member["id"], package_id=one_hour["id"])
        self.assertEqual(result["member"]["time_balance_seconds"], 3600)
        self.assertEqual(result["transaction"]["amount"], one_hour["price"])
        self.assertEqual(result["transaction"]["kind"], "topup")

    # ------------------------------------------------------------ sessions
    async def test_cannot_login_without_time(self) -> None:
        with self.assertRaises(EngineError) as ctx:
            await self.engine.start_session(self.station["id"], member_id=self.member["id"])
        self.assertEqual(ctx.exception.code, "no_time")

    async def test_session_counts_down_and_deducts_on_logout(self) -> None:
        await self.topup(3600, 2000)
        view = await self.engine.start_session(self.station["id"], member_id=self.member["id"])
        self.assertEqual(view["remaining_seconds"], 3600)
        self.assertEqual(view["kind"], "member")

        self.clock.advance(600)
        live = self.engine.session_view(self.engine.session_row(view["id"]))
        self.assertEqual(live["elapsed_seconds"], 600)
        self.assertEqual(live["remaining_seconds"], 3000)

        ended = await self.engine.end_session(view["id"], "logout")
        self.assertEqual(ended["seconds_used"], 600)
        self.assertFalse(ended["active"])
        member = self.engine.member_row(self.member["id"])
        self.assertEqual(member["time_balance_seconds"], 3000)
        self.assertEqual(self.hub.messages("session_ended")[-1]["reason"], "logout")

    async def test_tick_expires_session_when_time_runs_out(self) -> None:
        await self.topup(300)
        view = await self.engine.start_session(self.station["id"], member_id=self.member["id"])
        self.clock.advance(299)
        await self.engine.tick()
        self.assertIsNotNone(self.engine.active_session_row(self.station["id"]))
        self.clock.advance(1)
        await self.engine.tick()
        self.assertIsNone(self.engine.active_session_row(self.station["id"]))
        ended = self.engine.session_row(view["id"])
        self.assertEqual(ended["end_reason"], "expired")
        self.assertEqual(ended["seconds_used"], 300)
        self.assertEqual(self.engine.member_row(self.member["id"])["time_balance_seconds"], 0)

    async def test_topup_during_session_extends_it(self) -> None:
        await self.topup(600)
        view = await self.engine.start_session(self.station["id"], member_id=self.member["id"])
        self.clock.advance(500)
        await self.topup(3600, 2000)
        live = self.engine.session_view(self.engine.session_row(view["id"]))
        self.assertEqual(live["remaining_seconds"], 600 + 3600 - 500)
        # the kiosk got a fresh session_update flagged as a top-up
        updates = [m for m in self.hub.messages("session_update") if m.get("event") == "topup"]
        self.assertEqual(len(updates), 1)
        self.clock.advance(3700)
        await self.engine.tick()
        self.assertIsNone(self.engine.active_session_row(self.station["id"]))
        self.assertEqual(self.engine.member_row(self.member["id"])["time_balance_seconds"], 0)

    async def test_wallet_never_goes_negative(self) -> None:
        await self.topup(120)
        view = await self.engine.start_session(self.station["id"], member_id=self.member["id"])
        self.clock.advance(999)          # server was asleep; far past the budget
        await self.engine.tick()
        ended = self.engine.session_row(view["id"])
        self.assertEqual(ended["seconds_used"], 120)
        self.assertEqual(self.engine.member_row(self.member["id"])["time_balance_seconds"], 0)

    async def test_member_cannot_be_on_two_stations(self) -> None:
        await self.topup(3600)
        other = self.engine.create_station("PC-02")
        self.hub.online.add(other["id"])
        await self.engine.start_session(self.station["id"], member_id=self.member["id"])
        with self.assertRaises(EngineError) as ctx:
            await self.engine.start_session(other["id"], member_id=self.member["id"])
        self.assertEqual(ctx.exception.code, "member_busy")
        with self.assertRaises(EngineError) as ctx:
            await self.engine.start_session(self.station["id"], guest_seconds=600)
        self.assertEqual(ctx.exception.code, "station_busy")

    async def test_locked_station_rejects_client_login_but_not_staff(self) -> None:
        await self.topup(3600)
        self.engine.update_station(self.station["id"], locked=True)
        with self.assertRaises(EngineError) as ctx:
            await self.engine.start_session(self.station["id"], member_id=self.member["id"], started_by="client")
        self.assertEqual(ctx.exception.code, "station_locked")
        view = await self.engine.start_session(self.station["id"], member_id=self.member["id"], started_by="staff")
        self.assertTrue(view["active"])

    async def test_guest_session_has_its_own_budget_and_sale(self) -> None:
        view = await self.engine.start_session(self.station["id"], guest_seconds=1800, started_by="staff", staff_id=1)
        self.assertEqual(view["kind"], "guest")
        self.assertEqual(view["remaining_seconds"], 1800)
        sales = self.engine.list_transactions()
        self.assertEqual(sales[0]["kind"], "guest_time")
        self.assertEqual(sales[0]["amount"], 1000)          # 30 min at 2000/hour
        await self.engine.topup_session(view["id"], seconds=600)
        live = self.engine.session_view(self.engine.session_row(view["id"]))
        self.assertEqual(live["budget_seconds"], 2400)
        self.clock.advance(2400)
        await self.engine.tick()
        self.assertEqual(self.engine.session_row(view["id"])["end_reason"], "expired")

    # ------------------------------------------------------------ warnings
    async def test_warnings_fire_once_per_threshold_in_order(self) -> None:
        await self.topup(2000)
        await self.engine.start_session(self.station["id"], member_id=self.member["id"])
        fired: list[int] = []
        for _ in range(2000):
            self.clock.advance(1)
            await self.engine.tick()
            fired = [m["threshold"] for m in self.hub.messages("warning")]
        self.assertEqual(fired, [1800, 600, 300, 60])

    async def test_short_session_does_not_warn_immediately(self) -> None:
        await self.topup(1200)   # 20 minutes: below the 30-minute threshold from the start
        await self.engine.start_session(self.station["id"], member_id=self.member["id"])
        await self.engine.tick()
        self.assertEqual(self.hub.messages("warning"), [])
        self.clock.advance(601)
        await self.engine.tick()
        self.assertEqual([m["threshold"] for m in self.hub.messages("warning")], [600])

    async def test_topup_re_arms_warnings(self) -> None:
        await self.topup(700)
        await self.engine.start_session(self.station["id"], member_id=self.member["id"])
        self.clock.advance(150)      # remaining 550 -> 600 warning fires
        await self.engine.tick()
        self.assertEqual([m["threshold"] for m in self.hub.messages("warning")], [600])
        await self.topup(3600)       # remaining 4150
        self.clock.advance(2400)     # remaining 1750 -> 1800 warning must fire again
        await self.engine.tick()
        self.assertEqual([m["threshold"] for m in self.hub.messages("warning")], [600, 1800])

    # ------------------------------------------------------------ stations
    def test_station_hello_auto_registers_then_requires_key(self) -> None:
        row, issued = self.engine.station_hello("PC-09", "", hostname="DESK-9", ip="192.168.1.9")
        self.assertIsNotNone(issued)
        self.assertEqual(row["name"], "PC-09")
        again, issued2 = self.engine.station_hello("PC-09", issued, hostname="DESK-9", ip="192.168.1.9")
        self.assertIsNone(issued2)
        self.assertEqual(again["id"], row["id"])
        with self.assertRaises(EngineError) as ctx:
            self.engine.station_hello("PC-09", "wrong-key")
        self.assertEqual(ctx.exception.code, "station_key_mismatch")
        self.settings.auto_register_stations = False
        with self.assertRaises(EngineError) as ctx:
            self.engine.station_hello("PC-10", "")
        self.assertEqual(ctx.exception.code, "unknown_station")

    async def test_dashboard_counts(self) -> None:
        await self.topup(3600, 2000)
        await self.engine.start_session(self.station["id"], member_id=self.member["id"])
        dash = self.engine.dashboard()
        self.assertEqual(dash["stations_total"], 1)
        self.assertEqual(dash["stations_in_session"], 1)
        self.assertEqual(dash["revenue_today"], 2000)
        self.assertEqual(len(dash["active_sessions"]), 1)

    def test_exit_pin(self) -> None:
        self.assertIsNotNone(self.engine.verify_exit_pin("1234"))
        self.assertIsNone(self.engine.verify_exit_pin("0000"))

    # ------------------------------------------------------------ shop: products
    def test_seed_products_events_and_pictures(self) -> None:
        products = self.engine.products()
        self.assertEqual(len(products), 24)
        cola = products[0]
        self.assertEqual(cola["name"], "Coca-Cola")
        self.assertEqual(cola["price"], 2500)
        self.assertTrue(cola["best"])
        self.assertEqual(cola["image_url"], "/media/products/cocacola.png")
        self.assertTrue((self.media_dir / "products" / "cocacola.png").is_file())
        self.assertEqual(len(list((self.media_dir / "products").glob("*.png"))), 24)
        events = self.engine.events()
        self.assertEqual(len(events), 8)
        self.assertEqual(events[0]["when"], "Starts in 2h 15m")
        self.assertEqual(events[0]["cats"], ["upcoming", "tournament"])
        self.assertEqual([e["show_home"] for e in events], [True] + [False] * 7)
        self.assertEqual(events[-1]["kind"], "offer")
        # seeding again must not duplicate anything
        self.assertEqual(self.engine.seed_defaults(), {})
        self.assertEqual(len(self.engine.products()), 24)
        self.assertEqual(len(self.engine.events()), 8)

    async def test_product_crud_and_view(self) -> None:
        self.hub.stations[self.station["id"]] = object()      # "connected" so pushes are recorded
        view = await self.engine.create_product("Tea", "drinks", 1500, best=True, staff_id=1)
        # no sort given -> appended after the 24 seeded products (sort 0..23)
        self.assertEqual(view, {"id": view["id"], "name": "Tea", "category": "drinks", "price": 1500, "image": None,
                                "image_url": None, "best": True, "enabled": True, "sort": 24})
        self.assertEqual(len(self.engine.products()), 25)
        pushed = self.hub.messages("shop")
        self.assertEqual(len(pushed), 1)
        self.assertIn("Tea", [p["name"] for p in pushed[0]["items"]])

        view = await self.engine.update_product(view["id"], price=1800, enabled=False, category="snacks")
        self.assertEqual((view["price"], view["enabled"], view["category"]), (1800, False, "snacks"))
        self.assertNotIn("Tea", [p["name"] for p in self.engine.products(include_disabled=False)])
        with self.assertRaises(EngineError) as ctx:
            await self.engine.update_product(view["id"], category="toys")
        self.assertEqual(ctx.exception.code, "invalid")
        with self.assertRaises(EngineError):
            await self.engine.create_product("   ", "drinks", 100)
        with self.assertRaises(EngineError):
            await self.engine.create_product("Neg", "drinks", -1)

        await self.engine.delete_product(view["id"])
        self.assertIsNone(self.engine.product_row(view["id"]))
        with self.assertRaises(EngineError) as ctx:
            await self.engine.delete_product(view["id"])
        self.assertEqual(ctx.exception.code, "not_found")
        self.assertEqual(self.engine.recent_events(3)[-1]["action"], "product.create")

    async def test_product_image_upload_and_cleanup(self) -> None:
        cola = self.product_named("Coca-Cola")
        data = base64.b64encode(PNG_BYTES).decode()
        view = await self.engine.set_product_image(cola["id"], "photo.PNG", data, staff_id=1)
        first = self.media_dir / view["image"]
        self.assertEqual(view["image"], f"products/{cola['id']}-{int(self.clock.now.timestamp())}.png")
        self.assertEqual(first.read_bytes(), PNG_BYTES)
        self.assertFalse((self.media_dir / "products" / "cocacola.png").exists())   # previous (seed) file cleaned up
        self.assertTrue((self.media_dir / "products" / "pepsi.png").is_file())        # other products untouched

        self.clock.advance(1)
        view = await self.engine.set_product_image(cola["id"], "again.png", "data:image/png;base64," + data)
        self.assertFalse(first.exists())                        # previous upload removed
        self.assertTrue((self.media_dir / view["image"]).is_file())

        with self.assertRaises(EngineError) as ctx:
            await self.engine.set_product_image(cola["id"], "photo.gif", data)
        self.assertEqual(ctx.exception.code, "invalid")
        with self.assertRaises(EngineError) as ctx:
            await self.engine.set_product_image(cola["id"], "photo.png", base64.b64encode(b"not an image").decode())
        self.assertEqual(ctx.exception.code, "invalid")
        with self.assertRaises(EngineError) as ctx:
            await self.engine.set_product_image(cola["id"], "photo.png", "@@@ not base64")
        self.assertEqual(ctx.exception.code, "invalid")
        big = base64.b64encode(PNG_BYTES + b"\0" * (4 * 1024 * 1024)).decode()
        with self.assertRaises(EngineError) as ctx:
            await self.engine.set_product_image(cola["id"], "photo.png", big)
        self.assertEqual((ctx.exception.code, ctx.exception.status), ("too_large", 413))

        current = self.media_dir / view["image"]
        cleared = await self.engine.clear_product_image(cola["id"])
        self.assertIsNone(cleared["image_url"])
        self.assertFalse(current.exists())

    # ------------------------------------------------------------ shop: orders
    async def test_order_requires_active_session(self) -> None:
        cola = self.product_named("Coca-Cola")
        with self.assertRaises(EngineError) as ctx:
            await self.engine.create_order(self.station["id"], cola["id"], 1)
        self.assertEqual((ctx.exception.code, ctx.exception.status), ("no_session", 409))

        await self.topup(3600)
        sess = await self.engine.start_session(self.station["id"], member_id=self.member["id"])
        order = await self.engine.create_order(self.station["id"], cola["id"], 2)
        self.assertEqual(order["status"], "pending")
        self.assertEqual(order["station"], {"id": self.station["id"], "name": "PC-01"})
        self.assertEqual(order["member"]["username"], "nova_rider")
        self.assertEqual(order["session_id"], sess["id"])
        self.assertEqual((order["product_name"], order["qty"], order["unit_price"], order["total"]), ("Coca-Cola", 2, 2500, 5000))

        for bad_qty in (0, 11, "x"):
            with self.assertRaises(EngineError) as ctx:
                await self.engine.create_order(self.station["id"], cola["id"], bad_qty)
            self.assertEqual(ctx.exception.code, "invalid")
        await self.engine.update_product(cola["id"], enabled=False)
        with self.assertRaises(EngineError) as ctx:
            await self.engine.create_order(self.station["id"], cola["id"], 1)
        self.assertEqual(ctx.exception.code, "not_found")
        self.assertEqual(self.engine.list_orders("pending")[0]["id"], order["id"])
        self.assertIn("PC-01: Coca-Cola x2", [e["detail"] for e in self.engine.recent_events(5) if e["action"] == "kiosk.order"])

    async def test_order_done_records_shop_sale(self) -> None:
        await self.engine.start_session(self.station["id"], guest_seconds=1800, started_by="staff", staff_id=1)
        pizza = self.product_named("Pizza Slice")
        order = await self.engine.create_order(self.station["id"], pizza["id"], 3)
        before = self.engine.dashboard()["revenue_today"]

        done = await self.engine.set_order_status(order["id"], "done", staff_id=1)
        self.assertEqual(done["status"], "done")
        self.assertIsNotNone(done["updated_at"])
        sale = self.engine.list_transactions()[0]
        self.assertEqual((sale["kind"], sale["amount"], sale["seconds"], sale["staff_id"]), ("shop", 18000, 0, 1))
        self.assertEqual(sale["note"], "Pizza Slice x3")
        self.assertEqual(sale["station_id"], self.station["id"])
        self.assertEqual(self.engine.dashboard()["revenue_today"], before + 18000)
        update = self.hub.messages("order_update")[-1]
        self.assertEqual(update["order"]["id"], order["id"])

        # idempotent done; cancelling a delivered order is refused; only one sale recorded
        self.assertEqual((await self.engine.set_order_status(order["id"], "done", staff_id=1))["status"], "done")
        with self.assertRaises(EngineError) as ctx:
            await self.engine.set_order_status(order["id"], "cancelled", staff_id=1)
        self.assertEqual((ctx.exception.code, ctx.exception.status), ("not_pending", 409))
        self.assertEqual(sum(1 for t in self.engine.list_transactions() if t["kind"] == "shop"), 1)

        other = await self.engine.create_order(self.station["id"], pizza["id"], 1)
        cancelled = await self.engine.set_order_status(other["id"], "cancelled", staff_id=1)
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(self.engine.list_orders("pending"), [])
        self.assertEqual([o["id"] for o in self.engine.list_orders("all")], [other["id"], order["id"]])
        # a product with order history is only disabled on delete
        await self.engine.delete_product(pizza["id"])
        self.assertFalse(self.engine.product_row(pizza["id"])["enabled"])

    # ------------------------------------------------------------ events
    async def test_events_crud_and_disable_all(self) -> None:
        self.hub.stations[self.station["id"]] = object()
        view = await self.engine.create_event(title="Test Night", kind="offer", when="8PM", cats=["offer", "weekly"], staff_id=1)
        self.assertEqual((view["kind"], view["when"], view["cats"], view["enabled"]), ("offer", "8PM", ["offer", "weekly"], True))
        view = await self.engine.update_event(view["id"], title="Test Night 2", show_home=True, cats=[])
        self.assertEqual((view["title"], view["show_home"], view["cats"]), ("Test Night 2", True, []))
        with self.assertRaises(EngineError):
            await self.engine.update_event(view["id"], cats=["bogus"])
        with self.assertRaises(EngineError):
            await self.engine.create_event(title="", staff_id=1)
        self.assertEqual(len(self.engine.events()), 9)
        self.assertIn("Test Night 2", [e["title"] for e in self.hub.messages("events")[-1]["events"]])

        disabled = await self.engine.set_all_events_enabled(False, staff_id=1)
        self.assertEqual(len(disabled), 9)
        self.assertFalse(any(e["enabled"] for e in disabled))
        self.assertEqual(self.engine.events(include_disabled=False), [])
        self.assertEqual(self.hub.messages("events")[-1]["events"], [])   # the client sees "no events"
        enabled = await self.engine.set_all_events_enabled(True, staff_id=1)
        self.assertTrue(all(e["enabled"] for e in enabled))
        await self.engine.delete_event(view["id"], staff_id=1)
        self.assertEqual(len(self.engine.events()), 8)


if __name__ == "__main__":
    unittest.main()
