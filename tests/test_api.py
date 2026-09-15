import asyncio
import hashlib
import hmac
import json
import sqlite3
import time
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode

from aiohttp.test_utils import TestClient, TestServer
import main
import bot_workflows
from lunch_api import create_app
from order_lifecycle import ActionError
from telegram_auth import AuthError, verify_init_data
import test_orders

SECRET = "synthetic-test-token"


def signed(user_id=1, age=0, **extra):
    data = dict(auth_date=str(int(time.time()) - age), user=json.dumps({"id": user_id}), **extra)
    key = hmac.new(b"WebAppData", SECRET.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(key, "\n".join(f"{k}={data[k]}" for k in sorted(data)).encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


class Auth(unittest.TestCase):
    def test_signature_age_tampering_and_duplicates(self):
        self.assertEqual(verify_init_data(signed(), SECRET), 1)
        self.assertEqual(verify_init_data(signed(signature="signed-extra-field"), SECRET), 1)
        for raw in ["", signed(age=3601), signed(age=-100), signed().replace("user=", "receiver="), signed() + "&auth_date=1"]:
            with self.subTest(case=raw[:0]), self.assertRaises(AuthError):
                verify_init_data(raw, SECRET)
        with self.assertRaises(AuthError):
            verify_init_data(signed(), "different-secret")


class TelegramWebhook(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot_app = SimpleNamespace(bot=SimpleNamespace(), process_update=AsyncMock())
        app = __import__("aiohttp").web.Application()
        main.add_telegram_webhook(app, self.bot_app, "synthetic_webhook_secret")
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_rejects_missing_secret_and_accepts_telegram_update(self):
        payload = {"update_id": 123456}
        response = await self.client.post("/api/telegram/webhook", json=payload)
        self.assertEqual(response.status, 401)
        response = await self.client.post(
            "/api/telegram/webhook",
            json=payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": "synthetic_webhook_secret"},
        )
        self.assertEqual(response.status, 200)
        self.bot_app.process_update.assert_awaited_once()


class API(unittest.IsolatedAsyncioTestCase):
    sql = test_orders.Orders.sql
    create = test_orders.Orders.create

    def setUp(self):
        test_orders.Orders.setUp(self)
        for p in [patch.object(main, "TOKEN", SECRET), patch.object(main, "API_ALLOWED_ORIGINS", ["https://mini.example"]), patch.object(main, "BOT_USERNAME", "synthetic_bot")]:
            p.start(); self.addCleanup(p.stop)

    async def asyncSetUp(self):
        self.client = TestClient(TestServer(create_app(main)))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def request(self, path, method="GET", value=None, user=1):
        return await self.client.request(method, path, json=value, headers={"Authorization": "tma " + signed(user)})

    def draft(self, **changes):
        return dict(items=self.items, pickup_date="2026-09-14", pickup_time="12:00", comment="Synthetic comment", use_points=True) | changes

    async def place(self, token="synthetic_order"):
        value = self.draft()
        response = await self.request("/api/quote", "POST", value)
        quote = await response.json()
        response = await self.request("/api/orders", "POST", value | dict(request_token=token, quote_token=quote["quote_token"]))
        self.assertEqual(response.status, 201)
        return await response.json(), value | dict(request_token=token, quote_token=quote["quote_token"])

    async def test_public_catalog_protected_data_and_cors(self):
        response = await self.client.get("/api/catalog")
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())["menu"][0]["meals"][0]["price"], 63000)
        self.assertEqual((await self.client.get("/api/me")).status, 401)
        self.assertEqual((await self.client.get("/api/catalog", headers={"Origin": "https://evil.example"})).status, 403)
        response = await self.client.options("/api/orders", headers={"Origin": "https://mini.example"})
        self.assertEqual(response.status, 204)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "https://mini.example")
        self.assertNotIn("Access-Control-Allow-Credentials", response.headers)

    async def test_bot_home_exposes_registration_orders_cart_and_bonuses(self):
        labels = [button.text for row in bot_workflows.home(main).inline_keyboard for button in row]
        self.assertIn("🍽 Открыть меню", labels)
        self.assertIn("📋 Мои заказы", labels)
        self.assertIn("🛒 Корзина", labels)
        self.assertIn("⭐ Мои бонусы", labels)
        contact = bot_workflows.contact_keyboard().keyboard[0][0]
        self.assertTrue(contact.request_contact)
        message = SimpleNamespace(reply_text=AsyncMock())
        await bot_workflows.show_bonuses(main, message, 1)
        self.assertIn("Баланс:", message.reply_text.await_args.args[0])

    async def test_registration_draft_and_real_balance(self):
        self.sql("DELETE FROM users WHERE user_id=1")
        self.assertFalse((await (await self.request("/api/me")).json())["registered"])
        self.assertEqual((await self.request("/api/orders", "POST", self.draft())).status, 403)
        # Native contact from the same Telegram account registers without touching a draft.
        message = SimpleNamespace(contact=SimpleNamespace(user_id=1, phone_number="synthetic-phone"), reply_text=AsyncMock())
        update = SimpleNamespace(message=message, effective_user=SimpleNamespace(id=1), effective_chat=SimpleNamespace(type="private"))
        context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()), user_data={})
        await main.handle_contact(update, context)
        self.assertEqual((await self.request("/api/draft", "PUT", self.draft())).status, 200)
        restored = await (await self.request("/api/draft")).json()
        self.assertEqual(restored["draft"], self.draft())
        quote = await (await self.request("/api/quote", "POST", self.draft())).json()
        self.assertEqual((quote["balance"], quote["points_used"], quote["total"]), (0, 0, 35000))
        self.sql("UPDATE users SET balance=2000")
        quote = await (await self.request("/api/quote", "POST", self.draft() | {"balance": 9999999, "price": 1})).json()
        self.assertEqual((quote["points_used"], quote["total"]), (2000, 33000))

    async def test_replay_after_lost_response_uses_saved_order(self):
        first, payload = await self.place()
        self.sql("DELETE FROM menu_items")
        main.set_menu_active(False)
        response = await self.request("/api/orders", "POST", payload | {"quote_token": "expired"})
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())["order"], first["order"])
        self.assertEqual(main.get_points_balance(1), 0)
        conflict = await self.request("/api/orders", "POST", payload | {"comment": "Different composition"})
        self.assertEqual(conflict.status, 409)
        recovered = await self.request("/api/orders/by-request/synthetic_order")
        self.assertEqual((await recovered.json())["order"], first["order"])
        self.assertEqual((await self.request("/api/orders/by-request/synthetic_order", user=2)).status, 404)

    async def test_amount_changes_require_explicit_reconfirmation(self):
        value = self.draft()
        before = await (await self.request("/api/quote", "POST", value)).json()
        self.sql("UPDATE users SET balance=1000")
        payload = value | dict(request_token="synthetic_quote", quote_token=before["quote_token"])
        response = await self.request("/api/orders", "POST", payload)
        self.assertEqual(response.status, 409)
        updated = await response.json()
        self.assertEqual(updated["quote"]["total"], 34000)
        self.assertFalse(self.sql("SELECT order_id FROM orders"))
        response = await self.request("/api/orders", "POST", payload | {"quote_token": updated["quote"]["quote_token"]})
        self.assertEqual(response.status, 201)

    async def test_other_user_cannot_read_report_or_resend(self):
        result, _ = await self.place()
        oid = result["order"]["order_id"]
        for suffix, method in [("", "GET"), ("/paid", "POST"), ("/resend", "POST")]:
            response = await self.request(f"/api/orders/{oid}{suffix}", method, user=2)
            self.assertEqual(response.status, 404)
        self.assertNotIn("qr_token", result["order"])
        self.assertNotIn("user_id", result["order"])

    async def test_client_paid_is_only_a_report(self):
        result, _ = await self.place()
        oid = result["order"]["order_id"]
        response = await self.request(f"/api/orders/{oid}/paid", "POST")
        self.assertEqual((await response.json())["order"]["payment_status"], "review")
        self.assertIsNone(main.get_order(oid)["payment_confirmed_by"])
        self.assertFalse(main.get_kitchen_summary())

    async def test_notification_failure_does_not_fail_api_or_rollback(self):
        await self.client.close()
        with patch.object(main, "notify_saved_order", new_callable=AsyncMock, side_effect=RuntimeError("synthetic")) as notify:
            self.client = TestClient(TestServer(create_app(main, bot=object())))
            await self.client.start_server()
            result, payload = await self.place()
            await asyncio.sleep(.01)
            self.assertTrue(notify.called)
            repeat = await self.request("/api/orders", "POST", payload)
            self.assertEqual((await repeat.json())["order"]["order_id"], result["order"]["order_id"])
            self.assertEqual(len(self.sql("SELECT order_id FROM orders")), 1)

    async def test_draft_cleared_atomically(self):
        await self.request("/api/draft", "PUT", self.draft())
        await self.place()
        self.assertIsNone((await (await self.request("/api/draft")).json())["draft"])

    async def test_roles_payment_kitchen_qr_and_delivery(self):
        oid = self.create(points=5000)[0]
        for actor in (1, 901):
            with self.assertRaises(ActionError):
                main.confirm_payment(oid, actor)
        with self.assertRaises(ActionError):
            main.set_order_status(oid, "cooking", 901)
        main.confirm_payment(oid, 900)
        self.assertFalse(main.confirm_payment(oid, 900))
        row = main.get_order(oid)
        self.assertEqual(row["payment_confirmed_by"], 900)
        self.assertIsNotNone(row["payment_confirmed_at"])
        self.assertTrue(main.get_kitchen_summary())
        with self.assertRaises(ActionError):
            main.set_order_status(oid, "delivered", 901)
        main.set_order_status(oid, "cooking", 901)
        main.set_order_status(oid, "ready", 901)
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_user=SimpleNamespace(id=901), effective_chat=SimpleNamespace(type="private"), message=message)
        await main.cmd_start(update, SimpleNamespace(args=["pickup_" + row["qr_token"]]))
        self.assertEqual(main.get_order(oid)["status"], "ready")
        self.assertEqual(main.get_points_balance(1), 5000)
        main.set_order_status(oid, "delivered", 901)
        self.assertFalse(main.set_order_status(oid, "delivered", 901))
        self.assertEqual(main.get_points_balance(1), 6500)

    async def test_cancellation_refund_and_kitchen_privacy(self):
        oid = self.create(points=5000)[0]
        main.confirm_payment(oid, 900)
        with self.assertRaises(ActionError):
            main.set_order_status(oid, "cancelled", 901)
        main.set_order_status(oid, "cancelled", 900)
        main.set_order_status(oid, "cancelled", 900)
        self.assertEqual(main.get_points_balance(1), 10000)
        self.assertIn("ручной возврат", bot_workflows.card(main, main.get_order(oid)))
        for callback in ("adm_export", "adm_broadcast", "adm_payments", "payment_confirm:1"):
            q = SimpleNamespace(data=callback, from_user=SimpleNamespace(id=901), answer=AsyncMock(), message=SimpleNamespace(message_id=1, reply_text=AsyncMock()))
            update = SimpleNamespace(effective_user=SimpleNamespace(id=901), effective_chat=SimpleNamespace(type="private"), callback_query=q)
            await main.btn(update, SimpleNamespace(user_data={}))
            self.assertTrue(q.answer.call_args.kwargs.get("show_alert"))
            q.message.reply_text.assert_not_called()

    async def test_qr_only_sent_after_confirmed_payment(self):
        oid = self.create()[0]
        bot = SimpleNamespace(send_message=AsyncMock(), send_photo=AsyncMock(), get_me=AsyncMock(return_value=SimpleNamespace(username="synthetic_bot")))
        await bot_workflows.send_customer(main, bot, main.get_order(oid))
        bot.send_photo.assert_not_called()
        main.confirm_payment(oid, 900)
        await bot_workflows.send_customer(main, bot, main.get_order(oid))
        bot.send_photo.assert_awaited_once()

    async def test_old_schema_migration_does_not_infer_payment(self):
        legacy = str(Path(self.temp.name) / "legacy.db")
        with closing(sqlite3.connect(legacy)) as conn, conn:
            conn.execute("CREATE TABLE orders(order_id INTEGER PRIMARY KEY,user_id INTEGER,items TEXT,total INTEGER,status TEXT,pickup_time TEXT,created_at TEXT,discount_amount INTEGER DEFAULT 0)")
            for index, status in enumerate(["new", "paid", "cooking", "ready", "delivered"], 1):
                conn.execute("INSERT INTO orders(order_id,user_id,items,total,status,created_at) VALUES (?,?,?,100,?,'2026-09-14 10:00:00')", (index, 1, "Synthetic", status))
        with patch.object(main, "DB_NAME", legacy):
            main.init_db()
            main.init_db()
            rows = self.sql("SELECT status,payment_status,payment_confirmed_by,rewards_applied FROM orders ORDER BY order_id")
            self.assertEqual([r[0] for r in rows], ["new", "paid", "cooking", "ready", "delivered"])
            self.assertTrue(all(r[1] == "legacy_unknown" and r[2] is None and r[3] == 1 for r in rows))
