"""Shared, side-effect-free order validation for both entry points."""
import hashlib
import json
from datetime import datetime, time, timedelta


class OrderError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def fail(code):
    messages = {
        "date": "Дата недоступна. Выберите будний день в ближайшие 14 дней.",
        "time": "Время прошло или недоступно. Выдача с 09:00 до 20:00.",
        "limit": "Превышен лимит: 5 единиц позиции, 10 в заказе, 2 000 000 сум.",
        "unavailable": "Блюдо больше недоступно. Откройте меню заново.",
        "stale": "Оформление устарело. Откройте корзину и подтвердите новый расчёт.",
        "paused": "Приём новых заказов приостановлен.",
        "conflict": "Этот запрос уже использован для другого заказа. Откройте меню заново.",
    }
    raise OrderError(code, messages[code])


def normalize(items):
    if not isinstance(items, list) or not items:
        fail("limit")
    merged = {}
    for item in items:
        if not isinstance(item, dict):
            fail("stale")
        qty = item.get("quantity")
        if type(qty) is not int or qty < 1:
            fail("limit")
        fields = ("day_id", "hot_name", "garnish", "drink_code", "with_salad") if item.get("item_type", "lunch") == "lunch" else ("category_id", "item_name")
        clean = {k: item.get(k) for k in fields}
        clean["item_type"] = item.get("item_type", "lunch")
        key = json.dumps(clean, sort_keys=True, ensure_ascii=False)
        if key not in merged:
            merged[key] = dict(clean, quantity=0)
        merged[key]["quantity"] += qty
    result = [merged[k] for k in sorted(merged)]
    if any(i["quantity"] > 5 for i in result) or sum(i["quantity"] for i in result) > 10:
        fail("limit")
    return result


def fingerprint(items, date, pickup, comment="", use_points=False):
    value = [normalize(items), date, pickup, comment, use_points]
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_schedule(date, pickup, now, active=True):
    if not active:
        fail("paused")
    try:
        day = datetime.strptime(date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        fail("date")
    if day.weekday() > 4 or not now.date() <= day <= now.date() + timedelta(days=14):
        fail("date")
    clock = now.time().replace(tzinfo=None)
    if pickup == "Сейчас (В очереди)":
        if day != now.date() or not time(9) <= clock < time(20):
            fail("time")
    elif pickup == "16:00–17:00":
        if day != now.date() or not time(16) <= clock < time(17):
            fail("time")
    else:
        try:
            selected = datetime.strptime(pickup, "%H:%M").time()
        except (TypeError, ValueError):
            fail("time")
        if not time(9) <= selected <= time(20) or (day == now.date() and selected < clock):
            fail("time")


def quote(items, date, pickup, now, active, get_items, get_lunch, drinks, built_in):
    validate_schedule(date, pickup, now, active)
    items = normalize(items)
    expected = ["mon", "tue", "wed", "thu", "fri"][datetime.strptime(date, "%Y-%m-%d").weekday()]
    components, names = [], []
    total = lunch_total = 0
    for item in items:
        qty = item["quantity"]
        if item["item_type"] == "menu_item":
            cat = item["category_id"]
            if cat not in {"breakfasts", "hot_drinks", "cold_drinks", "fresh_drinks"}:
                fail("unavailable")
            product = next((p for p in get_items(cat) if p["name"] == item["item_name"]), None)
            if not product:
                fail("unavailable")
            components.append(("fresh" if cat == "fresh_drinks" else "other", product["name"], qty, product["price"]))
            name = product["name"]
        elif item["item_type"] == "lunch":
            if item["day_id"] != expected or type(item["with_salad"]) is not bool:
                fail("unavailable")
            cfg, hot = get_lunch(expected)
            product = next((p for p in hot if p["name"] == item["hot_name"]), None)
            if not cfg or not product or item["drink_code"] not in drinks:
                fail("unavailable")
            garnish = item["garnish"]
            builtin = built_in(product["name"])
            if garnish not in ({"", "Гарнир уже в составе блюда"} if builtin else {cfg[f"garnish{i}"] for i in (1, 2, 3)}):
                fail("unavailable")
            components.append(("hot", product["name"], qty, product["price"]))
            opts = []
            for kind, value, enabled in [("garnish", garnish, not builtin), ("salad", cfg["salad"], item["with_salad"]), ("drink", drinks[item["drink_code"]], item["drink_code"] != "none")]:
                if enabled:
                    components.append((kind, value, qty, 0))
                    opts.append(value)
            name = " + ".join([product["name"], *opts])
            lunch_total += product["price"] * qty
        else:
            fail("unavailable")
        total += product["price"] * qty
        names.append(f"{name} x{qty}")
    if not 0 < total <= 2_000_000:
        fail("limit")
    if pickup == "16:00–17:00" and not lunch_total:
        fail("stale")
    discount = int(lunch_total * .2) if pickup == "16:00–17:00" else 0
    return total - discount, discount, components, ", ".join(names)
