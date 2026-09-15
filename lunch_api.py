"""Small authenticated API mounted in the polling bot's aiohttp application."""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import re
import time
import uuid
from contextlib import closing
from datetime import timedelta

from aiohttp import web
from order_rules import OrderError, fail, fingerprint, normalize
from order_storage import existing_order
from order_lifecycle import PAYMENT_LABELS, ActionError
from telegram_auth import AuthError, verify_init_data


def clean_order(value):
    if not isinstance(value, dict):
        fail("stale")
    comment = value.get("comment", "")
    use_points = value.get("use_points", False)
    if not isinstance(comment, str) or len(comment) > 300 or type(use_points) is not bool:
        fail("stale")
    return dict(items=normalize(value.get("items")), pickup_date=value.get("pickup_date"),
                pickup_time=value.get("pickup_time"), comment=comment.strip(), use_points=use_points)


def order_digest(value):
    return fingerprint(value["items"], value["pickup_date"], value["pickup_time"], value["comment"], value["use_points"])


def sign_quote(data, secret):
    encoded = base64.urlsafe_b64encode(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).decode()
    sig = hmac.new(secret.encode(), ("quote:" + encoded).encode(), hashlib.sha256).hexdigest()
    return encoded + "." + sig


def read_quote(token, secret, user_id, digest):
    try:
        encoded, sig = token.split(".")
        expected = hmac.new(secret.encode(), ("quote:" + encoded).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            fail("stale")
        data = json.loads(base64.urlsafe_b64decode(encoded))
        if data["user"] != user_id or data["digest"] != digest or data["expires"] < time.time():
            fail("stale")
        return data
    except (ValueError, TypeError, KeyError, AttributeError):
        fail("stale")


def public_order(row):
    keys = ("order_id", "items", "total", "status", "payment_status", "pickup_date", "pickup_time", "comment", "points_used", "points_earned")
    result = {key: row[key] for key in keys}
    if result["status"] == "paid":
        result["status"] = "new"  # Legacy preparation alias, not proof of payment.
    return result | {"payment_label": PAYMENT_LABELS.get(row["payment_status"], "Нужна проверка")}


def catalog(runtime):
    days = []
    for index, (day_id, label) in runtime.WEEKDAYS.items():
        cfg, hot = runtime.get_lunch_config(day_id)
        if not cfg:
            continue
        days.append(dict(id=day_id, short=["Пн", "Вт", "Ср", "Чт", "Пт"][index], label=label,
                         salad=cfg["salad"], garnishes=[cfg[f"garnish{i}"] for i in (1, 2, 3)],
                         meals=[dict(id=f"lunch-{h['id']}", name=h["name"], description=h["description"] or "", price=h["price"],
                                     image=media_url(h["image"]), builtInGarnish=runtime.hot_has_built_in_garnish(h["name"])) for h in hot]))
    products = []
    for category in ("breakfasts", "hot_drinks", "cold_drinks", "fresh_drinks"):
        for p in runtime.get_items(category):
            products.append(dict(id=f"item-{p['id']}", categoryId=category, name=p["name"], backendName=p["name"],
                                 description=p["description"] or "", price=p["price"], emoji="🍳" if category == "breakfasts" else "🥤",
                                 tone="amber" if category == "breakfasts" else "sky"))
    now = runtime.local_now()
    dates = [(now.date() + timedelta(days=i)).isoformat() for i in range(15) if (now.date() + timedelta(days=i)).weekday() < 5]
    return dict(menu=days, products=products, active=runtime.menu_is_active(), now=now.isoformat(), dates=dates,
                rules=dict(max_per_item=5, max_quantity=10, max_total=2000000, opens="09:00", closes="20:00"),
                bot_username=runtime.BOT_USERNAME, drinks=runtime.LUNCH_DRINKS)


def media_url(path):
    if str(path or "").startswith(("https://", "http://")):
        return path
    if str(path or "").replace("\\", "/").startswith("assets/") and ".." not in path:
        return "/media/" + str(path).replace("\\", "/")[7:]
    return ""


def create_app(runtime, bot=None):
    origins = set(runtime.API_ALLOWED_ORIGINS)
    tasks = set()

    @web.middleware
    async def boundary(request, handler):
        request_id = uuid.uuid4().hex[:16]
        origin = request.headers.get("Origin")
        if origin and origin not in origins:
            return web.json_response({"code": "origin", "message": "Этот адрес приложения не разрешён."}, status=403)
        try:
            response = web.Response(status=204) if request.method == "OPTIONS" else await handler(request)
        except AuthError as error:
            response = web.json_response({"code": "auth", "message": str(error)}, status=401)
        except (OrderError, ActionError) as error:
            code = getattr(error, "code", "action")
            logging.warning("api_rejected reason=%s request_id=%s", code, request_id)
            response = web.json_response({"code": code, "message": str(error)}, status=409 if code in {"stale", "conflict"} else 400)
        except web.HTTPException as error:
            response = web.json_response({"code": "request", "message": "Запрос недоступен."}, status=error.status)
        except (ValueError, TypeError, KeyError):
            response = web.json_response({"code": "format", "message": "Проверьте состав заказа."}, status=400)
        except Exception as error:
            logging.error("api_failed type=%s request_id=%s", type(error).__name__, request_id)
            response = web.json_response({"code": "server", "message": "Не удалось получить ответ. Повторите запрос с тем же номером."}, status=500)
        if origin:
            response.headers.update({"Access-Control-Allow-Origin": origin, "Vary": "Origin", "Access-Control-Allow-Headers": "Content-Type, Authorization", "Access-Control-Allow-Methods": "GET, POST, PUT, OPTIONS"})
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = request_id
        return response

    app = web.Application(middlewares=[boundary], client_max_size=32768)

    def identity(request):
        value = request.headers.get("Authorization", "")
        return verify_init_data(value[4:] if value.startswith("tma ") else "", runtime.TOKEN, runtime.INIT_DATA_MAX_AGE)

    def registered(request):
        user_id = identity(request)
        if not runtime.get_user(user_id):
            raise web.HTTPForbidden()
        return user_id

    def owned(request):
        user_id = identity(request)
        row = runtime.get_order(int(request.match_info["order_id"]))
        if not row or row["user_id"] != user_id:
            raise web.HTTPNotFound()
        return user_id, row

    def dispatch(order_id, owner_notice=False):
        if bot is None:
            return
        async def send():
            try:
                await asyncio.wait_for(runtime.notify_saved_order(bot, order_id, owner_notice), timeout=10)
            except Exception as error:
                logging.warning("order_notification_failed order_id=%s type=%s", order_id, type(error).__name__)
        task = asyncio.create_task(send())
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    async def cleanup(app):
        for task in list(tasks):
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    app.on_cleanup.append(cleanup)

    async def get_catalog(request):
        return web.json_response(catalog(runtime))

    async def me(request):
        user_id = identity(request)
        account_key = hmac.new(runtime.TOKEN.encode(), f"local-account:{user_id}".encode(), hashlib.sha256).hexdigest()[:24]
        return web.json_response(dict(registered=bool(runtime.get_user(user_id)), balance=runtime.get_points_balance(user_id), account_key=account_key))

    async def draft(request):
        user_id = registered(request)
        with closing(runtime._conn()) as conn, conn:
            if request.method == "PUT":
                value = await request.json()
                if not isinstance(value, dict):
                    fail("stale")
                # An empty or expired draft is allowed; checkout will validate its date.
                if value.get("items") == []:
                    conn.execute("DELETE FROM drafts WHERE user_id=?", (user_id,))
                    return web.json_response({"draft": None})
                value = clean_order(value)
                conn.execute("INSERT INTO drafts(user_id,payload,updated_at) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at", (user_id, json.dumps(value), runtime.local_now().isoformat()))
                return web.json_response({"draft": value})
            row = conn.execute("SELECT payload FROM drafts WHERE user_id=?", (user_id,)).fetchone()
            return web.json_response({"draft": json.loads(row[0]) if row else None})

    def calculate(user_id, value):
        base, discount, components, description = runtime.server_quote(value["items"], value["pickup_date"], value["pickup_time"])
        balance = runtime.get_points_balance(user_id)
        maximum = min(balance, int(base * .3))
        points = maximum if value["use_points"] else 0
        signed = dict(user=user_id, digest=order_digest(value), total=base-points, points=points, expires=int(time.time())+300)
        return dict(subtotal=base+discount, discount=discount, balance=balance, max_points=maximum, points_used=points, total=base-points,
                    description=description, quote_token=sign_quote(signed, runtime.TOKEN))

    async def quote(request):
        user_id = registered(request)
        return web.json_response(calculate(user_id, clean_order(await request.json())))

    async def orders(request):
        user_id = registered(request)
        if request.method == "GET":
            with closing(runtime._conn()) as conn:
                rows = conn.execute("SELECT * FROM orders WHERE user_id=? ORDER BY order_id DESC LIMIT 30", (user_id,)).fetchall()
            return web.json_response({"orders": [public_order(r) for r in rows]})
        raw = await request.json()
        value = clean_order(raw)
        token = raw.get("request_token")
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", token):
            fail("stale")
        token = f"api:{user_id}:{token}"
        digest = order_digest(value)
        existing = existing_order(runtime._conn, token, digest, user_id)
        if existing:
            return web.json_response({"order": public_order(existing), "created": False})
        try:
            checked = read_quote(raw.get("quote_token"), runtime.TOKEN, user_id, digest)
            result = runtime.create_order(user_id, "", checked["total"], value["pickup_time"], value["pickup_date"], token,
                comment=value["comment"], points_used=checked["points"], source_items=value["items"], request_hash=digest)
        except OrderError as error:
            if error.code != "stale":
                raise
            return web.json_response({"code": "stale", "message": "Расчёт изменился. Проверьте новую сумму и подтвердите ещё раз.", "quote": calculate(user_id, value)}, status=409)
        row = runtime.get_order(result[0])
        dispatch(row["order_id"], result[-1])
        return web.json_response({"order": public_order(row), "created": result[-1]}, status=201 if result[-1] else 200)

    async def detail(request):
        _, row = owned(request)
        return web.json_response({"order": public_order(row)})

    async def by_request(request):
        user_id = identity(request)
        token = request.match_info["token"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", token):
            raise web.HTTPNotFound()
        with closing(runtime._conn()) as conn:
            row = conn.execute("SELECT * FROM orders WHERE request_token=? AND user_id=?", (f"api:{user_id}:{token}", user_id)).fetchone()
        if not row:
            raise web.HTTPNotFound()
        return web.json_response({"order": public_order(row)})

    async def report_paid(request):
        user_id, row = owned(request)
        if runtime.report_payment(row["order_id"], user_id):
            dispatch(row["order_id"], True)
        return web.json_response({"order": public_order(runtime.get_order(row["order_id"]))})

    async def resend(request):
        _, row = owned(request)
        dispatch(row["order_id"])
        return web.json_response({"queued": True}, status=202)

    app.router.add_get("/api/catalog", get_catalog)
    app.router.add_get("/api/me", me)
    app.router.add_get("/api/draft", draft)
    app.router.add_put("/api/draft", draft)
    app.router.add_post("/api/quote", quote)
    app.router.add_get("/api/orders", orders)
    app.router.add_post("/api/orders", orders)
    app.router.add_get("/api/orders/{order_id}", detail)
    app.router.add_get("/api/orders/by-request/{token}", by_request)
    app.router.add_post("/api/orders/{order_id}/paid", report_paid)
    app.router.add_post("/api/orders/{order_id}/resend", resend)
    app.router.add_get("/", runtime.health)
    app.router.add_static("/media/", runtime.BASE_DIR / "assets", show_index=False)
    return app
