import asyncio
import json
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import main
from order_lifecycle import ActionError
from lunch_api import catalog
from backup import backup
from config import database_path
from order_rules import OrderError, fingerprint, normalize, validate_schedule
from order_storage import existing_order


class Orders(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name) / "synthetic.db")
        self.patches = [patch.object(main, "ADMIN_ID", 900), patch.object(main, "KITCHEN_IDS", {901}), patch.object(main, "DB_NAME", self.db), patch.object(main, "local_now", return_value=datetime(2026, 9, 14, 10, tzinfo=timezone(timedelta(hours=5))))]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        main.init_db()
        self.sql("INSERT INTO users(user_id,balance) VALUES (1,10000)")
        self.items = [dict(item_type="menu_item", category_id="breakfasts", item_name="Омлет", quantity=1)]

    def sql(self, query, args=()):
        with closing(main._conn()) as conn, conn:
            return conn.execute(query, args).fetchall()

    def create(self, token="test_request", items=None, points=0, clear=False):
        items = items or self.items
        base, disc, comp, text = main.server_quote(items, "2026-09-14", "12:00")
        digest = fingerprint(items, "2026-09-14", "12:00", "", bool(points))
        return main.create_order(1, text, base-points, "12:00", "2026-09-14", token, points_used=points, source_items=items, request_hash=digest, clear_server_cart=clear)

    def test_replay_without_catalog_or_new_debit(self):
        first = self.create(points=5000)
        digest = fingerprint(self.items, "2026-09-14", "12:00", "", True)
        self.sql("DELETE FROM menu_items")
        row = existing_order(main._conn, "test_request", digest, 1)
        self.assertEqual(row["order_id"], first[0])
        again = main.create_order(1, "ignored", 0, "old", "old", "test_request", source_items=self.items, request_hash=digest)
        self.assertFalse(again[-1])
        self.assertEqual(main.get_points_balance(1), 5000)

    def test_conflicting_token(self):
        self.create()
        with self.assertRaisesRegex(OrderError, "другого заказа"):
            self.create(items=[dict(self.items[0], quantity=2)])

    def test_balance_race_does_not_save(self):
        base, _, _, text = main.server_quote(self.items, "2026-09-14", "12:00")
        self.sql("UPDATE users SET balance=1000")
        with self.assertRaises(OrderError):
            main.create_order(1, text, base-5000, "12:00", "2026-09-14", "race", points_used=5000, source_items=self.items, request_hash="digest")
        self.assertEqual(len(self.sql("SELECT order_id FROM orders")), 0)
        self.assertEqual(main.get_points_balance(1), 1000)

    def test_rewards_and_refund_once(self):
        oid = self.create(points=5000)[0]
        main.confirm_payment(oid, 900)
        main.set_order_status(oid, "cooking", 901)
        main.set_order_status(oid, "ready", 901)
        main.set_order_status(oid, "delivered", 901)
        main.set_order_status(oid, "delivered", 901)
        self.assertEqual(main.get_points_balance(1), 6500)
        with self.assertRaises(ActionError):
            main.set_order_status(oid, "cancelled", 900)
        oid = self.create(token="second", points=1000)[0]
        main.set_order_status(oid, "cancelled", 900)
        main.set_order_status(oid, "cancelled", 900)
        self.assertEqual(main.get_points_balance(1), 6500)

    def test_rollback_components_and_cart(self):
        product = main.get_items("breakfasts")[1]
        main.update_cart(1, str(product["id"]), product["name"], product["price"], 1, "2026-09-14")
        self.sql("CREATE TRIGGER fail_component BEFORE INSERT ON order_components BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.create(points=1000, clear=True)
        self.assertEqual(len(self.sql("SELECT order_id FROM orders")), 0)
        self.assertEqual(len(self.sql("SELECT id FROM order_items")), 0)
        self.assertTrue(main.get_cart(1))
        self.assertEqual(main.get_points_balance(1), 10000)
        self.sql("DROP TRIGGER fail_component")
        self.create(clear=True)
        self.assertFalse(main.get_cart(1))

    def test_iced_tea_and_shared_flow_limits(self):
        cfg, hot = main.get_lunch_config("mon")
        h = hot[0]
        main.update_cart(1, f"lunch_mon_{h['id']}_g1_skeep_iced_tea", "Synthetic lunch", h["price"], 1, "2026-09-14")
        items = main.cart_items(1)
        self.assertEqual(items[0]["drink_code"], "iced_tea")
        oid = self.create(items=items, clear=True)[0]
        main.confirm_payment(oid, 900)
        self.assertIn("Айс-ти", str(main.get_kitchen_summary()))
        main.update_cart(1, f"lunch_mon_{h['id']}_g1_skeep_iced_tea", "Synthetic lunch", h["price"], 6, "2026-09-14")
        with self.assertRaises(OrderError):
            main.cart_items(1)
        with self.assertRaises(OrderError):
            normalize([dict(items[0], quantity=6)])

    def test_quantity_types_and_duplicate_rows(self):
        for value in [True, "2", 1.5, 0, -1]:
            with self.subTest(value=value), self.assertRaises(OrderError):
                normalize([dict(self.items[0], quantity=value)])
        with self.assertRaises(OrderError):
            normalize([dict(self.items[0], quantity=3), dict(self.items[0], quantity=3)])
        self.assertEqual(normalize([self.items[0], self.items[0]])[0]["quantity"], 2)

    def test_dates_times_and_pause(self):
        now = main.local_now()
        for date, time in [("2026-09-14", "10:00"), ("2026-09-28", "20:00"), ("2026-09-15", "09:00"), ("2026-09-14", "Сейчас (В очереди)")]:
            validate_schedule(date, time, now)
        for date, time in [("2026-09-13", "12:00"), ("2026-09-19", "12:00"), ("2026-09-29", "12:00"), ("2026-09-14", "09:59"), ("2026-09-15", "20:01"), ("2026-09-15", "08:59"), ("2026-09-15", "Сейчас (В очереди)"), ("2026-09-14", "16:00–17:00")]:
            with self.subTest(date=date, time=time), self.assertRaises(OrderError):
                validate_schedule(date, time, now)
        validate_schedule("2026-09-14", "16:00–17:00", now.replace(hour=16))
        with self.assertRaises(OrderError):
            validate_schedule("2026-09-14", "16:00–17:00", now.replace(hour=17))
        main.set_menu_active(False)
        with self.assertRaises(OrderError):
            self.create()

    def test_catalog_price_change_and_unavailable(self):
        self.sql("UPDATE menu_items SET price=40000 WHERE name='Омлет'")
        with self.assertRaises(OrderError):
            main.create_order(1, "old", 35000, "12:00", "2026-09-14", "old", source_items=self.items, request_hash="digest")
        self.sql("DELETE FROM menu_items WHERE name='Омлет'")
        with self.assertRaises(OrderError):
            self.create()

    def test_backup_restore(self):
        self.create()
        copy = Path(self.temp.name) / "backup.db"
        restored = Path(self.temp.name) / "restored.db"
        backup(self.db, copy)
        backup(copy, restored)
        with closing(sqlite3.connect(restored)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM orders").fetchone()[0], 1)
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        with self.assertRaises(FileExistsError):
            backup(self.db, copy)

    def test_resend_after_delivery_failure(self):
        oid = self.create()[0]
        bot = SimpleNamespace(get_me=AsyncMock(return_value=SimpleNamespace(username="synthetic_bot")), send_photo=AsyncMock(side_effect=RuntimeError("synthetic")), send_message=AsyncMock(side_effect=RuntimeError("synthetic")))
        context = SimpleNamespace(bot=bot)
        with self.assertRaises(RuntimeError):
            asyncio.run(main.resend_order(context, 1, main.get_order(oid)))
        bot.send_message.side_effect = None
        asyncio.run(main.resend_order(context, 1, main.get_order(oid)))
        self.assertEqual(len(self.sql("SELECT order_id FROM orders")), 1)
        self.assertIn("reply_markup", bot.send_message.call_args.kwargs)

    def test_payload_must_be_object(self):
        for payload in [[], None, 1, "text"]:
            message = SimpleNamespace(web_app_data=SimpleNamespace(data=json.dumps(payload)), reply_text=AsyncMock())
            update = SimpleNamespace(effective_message=message, effective_user=SimpleNamespace(id=1), update_id=123)
            asyncio.run(main.handle_web_app_data(update, SimpleNamespace()))
            message.reply_text.assert_awaited_once()

    def test_database_path(self):
        self.assertEqual(database_path(self.db), self.db)
        self.assertEqual(Path(database_path("a.db", self.temp.name)), Path(self.temp.name) / "a.db")

    def test_old_button_redirects_after_restart_and_pause(self):
        self.create()
        main.set_menu_active(False)
        message = SimpleNamespace(message_id=1, reply_text=AsyncMock())
        q = SimpleNamespace(data="confirm_order:test_request", from_user=SimpleNamespace(id=1), message=message, answer=AsyncMock())
        update = SimpleNamespace(callback_query=q, update_id=1, effective_chat=SimpleNamespace(type="private"), effective_user=SimpleNamespace(id=1))
        asyncio.run(main.btn(update, SimpleNamespace(user_data={})))
        self.assertIn("Mini App", message.reply_text.call_args.args[0])
        self.assertEqual(len(self.sql("SELECT order_id FROM orders")), 1)

    def test_manual_lifecycle_calls_post_init(self):
        calls = []
        app = MagicMock()
        app.initialize = AsyncMock(side_effect=lambda: calls.append("initialize"))
        app.post_init = AsyncMock(side_effect=lambda app: calls.append("post_init"))
        app.start = AsyncMock(side_effect=lambda: calls.append("start"))
        app.stop = AsyncMock()
        app.shutdown = AsyncMock()
        app.updater.start_polling = AsyncMock()
        app.updater.stop = AsyncMock()
        runner = SimpleNamespace(setup=AsyncMock(), cleanup=AsyncMock())
        site = SimpleNamespace(start=AsyncMock())
        event = SimpleNamespace(wait=AsyncMock(side_effect=asyncio.CancelledError))
        builder = MagicMock()
        builder.token.return_value.post_init.return_value.build.return_value = app
        with patch.object(main, "TOKEN", "synthetic"), patch.object(main, "init_db"), patch.object(main.Application, "builder", return_value=builder), patch.object(main.web, "AppRunner", return_value=runner), patch.object(main.web, "TCPSite", return_value=site), patch.object(main.asyncio, "Event", return_value=event):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(main.main())
        self.assertEqual(calls, ["initialize", "post_init", "start"])
        app.shutdown.assert_awaited_once()

    def test_total_limits(self):
        other = dict(self.items[0], item_name="Овсяная каша", quantity=5)
        main.server_quote([dict(self.items[0], quantity=5), other], "2026-09-14", "12:00")
        with self.assertRaises(OrderError):
            normalize([dict(self.items[0], quantity=5), other, dict(self.items[0], item_name="Гренки 4 шт", quantity=1)])
        self.sql("UPDATE menu_items SET price=400000 WHERE name='Омлет'")
        self.assertEqual(main.server_quote([dict(self.items[0], quantity=5)], "2026-09-14", "12:00")[0], 2000000)
        self.sql("UPDATE menu_items SET price=400001 WHERE name='Омлет'")
        with self.assertRaises(OrderError):
            main.server_quote([dict(self.items[0], quantity=5)], "2026-09-14", "12:00")

    def test_legacy_send_data_never_creates_order(self):
        payload = dict(type="miniapp_order", version=2, request_token="synthetic_request", pickup_date="2026-09-14", pickup_time="12:00", items=self.items)
        message = SimpleNamespace(web_app_data=SimpleNamespace(data=json.dumps(payload)), reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message, effective_user=SimpleNamespace(id=1), update_id=123)
        asyncio.run(main.handle_web_app_data(update, SimpleNamespace()))
        self.assertEqual(len(self.sql("SELECT order_id FROM orders")), 0)

    def test_api_catalog_is_database_catalog(self):
        data = catalog(main)
        self.assertEqual({(p["categoryId"], p["name"], p["price"]) for p in data["products"]}, {(r[0], r[1], r[3]) for r in main.DEFAULT_ITEMS})
        self.sql("UPDATE menu_items SET price=12345 WHERE name='Омлет'")
        changed = catalog(main)
        self.assertEqual(next(p["price"] for p in changed["products"] if p["name"] == "Омлет"), 12345)
        self.assertNotIn("const menu: DayMenu[]", Path("miniapp/app/page.tsx").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
