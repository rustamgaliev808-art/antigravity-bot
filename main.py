import os
import logging
import asyncio
import sqlite3
import csv
import secrets
import html
import json
import re
from io import BytesIO, StringIO
from pathlib import Path
from urllib.parse import quote, urlencode
from datetime import datetime, time as t_time, timedelta, timezone
from aiohttp import web
import qrcode
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    InputMediaPhoto,
    KeyboardButton,
    WebAppInfo,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ============================================================
# CONFIG
# ============================================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# httpx пишет полный URL Telegram Bot API, содержащий секретный токен.
# Оставляем для сетевых библиотек только предупреждения и ошибки.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel")
MINIAPP_URL = os.getenv(
    "MINIAPP_URL",
    "https://click-lunch-tashkent.click-ai-c-l-0087.chatgpt.site",
).strip()
_order_channel_id = os.getenv("ORDER_CHANNEL_ID", "").strip()
ORDER_CHANNEL_ID = (
    int(_order_channel_id)
    if _order_channel_id.lstrip("-").isdigit()
    else _order_channel_id
)
TZ_OFFSET = int(os.getenv("TZ_OFFSET", "5"))
CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID", "52528").strip()
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "20421").strip()

DB_NAME = os.getenv("DB_NAME", "click_lunch_v6.db")

BASE_DIR = Path(__file__).resolve().parent


def asset_path(*parts):
    """Возвращает переносимый относительный путь к файлу проекта."""
    return str(Path("assets").joinpath(*parts))


WEEK_POSTERS = {
    "mon": asset_path("posts", "monday-menu-poster-v3-ai.png"),
    "tue": asset_path("posts", "tuesday-menu-poster-ai.png"),
    "wed": asset_path("posts", "wednesday-menu-poster-ai.png"),
    "thu": asset_path("posts", "thursday-menu-poster-ai.png"),
    "fri": asset_path("posts", "friday-menu-poster-ai.png"),
}

MAIN_BANNER = "https://images.unsplash.com/photo-1498837167922-41cfa6f318ba?q=80&w=1200&auto=format&fit=crop"
CART_BANNER = "https://images.unsplash.com/photo-1556742044-3c52d6e88c62?q=80&w=1200&auto=format&fit=crop"
LUNCH_BANNER = "https://images.unsplash.com/photo-1543339308-43e59d6b73a6?q=80&w=1200&auto=format&fit=crop"
MON_BANNER = WEEK_POSTERS["mon"]

WEEKDAYS = {
    0: ("mon", "Понедельник"),
    1: ("tue", "Вторник"),
    2: ("wed", "Среда"),
    3: ("thu", "Четверг"),
    4: ("fri", "Пятница"),
}

LUNCH_CAT_IDS = {"mon", "tue", "wed", "thu", "fri"}

# Напиток выбирается отдельно для каждого комплексного обеда.
LUNCH_DRINKS = {
    "sherbet": "Шербет",
    "iced_tea": "Айс-ти",
    "none": "Без напитка",
}
POINTS_RATE = 0.05
POINTS_MAX_USE_RATE = 0.30

ORDER_STATUSES = {
    "new": "🆕 Принят",
    "paid": "💳 Оплачен",
    "cooking": "👨‍🍳 Готовится",
    "ready": "✅ Готов к выдаче",
    "delivered": "🎉 Выдан",
    "cancelled": "❌ Отменён",
}

NEXT_ORDER_STATUS = {
    "new": "cooking",
    "paid": "cooking",  # Поддержка заказов, созданных старой версией.
    "cooking": "ready",
    "ready": "delivered",
}

# ============================================================
# DEFAULT MENU
# ============================================================
DEFAULT_CATEGORIES = [
    ("breakfasts", "Завтраки", "https://images.unsplash.com/photo-1533089860892-a7c6f0a88666?q=80&w=1200&auto=format&fit=crop"),
    ("hot_drinks", "Горячие напитки", "https://images.unsplash.com/photo-1497935586351-b67a49e012bf?q=80&w=1200&auto=format&fit=crop"),
    ("cold_drinks", "Холодные напитки", "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?q=80&w=1200&auto=format&fit=crop"),
    ("fresh_drinks", "Фреши", "https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?q=80&w=1200&auto=format&fit=crop"),
    ("mon", "Понедельник", WEEK_POSTERS["mon"]),
    ("tue", "Вторник", WEEK_POSTERS["tue"]),
    ("wed", "Среда", WEEK_POSTERS["wed"]),
    ("thu", "Четверг", WEEK_POSTERS["thu"]),
    ("fri", "Пятница", WEEK_POSTERS["fri"]),
]

DEFAULT_ITEMS = [
    ("breakfasts", "Яичница с сосисками", "Классический сытный завтрак.", 40000, ""),
    ("breakfasts", "Омлет", "Пышный свежеприготовленный омлет.", 35000, ""),
    ("breakfasts", "Гренки 4 шт", "Золотистые поджаренные гренки.", 20000, ""),
    ("breakfasts", "Овсяная каша", "Вкусная и полезная каша.", 25000, ""),
    ("breakfasts", "Сэндвич с говядиной", "Сытный сэндвич с говядиной и сыром.", 32000, ""),

    ("hot_drinks", "☕ Американо", "Классический чёрный кофе.", 15000, ""),
    ("hot_drinks", "☕🥛 Капучино", "Эспрессо с молоком и пенкой.", 24000, ""),
    ("hot_drinks", "☕🥛 Латте", "Мягкий кофейный напиток.", 27000, ""),
    ("hot_drinks", "☕✨ Флэт Уайт", "Насыщенный кофе с микропенкой.", 24500, ""),

    ("cold_drinks", "🥤 Кола 0.25 / Zero", "Освежающая газировка.", 13000, ""),
    ("cold_drinks", "🍊 Fanta 0.25", "Апельсиновая газировка.", 12000, ""),
    ("cold_drinks", "🍹 Мохито", "Охлаждающий напиток.", 20000, ""),
    ("cold_drinks", "💧 Chortoq (с газом)", "Минеральная газированная вода.", 12000, ""),

    # Фреши — ровно 6 позиций.
    ("fresh_drinks", "🍎 Яблочный фреш", "Свежевыжатый яблочный сок, 250 мл.", 27000, ""),
    ("fresh_drinks", "🥕 Морковный фреш", "Свежевыжатый морковный сок, 250 мл.", 16000, ""),
    ("fresh_drinks", "❤️ Свекольный фреш", "Свежевыжатый свекольный сок, 250 мл.", 16000, ""),
    ("fresh_drinks", "🍎🥕 Яблоко + Морковь", "Микс яблочного и морковного сока, 250 мл.", 19000, ""),
    ("fresh_drinks", "🍎❤️ Яблоко + Свёкла", "Микс яблочного и свекольного сока, 250 мл.", 19000, ""),
    ("fresh_drinks", "🥒🍎 Огурец + Яблоко", "Освежающий микс огурца и яблока, 250 мл.", 26000, ""),
]

# Базовые горячие блюда по дням. Гарниры вынесены отдельно.
DEFAULT_LUNCH = {
    "mon": {
        "hot": [
            (
                "🥩", "Говядина с овощами",
                "Нежные кусочки говядины с болгарским перцем, морковью и луком в лёгком соусе.",
                63000, asset_path("menu", "monday", "beef-with-vegetables-ai.png"),
            ),
            (
                "🍗", "Куриный казан-кебаб",
                "Сочные кусочки курицы с румяной корочкой, луком и ароматными специями.",
                58000, asset_path("menu", "monday", "chicken-kazan-kebab-v2-ai.png"),
            ),
        ],
        "salad": "Витаминный салат",
        "salad_description": "Свежий хрустящий салат из капусты, моркови, огурца, сладкого перца и зелени.",
        "salad_image": asset_path("menu", "monday", "vitamin-salad-v2-ai.png"),
        "poster": WEEK_POSTERS["mon"],
        "drink": "Шербет или Айс-ти",
        "garnishes": ["Рис", "Гречка", "Картофель"],
    },
    "tue": {
        "hot": [
            (
                "🥩", "Жаркое из говядины",
                "Томлёная говядина с картофелем, морковью и луком в насыщенном соусе.",
                63000, asset_path("menu", "tuesday", "beef-pot-roast-ai.png"),
            ),
            (
                "🍗", "Куриные котлеты",
                "Сочные домашние котлеты из курицы с аппетитной румяной корочкой.",
                58000, asset_path("menu", "tuesday", "chicken-cutlets-ai.png"),
            ),
        ],
        "salad": "Французский салат",
        "salad_description": "Салат из свёклы, моркови, картофеля, огурца и яйца с лёгкой сливочной заправкой.",
        "salad_image": asset_path("menu", "tuesday", "french-salad-ai.png"),
        "poster": WEEK_POSTERS["tue"],
        "drink": "Шербет или Айс-ти",
        "garnishes": ["Перловка", "Пюре", "Рис"],
    },
    "wed": {
        "hot": [
            (
                "🥩", "Бефстроганов",
                "Нежные полоски говядины с луком и грибами в мягком сливочном соусе.",
                63000, asset_path("menu", "wednesday", "beef-stroganoff-ai.png"),
            ),
            (
                "🍗", "Куриная отбивная с сыром",
                "Сочная куриная отбивная с золотистой корочкой под расплавленным сыром.",
                58000, asset_path("menu", "wednesday", "chicken-cheese-cutlet-ai.png"),
            ),
        ],
        "salad": "Овощной салат",
        "salad_description": "Свежие помидоры, огурцы, сладкий перец, красный лук и зелень с лёгкой заправкой.",
        "salad_image": asset_path("menu", "wednesday", "vegetable-salad-ai.png"),
        "poster": WEEK_POSTERS["wed"],
        "drink": "Шербет или Айс-ти",
        "garnishes": ["Рис", "Гречка", "Картофель"],
    },
    "thu": {
        "hot": [
            (
                "🥩", "Плов из говядины",
                "Рассыпчатый рис с нежной говядиной, морковью, луком и ароматными специями.",
                63000, asset_path("menu", "thursday", "beef-plov-ai.png"),
            ),
            (
                "🍗", "Куриный Ган-пан",
                "Кусочки курицы со сладким перцем, морковью и луком в пикантном соусе.",
                58000, asset_path("menu", "thursday", "chicken-gan-pan-ai.png"),
            ),
        ],
        "salad": "Ачик-чучук",
        "salad_description": "Тонко нарезанные спелые помидоры и лук со свежей зеленью и чёрным перцем.",
        "salad_image": asset_path("menu", "thursday", "achik-chuchuk-ai.png"),
        "poster": WEEK_POSTERS["thu"],
        "drink": "Шербет или Айс-ти",
        "garnishes": ["Рис", "Пюре", "Овощи"],
    },
    "fri": {
        "hot": [
            (
                "🥩", "Гуляш из говядины",
                "Сытные кусочки говядины с луком и сладким перцем в густом томатном соусе.",
                63000, asset_path("menu", "friday", "beef-goulash-ai.png"),
            ),
            (
                "🍗", "Курица в соусе карри",
                "Нежные кусочки курицы в мягком золотистом соусе карри с луком.",
                58000, asset_path("menu", "friday", "chicken-curry-ai.png"),
            ),
        ],
        "salad": "Греческий салат",
        "salad_description": "Помидоры, огурцы, сладкий перец, красный лук, маслины и сыр фета.",
        "salad_image": asset_path("menu", "friday", "greek-salad-ai.png"),
        "poster": WEEK_POSTERS["fri"],
        "drink": "Шербет или Айс-ти",
        "garnishes": ["Рис", "Пюре", "Овощи печёные"],
    },
}

# ============================================================
# TIME / HELPERS
# ============================================================
def local_now():
    """Текущее локальное время приложения, не зависящее от TZ сервера."""
    app_tz = timezone(timedelta(hours=TZ_OFFSET))
    return datetime.now(app_tz)


def fmt(amount):
    return f"{amount:,}".replace(",", " ")


def get_click_payment_url(amount):
    query = urlencode({
        "service_id": CLICK_SERVICE_ID,
        "merchant_id": CLICK_MERCHANT_ID,
        "amount": int(max(0, amount)),
    })
    return f"https://my.click.uz/services/pay/?{query}"


def kb_click_payment(amount):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("💳 Оплатить через Click", url=get_click_payment_url(amount)),
    ]])


def esc(value):
    return html.escape(str(value or ""), quote=False)


def current_day():
    return WEEKDAYS.get(local_now().weekday(), ("mon", "Понедельник"))


def next_business_date():
    now = local_now()
    result = now.date()
    if now.weekday() >= 5 or now.time() >= t_time(17, 0):
        result += timedelta(days=1)
    while result.weekday() >= 5:
        result += timedelta(days=1)
    return result.isoformat()


def next_date_for_day(day_id):
    target_weekday = next((idx for idx, value in WEEKDAYS.items() if value[0] == day_id), None)
    if target_weekday is None:
        return None
    now = local_now()
    delta = (target_weekday - now.weekday()) % 7
    if delta == 0 and now.time() >= t_time(17, 0):
        delta = 7
    return (now.date() + timedelta(days=delta)).isoformat()


def display_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return value or "не указана"


def display_pickup_date(value):
    """Показывает дату выдачи с понятным клиенту днём недели."""
    try:
        pickup_day = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return display_date(value)
    if pickup_day == local_now().date():
        return f"Сегодня, {pickup_day.strftime('%d.%m.%Y')}"
    weekday_name = WEEKDAYS.get(pickup_day.weekday(), (None, ""))[1]
    if weekday_name:
        return f"{weekday_name}, {pickup_day.strftime('%d.%m.%Y')}"
    return pickup_day.strftime("%d.%m.%Y")


def pickup_time_is_available(pickup_date, selected_time):
    """Проверяет, что время выдачи не находится в прошлом."""
    if pickup_date != local_now().date().isoformat():
        return True
    return selected_time > local_now().time().replace(tzinfo=None)

# ============================================================
# DATABASE
# ============================================================
def _conn():
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = _conn()
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON")

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        phone TEXT,
        orders_count INTEGER DEFAULT 0,
        balance INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS cart (
        user_id INTEGER,
        item_id TEXT,
        item_name TEXT,
        price INTEGER,
        count INTEGER,
        pickup_date TEXT,
        PRIMARY KEY (user_id, item_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        items TEXT NOT NULL,
        total INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'new',
        pickup_time TEXT,
        pickup_date TEXT,
        created_at TEXT NOT NULL,
        discount_amount INTEGER NOT NULL DEFAULT 0,
        points_used INTEGER NOT NULL DEFAULT 0,
        points_earned INTEGER NOT NULL DEFAULT 0,
        rewards_applied INTEGER NOT NULL DEFAULT 0,
        qr_token TEXT,
        request_token TEXT,
        comment TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        item_type TEXT NOT NULL,
        item_name TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        unit_price INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS menu_categories (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        banner TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS menu_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cat_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        price INTEGER NOT NULL,
        image TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS lunch_config (
        day_id TEXT PRIMARY KEY,
        salad TEXT NOT NULL,
        salad_description TEXT,
        salad_image TEXT,
        poster TEXT,
        drink TEXT NOT NULL,
        garnish1 TEXT NOT NULL,
        garnish2 TEXT NOT NULL,
        garnish3 TEXT NOT NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS lunch_hot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day_id TEXT NOT NULL,
        emoji TEXT,
        name TEXT NOT NULL,
        description TEXT,
        price INTEGER NOT NULL,
        image TEXT,
        active INTEGER NOT NULL DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS order_components (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        component_type TEXT NOT NULL,
        component_name TEXT NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE
    )""")

    # Миграция существующей БД без удаления старых клиентов и заказов.
    def ensure_column(table, column, definition):
        cols = {row[1] for row in c.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in cols:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    ensure_column("users", "balance", "INTEGER DEFAULT 0")
    ensure_column("cart", "pickup_date", "TEXT")
    ensure_column("orders", "points_used", "INTEGER NOT NULL DEFAULT 0")
    ensure_column("orders", "points_earned", "INTEGER NOT NULL DEFAULT 0")
    # В старой версии бонусы начислялись при создании заказа. Значение 1
    # предотвращает повторное начисление для уже существующих заказов.
    ensure_column("orders", "rewards_applied", "INTEGER NOT NULL DEFAULT 1")
    ensure_column("orders", "qr_token", "TEXT")
    ensure_column("orders", "pickup_date", "TEXT")
    ensure_column("orders", "request_token", "TEXT")
    ensure_column("orders", "comment", "TEXT")
    ensure_column("lunch_config", "salad_description", "TEXT")
    ensure_column("lunch_config", "salad_image", "TEXT")
    ensure_column("lunch_config", "poster", "TEXT")
    ensure_column("lunch_hot", "image", "TEXT")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_qr_token ON orders(qr_token)")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_request_token ON orders(request_token)")

    conn.commit()
    conn.close()
    _seed_menu()
    _seed_lunch()
    _ensure_setting("menu_active", "1")


def _ensure_setting(key, default):
    conn = _conn()
    conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, default))
    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = _conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = _conn()
    conn.execute(
        "INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


def menu_is_active():
    return get_setting("menu_active", "1") == "1"


def set_menu_active(active):
    set_setting("menu_active", "1" if active else "0")


def _seed_menu():
    conn = _conn()
    c = conn.cursor()
    c.executemany(
        "INSERT OR IGNORE INTO menu_categories(id,name,banner) VALUES (?,?,?)",
        DEFAULT_CATEGORIES,
    )
    # Недельные постеры обновляем и в уже существующей базе.
    for day_id, poster in WEEK_POSTERS.items():
        c.execute("UPDATE menu_categories SET banner=? WHERE id=?", (poster, day_id))
    if c.execute("SELECT COUNT(*) AS n FROM menu_items").fetchone()["n"] == 0:
        c.executemany(
            "INSERT INTO menu_items(cat_id,name,description,price,image) VALUES (?,?,?,?,?)",
            DEFAULT_ITEMS,
        )
    conn.commit()
    conn.close()


def _seed_lunch():
    conn = _conn()
    c = conn.cursor()
    for day_id, cfg in DEFAULT_LUNCH.items():
        c.execute(
            "INSERT OR IGNORE INTO lunch_config("
            "day_id,salad,salad_description,salad_image,poster,drink,garnish1,garnish2,garnish3"
            ") VALUES (?,?,?,?,?,?,?,?,?)",
            (
                day_id, cfg["salad"], cfg["salad_description"], cfg["salad_image"], cfg["poster"],
                cfg["drink"], *cfg["garnishes"],
            ),
        )
        c.execute(
            "UPDATE lunch_config SET salad_description=?,salad_image=?,poster=? WHERE day_id=?",
            (cfg["salad_description"], cfg["salad_image"], cfg["poster"], day_id),
        )
        for emoji, name, desc, price, image in cfg["hot"]:
            existing = c.execute(
                "SELECT id FROM lunch_hot WHERE day_id=? AND name=? ORDER BY id LIMIT 1",
                (day_id, name),
            ).fetchone()
            if existing:
                c.execute(
                    "UPDATE lunch_hot SET description=?,image=? WHERE id=?",
                    (desc, image, existing["id"]),
                )
            else:
                c.execute(
                    "INSERT INTO lunch_hot(day_id,emoji,name,description,price,image,active) "
                    "VALUES (?,?,?,?,?,?,1)",
                    (day_id, emoji, name, desc, price, image),
                )
    conn.commit()
    conn.close()

# ============================================================
# DB READ / WRITE
# ============================================================
def get_user(user_id):
    conn = _conn()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row


def add_user(user_id, phone):
    conn = _conn()
    conn.execute(
        "INSERT INTO users(user_id,phone,balance) VALUES (?,?,0) ON CONFLICT(user_id) DO UPDATE SET phone=excluded.phone",
        (user_id, phone),
    )
    conn.commit()
    conn.close()


def get_points_balance(user_id):
    conn = _conn()
    row = conn.execute("SELECT COALESCE(balance,0) AS balance FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return int(row["balance"]) if row else 0


def get_orders_count(user_id):
    conn = _conn()
    row = conn.execute("SELECT COALESCE(orders_count,0) AS cnt FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return int(row["cnt"]) if row else 0


def mark_order_delivered_by_qr(token):
    conn = _conn()
    row = conn.execute("SELECT * FROM orders WHERE qr_token=?", (token,)).fetchone()
    conn.close()
    if not row:
        return None, "not_found"
    if row["status"] == "delivered":
        return dict(row), "already_delivered"
    if row["status"] == "cancelled" or not set_order_status(row["order_id"], "delivered"):
        return dict(row), "invalid_status"
    return get_order(row["order_id"]), "delivered"


def build_qr_image(link):
    image = qrcode.make(link)
    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    output.name = "pickup_qr.png"
    return output


def get_pickup_link(bot_username, token):
    return f"https://t.me/{bot_username}?start=pickup_{quote(token, safe='')}"


def get_all_user_ids():
    conn = _conn()
    rows = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    return [r["user_id"] for r in rows]


def get_all_categories():
    conn = _conn()
    rows = conn.execute("SELECT id,name FROM menu_categories ORDER BY rowid").fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"]} for r in rows]


def get_category(cat_id):
    conn = _conn()
    row = conn.execute("SELECT * FROM menu_categories WHERE id=?", (cat_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_items(cat_id):
    conn = _conn()
    rows = conn.execute(
        "SELECT id,name,description,price,image FROM menu_items WHERE cat_id=? ORDER BY id",
        (cat_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_dish(cat_id, name, desc, price, photo):
    conn = _conn()
    conn.execute(
        "INSERT INTO menu_items(cat_id,name,description,price,image) VALUES (?,?,?,?,?)",
        (cat_id, name, desc, price, photo),
    )
    conn.commit()
    conn.close()


def delete_dish(item_id):
    conn = _conn()
    conn.execute("DELETE FROM menu_items WHERE id=?", (item_id,))
    conn.execute("DELETE FROM cart WHERE item_id=?", (str(item_id),))
    conn.commit()
    conn.close()


def get_lunch_config(day_id):
    conn = _conn()
    cfg = conn.execute("SELECT * FROM lunch_config WHERE day_id=?", (day_id,)).fetchone()
    hot = conn.execute(
        "SELECT id,emoji,name,description,price,image FROM lunch_hot "
        "WHERE day_id=? AND active=1 ORDER BY id",
        (day_id,),
    ).fetchall()
    conn.close()
    return (dict(cfg) if cfg else None), [dict(x) for x in hot]


def resolve_media(value):
    """Преобразует путь из БД в локальный файл, не ломая URL и Telegram file_id."""
    if not value:
        return value
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = BASE_DIR / candidate
    if candidate.is_file():
        return candidate
    return value


def get_day_poster(day_id, cfg=None):
    if cfg and cfg.get("poster"):
        return cfg["poster"]
    category = get_category(day_id)
    if category and category.get("banner"):
        return category["banner"]
    return WEEK_POSTERS.get(day_id, LUNCH_BANNER)


def build_day_caption(day_id, day_name, pickup_date=None, channel_post=False):
    """Собирает единое описание дня для бота и публикации в канале."""
    cfg, hot = get_lunch_config(day_id)
    if not cfg or not hot:
        return None
    heading = (
        f"🍽 <b>Обед на {esc(day_name.lower())}</b>"
        if channel_post
        else f"<b>🍽 {esc(day_name)}</b>"
    )
    lines = [heading]
    if pickup_date:
        lines.append(f"📅 {display_date(pickup_date)}")
    lines += ["", "Выберите основное блюдо:"]
    for item in hot:
        lines += [
            "",
            f"{item['emoji']} <b>{esc(item['name'])}</b> — <b>{fmt(item['price'])} сум</b>",
            esc(item["description"]),
        ]
    lines += [
        "",
        f"🥗 <b>{esc(cfg['salad'])}</b> — по желанию",
        esc(cfg.get("salad_description") or ""),
        f"🍚 Гарнир: {esc(cfg['garnish1'])} / {esc(cfg['garnish2'])} / {esc(cfg['garnish3'])}",
        "🥤 Напиток: Шербет, Айс-ти или без напитка",
    ]
    if channel_post:
        lines += [
            "",
            "🕒 Выдача: 11:00–16:00",
            "📍 4 этаж, кухня",
            "",
            "Оформите заказ заранее в боте 👇",
            "<i>Изображения носят иллюстративный характер. Фактическая подача может отличаться.</i>",
        ]
    return "\n".join(line for line in lines if line is not None)


def get_cart(user_id):
    conn = _conn()
    rows = conn.execute(
        "SELECT item_id,item_name,price,count,pickup_date FROM cart WHERE user_id=? ORDER BY rowid",
        (user_id,),
    ).fetchall()
    conn.close()
    return {
        r["item_id"]: {
            "name": r["item_name"],
            "price": r["price"],
            "count": r["count"],
            "pickup_date": r["pickup_date"],
        }
        for r in rows
    }


def get_cart_pickup_date(user_id):
    dates = {item["pickup_date"] for item in get_cart(user_id).values() if item.get("pickup_date")}
    if len(dates) > 1:
        return None
    return next(iter(dates), None) or next_business_date()


def cart_accepts_date(user_id, pickup_date):
    dates = {item["pickup_date"] for item in get_cart(user_id).values() if item.get("pickup_date")}
    return not dates or dates == {pickup_date}


def update_cart(user_id, item_id, item_name, price, count, pickup_date=None):
    conn = _conn()
    if count <= 0:
        conn.execute("DELETE FROM cart WHERE user_id=? AND item_id=?", (user_id, item_id))
    else:
        pickup_date = pickup_date or get_cart_pickup_date(user_id)
        conn.execute(
            "INSERT INTO cart(user_id,item_id,item_name,price,count,pickup_date) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(user_id,item_id) DO UPDATE SET "
            "item_name=excluded.item_name,price=excluded.price,count=excluded.count,pickup_date=excluded.pickup_date",
            (user_id, item_id, item_name, price, count, pickup_date),
        )
    conn.commit()
    conn.close()


def clear_cart(user_id):
    conn = _conn()
    conn.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def get_cart_summary(user_id):
    cart = get_cart(user_id)
    if not cart:
        return None, 0, 0, ""
    lines = []
    short = []
    lunch_total = 0
    other_total = 0
    conn = _conn()
    cat_map = {
        str(r["id"]): r["cat_id"]
        for r in conn.execute("SELECT id,cat_id FROM menu_items").fetchall()
    }
    conn.close()
    for item_id, data in cart.items():
        subtotal = data["price"] * data["count"]
        lines.append(f"• <b>{esc(data['name'])}</b> x{data['count']} — <b>{fmt(subtotal)} сум</b>")
        short.append(f"{data['name']} x{data['count']}")
        if str(item_id).startswith("lunch_") or cat_map.get(str(item_id)) in LUNCH_CAT_IDS:
            lunch_total += subtotal
        else:
            other_total += subtotal
    return "\n".join(lines), lunch_total, other_total, ", ".join(short)

# ============================================================
# ORDER STORAGE
# ============================================================
def create_order(
    user_id,
    items_str,
    total,
    pickup_time,
    pickup_date,
    request_token,
    comment="",
    discount_amount=0,
    components=None,
    points_used=0,
):
    components = components or []
    comment = str(comment or "").strip()[:300]
    if not request_token:
        raise ValueError("request_token is required")
    conn = _conn()
    now = local_now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    existing = cur.execute(
        "SELECT order_id,points_used,points_earned,qr_token FROM orders WHERE request_token=?",
        (request_token,),
    ).fetchone()
    if existing:
        conn.close()
        return existing["order_id"], existing["points_used"], existing["points_earned"], existing["qr_token"], False

    # Списание баллов и создание заказа выполняются одной транзакцией.
    # Начисление произойдёт только после фактической выдачи заказа.
    balance_row = cur.execute("SELECT COALESCE(balance,0) AS balance FROM users WHERE user_id=?", (user_id,)).fetchone()
    current_balance = int(balance_row["balance"]) if balance_row else 0
    points_used = max(0, min(int(points_used or 0), current_balance))
    points_earned = int(max(0, total) * POINTS_RATE)
    qr_token = secrets.token_urlsafe(18)
    cur.execute(
        "INSERT INTO orders("
        "user_id,items,total,status,pickup_time,pickup_date,created_at,discount_amount,"
        "points_used,points_earned,rewards_applied,qr_token,request_token,comment"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            user_id, items_str, total, "new", pickup_time, pickup_date, now, discount_amount,
            points_used, points_earned, 0, qr_token, request_token, comment,
        ),
    )
    order_id = cur.lastrowid
    for item_type, item_name, qty, unit_price in components:
        cur.execute(
            "INSERT INTO order_items(order_id,item_type,item_name,quantity,unit_price) VALUES (?,?,?,?,?)",
            (order_id, item_type, item_name, qty, unit_price),
        )
        cur.execute(
            "INSERT INTO order_components(order_id,component_type,component_name) VALUES (?,?,?)",
            (order_id, item_type, item_name),
        )
    cur.execute(
        "UPDATE users SET orders_count=orders_count+1, balance=COALESCE(balance,0)-? WHERE user_id=?",
        (points_used, user_id),
    )
    conn.commit()
    conn.close()
    return order_id, points_used, points_earned, qr_token, True


def set_order_status(order_id, status):
    if status not in ORDER_STATUSES:
        return False
    conn = _conn()
    conn.execute("BEGIN IMMEDIATE")
    row = conn.execute(
        "SELECT user_id,status,points_used,points_earned,rewards_applied FROM orders WHERE order_id=?",
        (order_id,),
    ).fetchone()
    if not row:
        conn.close()
        return False
    current = row["status"]
    if current == status:
        conn.close()
        return True

    if current in {"delivered", "cancelled"}:
        conn.close()
        return False

    status_rank = {"new": 0, "paid": 0, "cooking": 1, "ready": 2, "delivered": 3}
    if (
        status != "cancelled"
        and current in status_rank
        and status in status_rank
        and status_rank[status] < status_rank[current]
    ):
        conn.close()
        return False

    if status == "cancelled":
        # Бонусы нового заказа ещё не начислены, поэтому возвращаем только списанные.
        if not row["rewards_applied"] and row["points_used"]:
            conn.execute(
                "UPDATE users SET balance=COALESCE(balance,0)+? WHERE user_id=?",
                (row["points_used"], row["user_id"]),
            )
    elif status == "delivered" and not row["rewards_applied"]:
        conn.execute(
            "UPDATE users SET balance=COALESCE(balance,0)+? WHERE user_id=?",
            (row["points_earned"], row["user_id"]),
        )
        conn.execute("UPDATE orders SET rewards_applied=1 WHERE order_id=?", (order_id,))

    conn.execute("UPDATE orders SET status=? WHERE order_id=?", (status, order_id))
    conn.commit()
    conn.close()
    return True


def get_order(order_id):
    conn = _conn()
    row = conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_active_orders():
    conn = _conn()
    rows = conn.execute(
        "SELECT order_id,user_id,items,total,status,pickup_time,pickup_date,created_at,comment FROM orders "
        "WHERE status NOT IN ('delivered','cancelled') "
        "ORDER BY COALESCE(pickup_date,substr(created_at,1,10)), "
        "CASE pickup_time WHEN 'Сейчас (В очереди)' THEN '00:00' ELSE pickup_time END, order_id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_today_stats():
    today = local_now().strftime("%Y-%m-%d")
    conn = _conn()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt, COALESCE(SUM(total),0) AS total FROM orders "
        "WHERE substr(created_at,1,10)=? AND status!='cancelled'",
        (today,),
    ).fetchone()
    conn.close()
    return row["cnt"], row["total"]


def get_kitchen_summary():
    """Надежная сводка из order_items, без разбора строки заказа."""
    today = local_now().strftime("%Y-%m-%d")
    conn = _conn()
    rows = conn.execute(
        "SELECT oi.item_type, oi.item_name, SUM(oi.quantity) AS qty "
        "FROM order_items oi JOIN orders o ON o.order_id=oi.order_id "
        "WHERE COALESCE(o.pickup_date,substr(o.created_at,1,10))=? "
        "AND o.status IN ('new','paid','cooking') "
        "GROUP BY oi.item_type, oi.item_name ORDER BY oi.item_type, qty DESC",
        (today,),
    ).fetchall()
    conn.close()
    return [(r["item_type"], r["item_name"], r["qty"]) for r in rows]


def get_all_orders_for_export():
    conn = _conn()
    rows = conn.execute(
        "SELECT o.order_id,o.created_at,o.pickup_date,u.phone,o.items,o.total,o.status,o.pickup_time,"
        "o.discount_amount,o.points_used,o.points_earned,o.comment "
        "FROM orders o LEFT JOIN users u ON o.user_id=u.user_id ORDER BY o.order_id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ============================================================
# LUNCH SESSION / BUILDING A COMBO
# ============================================================
def lunch_session(context):
    return context.user_data.setdefault(
        "lunch",
        {
            "day_id": None,
            "pickup_date": None,
            "hot_id": None,
            "hot_name": None,
            "hot_price": 0,
            "hot_image": None,
            "garnish": None,
            "garnish_index": None,
            "salad_code": None,
            "salad_name": None,
            "drink_code": None,
            "drink_name": None,
        },
    )


def reset_lunch_session(context):
    context.user_data["lunch"] = {
        "day_id": None,
        "pickup_date": None,
        "hot_id": None,
        "hot_name": None,
        "hot_price": 0,
        "hot_image": None,
        "garnish": None,
        "garnish_index": None,
        "salad_code": None,
        "salad_name": None,
        "drink_code": None,
        "drink_name": None,
    }


def lunch_combo_item_id(session):
    if (
        not session.get("day_id")
        or not session.get("hot_id")
        or not session.get("garnish_index")
        or session.get("salad_code") is None
        or session.get("drink_code") is None
    ):
        return None
    return (
        f"lunch_{session['day_id']}_{session['hot_id']}"
        f"_g{session['garnish_index']}_s{session['salad_code']}_{session['drink_code']}"
    )


def lunch_combo_name(cfg, session):
    base = f"🍱 {session['hot_name']} + {session['garnish']}"
    if session.get("salad_code") == "none":
        base += " + 🚫 Без салата"
    else:
        base += f" + 🥗 {cfg['salad']}"
    if session.get("drink_code") == "none":
        return base + " + 🚫 Без напитка"
    return base + f" + {session['drink_name']}"


def get_garnish_by_index(cfg, index):
    mapping = {
        1: cfg["garnish1"],
        2: cfg["garnish2"],
        3: cfg["garnish3"],
    }
    return mapping.get(index)

# ============================================================
# KEYBOARDS
# ============================================================
def kb_miniapp():
    """Постоянная кнопка запуска Mini App в личном чате с ботом."""
    if not MINIAPP_URL.startswith("https://"):
        return None
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🍽 Открыть меню", web_app=WebAppInfo(url=MINIAPP_URL))]],
        resize_keyboard=True,
        is_persistent=True,
    )


def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🍱 Комплексный обед сегодня", callback_data="lunch_today")],
        [InlineKeyboardButton("🍳 Завтраки", callback_data="cat_breakfasts"),
         InlineKeyboardButton("🥤 Напитки", callback_data="nav_drinks")],
        [InlineKeyboardButton("🗓 Меню на неделю", callback_data="nav_week")],
        [InlineKeyboardButton("🛒 Корзина", callback_data="cart_view")],
        [InlineKeyboardButton("⭐ Мои бонусы", callback_data="profile")],
    ])


def kb_home():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Главное меню", callback_data="home")],
    ])


def kb_drinks():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("☕ Горячие напитки", callback_data="cat_hot_drinks")],
        [InlineKeyboardButton("🧊 Холодные напитки", callback_data="cat_cold_drinks")],
        [InlineKeyboardButton("🍹 Фреши", callback_data="cat_fresh_drinks")],
        [InlineKeyboardButton("🔙 Назад", callback_data="home")],
    ])


def kb_week():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Пн", callback_data="day_mon"),
         InlineKeyboardButton("Вт", callback_data="day_tue"),
         InlineKeyboardButton("Ср", callback_data="day_wed")],
        [InlineKeyboardButton("Чт", callback_data="day_thu"),
         InlineKeyboardButton("Пт", callback_data="day_fri")],
        [InlineKeyboardButton("🔙 Назад", callback_data="home")],
    ])


def kb_category(user_id, cat_id, items):
    cart = get_cart(user_id)
    rows = []
    for item in items:
        iid = str(item["id"])
        count = cart.get(iid, {}).get("count", 0)
        rows.append([
            InlineKeyboardButton(
                f"🍽 {item['name']} — {fmt(item['price'])} сум",
                callback_data=f"add_{cat_id}_{iid}",
            )
        ])
        if count:
            rows.append([
                InlineKeyboardButton("➖", callback_data=f"rm_{cat_id}_{iid}"),
                InlineKeyboardButton(f"{count} шт", callback_data="ignore"),
                InlineKeyboardButton("➕", callback_data=f"add_{cat_id}_{iid}"),
            ])
    back = "nav_drinks" if cat_id in {"hot_drinks", "cold_drinks", "fresh_drinks"} else "home"
    rows.append([
        InlineKeyboardButton("🛒 Корзина", callback_data="cart_view"),
        InlineKeyboardButton("🔙 Назад", callback_data=back),
    ])
    return InlineKeyboardMarkup(rows)


def kb_lunch_hot(hot_items):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{h['emoji']} {h['name']} — {fmt(h['price'])} сум", callback_data=f"lh_{h['id']}")]
        for h in hot_items
    ] + [[InlineKeyboardButton("🔙 В меню", callback_data="home")]])


def kb_lunch_garnishes(cfg):
    # В callback_data передаём номер гарнира, а не его название.
    # Это гарантирует корректный разбор независимо от языка/эмодзи/пробелов в названии.
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🍚 {cfg['garnish1']}", callback_data="lg_1")],
        [InlineKeyboardButton(f"🌾 {cfg['garnish2']}", callback_data="lg_2")],
        [InlineKeyboardButton(f"🥔 {cfg['garnish3']}", callback_data="lg_3")],
        [InlineKeyboardButton("🔙 Назад", callback_data="lunch_hot_back")],
    ])

def kb_lunch_salad():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🥗 Оставить салат", callback_data="ls_keep")],
        [InlineKeyboardButton("🚫 Без салата", callback_data="ls_none")],
        [InlineKeyboardButton("🔙 Назад к гарнирам", callback_data="lunch_salad_back")],
    ])


def kb_lunch_drinks():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🥤 Шербет", callback_data="ld_sherbet")],
        [InlineKeyboardButton("🧊 Айс-ти", callback_data="ld_iced_tea")],
        [InlineKeyboardButton("🚫 Без напитка", callback_data="ld_none")],
        [InlineKeyboardButton("🔙 Назад к гарнирам", callback_data="lunch_drink_back")],
    ])


def _scheduled_time_rows(pickup_date):
    """Возвращает только те готовые часы, которые ещё можно выбрать."""
    buttons = []
    for value in ("11:00", "12:00", "13:00", "14:00", "15:00", "16:00"):
        parsed = datetime.strptime(value, "%H:%M").time()
        if pickup_time_is_available(pickup_date, parsed):
            buttons.append(InlineKeyboardButton(value, callback_data=f"tv_{value}"))
    return [buttons[index:index + 2] for index in range(0, len(buttons), 2)]


def kb_time(pickup_date, has_lunch=False):
    """Показывает только доступные для выбранной даты варианты выдачи."""
    now = local_now()
    is_today = pickup_date == now.date().isoformat()
    now_time = now.time().replace(tzinfo=None)
    rows = []

    if is_today and t_time(11, 0) <= now_time < t_time(17, 0):
        rows.append([
            InlineKeyboardButton("🏃 Забрать сейчас", callback_data="tv_Сейчас (В очереди)")
        ])

    rows.extend(_scheduled_time_rows(pickup_date))
    rows.append([InlineKeyboardButton("✍️ Указать своё время", callback_data="time_custom")])

    if is_today and now.hour == 16 and has_lunch:
        rows.append([
            InlineKeyboardButton("🔥 Скидка 20% (16:00–17:00)", callback_data="tv_discount")
        ])

    rows.append([InlineKeyboardButton("🔙 Назад в корзину", callback_data="cart_view")])
    return InlineKeyboardMarkup(rows)


def kb_postpone_time(pickup_date):
    """Совместимость со старыми сообщениями, где была кнопка «Отложить»."""
    rows = _scheduled_time_rows(pickup_date)
    rows.append([InlineKeyboardButton("✍️ Указать своё время", callback_data="time_custom")])
    rows.append([InlineKeyboardButton("🔙 Назад в корзину", callback_data="cart_view")])
    return InlineKeyboardMarkup(rows)


def kb_order_status(order_id, current_status):
    next_status = NEXT_ORDER_STATUS.get(current_status)
    if not next_status:
        return None
    rows = [[
        InlineKeyboardButton(
            f"➡️ {ORDER_STATUSES[next_status]}",
            callback_data=f"setstatus_{order_id}_{next_status}",
        )
    ]]
    if current_status in {"new", "cooking", "ready"}:
        rows.append([
            InlineKeyboardButton("❌ Отменить заказ", callback_data=f"setstatus_{order_id}_cancelled")
        ])
    return InlineKeyboardMarkup(rows)

# ============================================================
# TELEGRAM RENDER
# ============================================================
async def send_or_edit(chat_id, msg_id, photo, caption, markup, context):
    photo = resolve_media(photo)
    try:
        media = InputMediaPhoto(media=photo, caption=caption, parse_mode="HTML")
        await context.bot.edit_message_media(
            chat_id=chat_id, message_id=msg_id, media=media, reply_markup=markup
        )
        context.user_data["last_msg_id"] = msg_id
        return
    except Exception:
        pass

    try:
        if msg_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception:
                pass
        if photo:
            msg = await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                reply_markup=markup,
                parse_mode="HTML",
            )
        else:
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=caption,
                reply_markup=markup,
                parse_mode="HTML",
            )
        context.user_data["last_msg_id"] = msg.message_id
    except Exception:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=markup,
            parse_mode="HTML",
        )
        context.user_data["last_msg_id"] = msg.message_id


async def show_profile(chat_id, context):
    """Понятный клиентский экран с бонусами и историей заказов."""
    balance = get_points_balance(chat_id)
    orders_count = get_orders_count(chat_id)
    text = (
        "<b>⭐ Мои бонусы</b>\n\n"
        f"Ваш баланс: <b>{fmt(balance)} бонусов</b>\n"
        f"Заказов с нами: <b>{orders_count}</b>\n\n"
        "💡 После выдачи заказа возвращается <b>5%</b> бонусами.\n"
        "До <b>30%</b> стоимости следующего заказа можно оплатить бонусами.\n\n"
        "❤️ Чем чаще вы заказываете, тем больше бонусов накапливается."
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍱 Заказать обед", callback_data="lunch_today")],
        [InlineKeyboardButton("🔙 В главное меню", callback_data="home")],
    ])
    await send_or_edit(chat_id, context.user_data.get("last_msg_id"), MAIN_BANNER, text, markup, context)


async def show_main(chat_id, context):
    balance = get_points_balance(chat_id)
    await send_or_edit(
        chat_id,
        context.user_data.get("last_msg_id"),
        MAIN_BANNER,
        f"<b>🏠 Главное меню</b>\n\n❤️ Рады вас видеть!\n⭐ Бонусный баланс: <b>{fmt(balance)}</b>\n\n🍽 Что хотите заказать сегодня?",
        kb_main(),
        context,
    )

# ============================================================
# COMMANDS / CONTACT
# ============================================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # QR-выдача: ссылка открывает этого же бота. Только администратор может подтвердить выдачу.
    if context.args and context.args[0].startswith("pickup_"):
        token = context.args[0][7:]
        if user_id != ADMIN_ID:
            await update.message.reply_text("🔒 Этот QR-код предназначен для сотрудника, который выдаёт заказ.")
            return
        order, result = mark_order_delivered_by_qr(token)
        if result == "not_found":
            await update.message.reply_text("❌ QR-код не найден. Попросите сотрудника открыть актуальный QR-код заказа.")
            return
        if result == "already_delivered":
            await update.message.reply_text(f"ℹ️ Заказ #{order['order_id']} уже выдан. Этот QR-код повторно использовать нельзя.")
            return
        if result == "invalid_status":
            await update.message.reply_text("❌ Этот заказ отменён или недоступен для выдачи.")
            return
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=f"🎉 <b>Заказ #{order['order_id']} выдан!</b>\n\nПриятного аппетита ❤️",
                reply_markup=kb_home(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        await update.message.reply_text(f"✅ Заказ #{order['order_id']} отмечен как выдан.")
        return

    if not get_user(user_id):
        kb = ReplyKeyboardMarkup(
            [[KeyboardButton("📱 Поделиться номером", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await context.bot.send_message(
            chat_id=user_id,
            text="👋 <b>Добро пожаловать!</b>\n\nЧтобы оформить заказ, поделитесь номером телефона. Это займёт пару секунд 👇",
            reply_markup=kb,
            parse_mode="HTML",
        )
        return
    if kb_miniapp():
        await update.message.reply_text(
            "🍽 Новое удобное меню доступно по кнопке ниже.",
            reply_markup=kb_miniapp(),
        )
    await show_main(user_id, context)


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if contact:
        if contact.user_id != update.effective_user.id:
            await update.message.reply_text(
                "⚠️ Отправьте именно свой номер кнопкой «Поделиться номером»."
            )
            return
        add_user(update.effective_user.id, contact.phone_number)
        await update.message.reply_text(
            "✅ Спасибо! Номер сохранён. Теперь можно заказывать 👌",
            reply_markup=kb_miniapp() or ReplyKeyboardRemove(),
        )
        await show_main(update.effective_user.id, context)


async def cmd_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not MINIAPP_URL:
        await update.message.reply_text("Мини‑приложение ещё не опубликовано.")
        return
    await update.message.reply_text(
        "Нажмите кнопку, чтобы открыть меню и оформить заказ 👇",
        reply_markup=kb_miniapp(),
    )


async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принимает заказ из Mini App и заново рассчитывает его по меню в БД."""
    message = update.effective_message
    user = update.effective_user
    if not message or not message.web_app_data or not user:
        return
    if not get_user(user.id):
        await message.reply_text(
            "Сначала поделитесь своим номером через /start, затем откройте меню снова.",
        )
        return
    if not menu_is_active():
        await message.reply_text("😔 Приём заказов сейчас приостановлен. Попробуйте немного позже.")
        return

    try:
        raw = message.web_app_data.data
        if len(raw.encode("utf-8")) > 4096:
            raise ValueError("payload is too large")
        payload = json.loads(raw)
        if payload.get("type") != "miniapp_order" or payload.get("version") != 1:
            raise ValueError("unsupported payload")

        request_token = str(payload.get("request_token") or "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_token):
            raise ValueError("invalid request token")

        pickup_date = str(payload.get("pickup_date") or "")
        pickup_day = datetime.strptime(pickup_date, "%Y-%m-%d").date()
        days_ahead = (pickup_day - local_now().date()).days
        if days_ahead < 0 or days_ahead > 14 or pickup_day.weekday() > 4:
            raise ValueError("invalid pickup date")

        pickup_time = str(payload.get("pickup_time") or "")
        selected_time = datetime.strptime(pickup_time, "%H:%M").time()
        if selected_time < t_time(11, 0) or selected_time > t_time(16, 0):
            raise ValueError("invalid pickup time")
        if not pickup_time_is_available(pickup_date, selected_time):
            raise ValueError("pickup time has passed")

        items = payload.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= 10:
            raise ValueError("invalid items")
        use_points = payload.get("use_points", False)
        if not isinstance(use_points, bool):
            raise ValueError("invalid points option")
        raw_comment = payload.get("comment", "")
        if not isinstance(raw_comment, str):
            raise ValueError("invalid order comment")
        comment = re.sub(r"\s+", " ", raw_comment).strip()
        if len(comment) > 300:
            raise ValueError("order comment is too long")

        expected_day_id = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri"}[pickup_day.weekday()]
        detail_lines = []
        short_names = []
        components = []
        total = 0
        total_quantity = 0

        for item in items:
            if not isinstance(item, dict) or item.get("day_id") != expected_day_id:
                raise ValueError("menu day mismatch")
            hot_name = str(item.get("hot_name") or "")
            garnish = str(item.get("garnish") or "")
            drink_code = str(item.get("drink_code") or "")
            with_salad = item.get("with_salad")
            quantity = int(item.get("quantity") or 0)
            if quantity < 1 or quantity > 5 or not isinstance(with_salad, bool):
                raise ValueError("invalid item options")

            cfg, hot_items = get_lunch_config(expected_day_id)
            hot = next((candidate for candidate in hot_items if candidate["name"] == hot_name), None)
            allowed_garnishes = {cfg["garnish1"], cfg["garnish2"], cfg["garnish3"]} if cfg else set()
            drink_name = LUNCH_DRINKS.get(drink_code)
            if not cfg or not hot or garnish not in allowed_garnishes or not drink_name:
                raise ValueError("menu item is no longer available")

            item_total = int(hot["price"]) * quantity
            total += item_total
            total_quantity += quantity
            if total > 2_000_000 or total_quantity > 10:
                raise ValueError("order limit exceeded")

            options = [garnish]
            if with_salad:
                options.append(cfg["salad"])
            else:
                options.append("без салата")
            if drink_code != "none":
                options.append(drink_name)
            else:
                options.append("без напитка")

            detail_lines.append(
                f"• <b>{esc(hot['name'])}</b> ×{quantity} — <b>{fmt(item_total)} сум</b>\n"
                f"  └ {esc(' · '.join(options))}"
            )
            short_names.append(f"{hot['name']} + {' + '.join(options)} x{quantity}")
            components.extend([
                ("hot", hot["name"], quantity, hot["price"]),
                ("garnish", garnish, quantity, 0),
            ])
            if with_salad:
                components.append(("salad", cfg["salad"], quantity, 0))
            if drink_code != "none":
                components.append(("drink", drink_name, quantity, 0))

        if total <= 0:
            raise ValueError("empty order")
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        logging.warning("Отклонены некорректные данные Mini App от пользователя %s", user.id)
        await message.reply_text(
            "⚠️ Не удалось проверить заказ. Откройте меню заново и повторите оформление.",
        )
        return

    request_token = f"miniapp:{user.id}:{request_token}"
    items_str = ", ".join(short_names)
    available_points = get_points_balance(user.id)
    points_to_use = (
        min(available_points, int(total * POINTS_MAX_USE_RATE))
        if use_points else 0
    )
    final_total = max(0, total - points_to_use)
    order_id, points_used, points_earned, qr_token, created = create_order(
        user.id,
        items_str,
        final_total,
        pickup_time,
        pickup_date,
        request_token,
        comment=comment,
        components=components,
        points_used=points_to_use,
    )
    if not created:
        await message.reply_text(f"ℹ️ Заказ #{order_id} уже был создан. Повторное оформление не выполнено.")
        return

    lines = "\n".join(detail_lines)
    balance_after = get_points_balance(user.id)
    bot_info = await context.bot.get_me()
    pickup_link = get_pickup_link(bot_info.username, qr_token)
    qr_image = build_qr_image(pickup_link)
    comment_line = f"📝 Комментарий: {esc(comment)}\n" if comment else ""
    confirmation = (
        f"<b>✅ Заказ #{order_id} принят!</b>\n\n{lines}\n\n"
        f"📍 Место выдачи: 4 этаж, кухня\n"
        f"📅 Дата: {display_date(pickup_date)}\n"
        f"🕒 Время: {pickup_time}\n"
        f"{comment_line}"
        f"💰 К оплате через Click: {fmt(final_total)} сум\n\n"
        f"⭐ Списано бонусов: {fmt(points_used)}\n"
        f"⭐ Будет начислено после выдачи: +{fmt(points_earned)}\n"
        f"⭐ Текущий баланс: {fmt(balance_after)} бонусов\n\n"
        "Нажмите кнопку оплаты ниже, затем покажите QR‑код сотруднику при получении."
    )
    payment_markup = kb_click_payment(final_total)
    try:
        await context.bot.send_photo(
            chat_id=user.id,
            photo=qr_image,
            caption=confirmation,
            reply_markup=payment_markup,
            parse_mode="HTML",
        )
    except Exception:
        await context.bot.send_message(
            chat_id=user.id,
            text=confirmation + f"\n\nQR: {pickup_link}",
            reply_markup=payment_markup,
            parse_mode="HTML",
        )

    order_notification_chat_id = ORDER_CHANNEL_ID or ADMIN_ID
    if order_notification_chat_id:
        user_row = get_user(user.id)
        phone = user_row["phone"] if user_row else "нет"
        full_name = esc(user.full_name or user.first_name or "Клиент")
        username = f" (@{esc(user.username)})" if user.username else ""
        admin_text = (
            f"🚨 <b>Новый заказ #{order_id} из Mini App!</b>\n"
            f"👤 {full_name}{username}\n📞 {esc(phone)}\n"
            f"📅 {display_date(pickup_date)}\n🕒 {pickup_time}\n"
            f"{comment_line}"
            f"💰 {fmt(final_total)} сум — ссылка Click отправлена клиенту\n"
            f"⭐ Списано бонусов: {fmt(points_used)}\n"
            f"⭐ Будет начислено после выдачи: {fmt(points_earned)}\n\n"
            f"<b>Состав:</b>\n{lines}"
        )
        try:
            await context.bot.send_message(
                chat_id=order_notification_chat_id,
                text=admin_text,
                reply_markup=kb_order_status(order_id, "new"),
                parse_mode="HTML",
            )
        except Exception:
            logging.exception("Не удалось отправить уведомление о заказе #%s", order_id)


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"<b>Ваш Telegram ID:</b>\n<code>{update.effective_user.id}</code>",
        parse_mode="HTML",
    )


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ закрыт.")
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton("🍽 Сводка для кухни", callback_data="adm_kitchen")],
        [InlineKeyboardButton("📋 Активные заказы", callback_data="adm_orders")],
        [InlineKeyboardButton("📣 Опубликовать меню", callback_data="adm_postmenu")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast")],
        [InlineKeyboardButton("➕ Добавить блюдо", callback_data="adm_add"),
         InlineKeyboardButton("🗑 Удалить блюдо", callback_data="adm_del")],
        [InlineKeyboardButton("📥 Экспорт CSV", callback_data="adm_export")],
        [InlineKeyboardButton("⛔ Вкл/Выкл приём заказов", callback_data="adm_toggle")],
    ])
    await update.message.reply_text("👑 <b>Панель администратора</b>", reply_markup=kb, parse_mode="HTML")


async def publish_day_post(day_id, context, response_message):
    day_name = next((name for _, (code, name) in WEEKDAYS.items() if code == day_id), None)
    if not day_name:
        await response_message.reply_text("❌ Неизвестный день недели.")
        return
    cfg, hot = get_lunch_config(day_id)
    if not cfg or not hot:
        await response_message.reply_text("❌ Меню на этот день не настроено.")
        return
    pickup_date = next_date_for_day(day_id)
    caption = build_day_caption(
        day_id,
        day_name,
        pickup_date=pickup_date,
        channel_post=True,
    )
    bot_info = await context.bot.get_me()
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🍱 Заказать обед", url=f"https://t.me/{bot_info.username}")
    ]])
    try:
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=resolve_media(get_day_poster(day_id, cfg)),
            caption=caption,
            reply_markup=markup,
            parse_mode="HTML",
        )
        await response_message.reply_text(
            f"✅ Пост на {day_name.lower()} опубликован в {CHANNEL_ID}."
        )
    except Exception as e:
        await response_message.reply_text(f"❌ Ошибка: {e}")


async def cmd_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    aliases = {
        "mon": "mon", "пн": "mon",
        "tue": "tue", "вт": "tue",
        "wed": "wed", "ср": "wed",
        "thu": "thu", "чт": "thu",
        "fri": "fri", "пт": "fri",
    }
    if context.args:
        day_id = aliases.get(context.args[0].lower())
        if not day_id:
            await update.message.reply_text("Использование: /post mon|tue|wed|thu|fri")
            return
    else:
        wd = local_now().weekday()
        if wd >= 5:
            await update.message.reply_text(
                "Сегодня выходной. Выберите день кнопкой «Опубликовать меню» в /admin."
            )
            return
        day_id = WEEKDAYS[wd][0]
    await publish_day_post(day_id, context, update.message)

# ============================================================
# ADMIN BROADCAST / ADD DISH
# ============================================================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text or ""
    state = context.user_data.get("state")

    if state == "CUSTOM_TIME":
        raw = text.strip()
        try:
            parsed = datetime.strptime(raw, "%H:%M").time()
        except ValueError:
            await update.message.reply_text(
                "⚠️ Не удалось распознать время.\n\nУкажите его в формате <b>ЧЧ:ММ</b>, например <b>14:45</b>.",
                parse_mode="HTML")
            return
        if not (t_time(11, 0) <= parsed <= t_time(16, 0)):
            await update.message.reply_text(
                "⚠️ Для обычной выдачи можно выбрать время с <b>11:00 до 16:00</b>.\n\nПопробуйте ещё раз.",
                parse_mode="HTML")
            return
        pickup_date = context.user_data.get("pickup_date") or get_cart_pickup_date(user_id)
        if not pickup_time_is_available(pickup_date, parsed):
            await update.message.reply_text("⚠️ Это время уже прошло. Выберите более позднее время.")
            return
        context.user_data["state"] = None
        context.user_data["points_to_use"] = 0
        await _show_checkout(update.message, context, user_id, parsed.strftime("%H:%M"), reply=True)
        return

    if user_id != ADMIN_ID:
        return

    if text.lower() == "отмена":
        context.user_data["state"] = None
        await update.message.reply_text("❌ Действие отменено.")
        return

    if state == "BROADCAST":
        await _do_broadcast(update, context)
        return
    if state == "DISH_NAME":
        context.user_data["new_dish"]["name"] = text
        context.user_data["state"] = "DISH_DESC"
        await update.message.reply_text("✏️ Напишите короткое описание блюда:")
        return
    if state == "DISH_DESC":
        context.user_data["new_dish"]["desc"] = text
        context.user_data["state"] = "DISH_PRICE"
        await update.message.reply_text("💰 Укажите цену в сумах (только цифры):")
        return
    if state == "DISH_PRICE":
        if not text.isdigit():
            await update.message.reply_text("⚠️ Цена должна содержать только цифры, например: 63000.")
            return
        context.user_data["new_dish"]["price"] = int(text)
        context.user_data["state"] = "DISH_PHOTO"
        await update.message.reply_text("🖼 Отправьте фото блюда или ссылку на изображение:")
        return
    if state == "DISH_PHOTO":
        context.user_data["new_dish"]["photo"] = text
        _save_dish(context)
        await update.message.reply_text("✅ Блюдо добавлено в меню.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    state = context.user_data.get("state")
    if state == "BROADCAST":
        await _do_broadcast(update, context)
    elif state == "DISH_PHOTO":
        context.user_data["new_dish"]["photo"] = update.message.photo[-1].file_id
        _save_dish(context)
        await update.message.reply_text("✅ Блюдо добавлено в меню.")


def _save_dish(context):
    d = context.user_data.get("new_dish", {})
    add_dish(d.get("cat_id", ""), d.get("name", ""), d.get("desc", ""), d.get("price", 0), d.get("photo", ""))
    context.user_data["state"] = None


async def _do_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_user_ids()
    count = 0
    msg = await update.message.reply_text("⏳ Рассылка началась. Отправляем сообщение клиентам…")
    for uid in users:
        try:
            await context.bot.copy_message(
                chat_id=uid,
                from_chat_id=update.message.chat_id,
                message_id=update.message.message_id,
            )
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    context.user_data["state"] = None
    await msg.edit_text(f"✅ Рассылка завершена! Доставлено: <b>{count}</b>", parse_mode="HTML")

# ============================================================
# CHECKOUT — ОПЛАТА ЧЕРЕЗ CLICK
# ============================================================
async def _show_checkout(source, context, user_id, pickup_time, discount=False, reply=False):
    lines, lunch_total, other_total, items_str = get_cart_summary(user_id)
    if not lines:
        return
    pickup_date = get_cart_pickup_date(user_id)
    if not pickup_date:
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ В корзине позиции на разные даты. Очистите корзину и соберите один заказ заново.",
        )
        return
    base = lunch_total + other_total
    if discount:
        disc_amt = int(lunch_total * 0.2)
        discounted_base = base - disc_amt
    else:
        disc_amt = 0
        discounted_base = base

    context.user_data["pickup_time"] = pickup_time
    context.user_data["pickup_date"] = pickup_date
    context.user_data["discount_active"] = bool(discount)
    balance = get_points_balance(user_id)
    max_points = min(balance, int(max(0, discounted_base) * POINTS_MAX_USE_RATE))
    current_points = int(context.user_data.get("points_to_use", 0))
    current_points = min(current_points, max_points)
    context.user_data["points_to_use"] = current_points
    final = max(0, discounted_base - current_points)
    context.user_data["final_total"] = final
    context.user_data["discount_amount"] = disc_amt
    request_token = secrets.token_urlsafe(18)
    context.user_data["request_token"] = request_token
    context.user_data["checkout_snapshot"] = {
        "items_str": items_str,
        "base": base,
        "pickup_date": pickup_date,
        "pickup_time": pickup_time,
        "discount": bool(discount),
        "discount_amount": disc_amt,
        "points_to_use": current_points,
        "final": final,
    }
    if max_points:
        points_btn = (
            f"↩️ Не использовать бонусы ({fmt(current_points)})"
            if current_points else f"⭐ Использовать бонусы: {fmt(max_points)}"
        )
        points_callback = "toggle_points"
    else:
        points_btn = "⭐ Бонусов для списания пока нет"
        points_callback = "ignore"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(points_btn, callback_data=points_callback)],
        [InlineKeyboardButton("💳 Перейти к оплате в Click", url=get_click_payment_url(final))],
        [InlineKeyboardButton("✅ Я оплатил(а) — подтвердить заказ", callback_data="confirm_order")],
        [InlineKeyboardButton("🔙 Назад", callback_data="select_time")],
    ])
    discount_line = f"\n🔥 Скидка на обеды: -{fmt(disc_amt)} сум" if disc_amt else ""
    caption = (
        f"<b>🧾 Проверьте заказ</b>\n\n"
        f"📅 Дата выдачи: <b>{display_date(pickup_date)}</b>\n"
        f"🕒 Время выдачи: <b>{pickup_time}</b>\n"
        f"⭐ Бонусов используется: {fmt(current_points)}"
        f"{discount_line}\n"
        f"💰 К оплате через Click: <b>{fmt(final)} сум</b>\n\n"
        f"Перейдите в Click, завершите оплату, затем вернитесь и подтвердите заказ."
    )
    last_mid = context.user_data.get("last_msg_id")
    try:
        await context.bot.delete_message(chat_id=user_id, message_id=last_mid)
    except Exception:
        pass
    if reply:
        try:
            msg = await source.reply_photo(photo=CART_BANNER, caption=caption, reply_markup=kb, parse_mode="HTML")
        except Exception:
            msg = await source.reply_text(text=caption, reply_markup=kb, parse_mode="HTML")
    else:
        try:
            msg = await context.bot.send_photo(chat_id=user_id, photo=CART_BANNER, caption=caption, reply_markup=kb, parse_mode="HTML")
        except Exception:
            msg = await context.bot.send_message(chat_id=user_id, text=caption, reply_markup=kb, parse_mode="HTML")
    context.user_data["last_msg_id"] = msg.message_id

# ============================================================
# MAIN CALLBACK HANDLER
# ============================================================
async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    data = q.data
    last = context.user_data.get("last_msg_id", q.message.message_id)

    if data == "ignore":
        await q.answer()
        return

    ordering_action = (
        data in {"lunch_today", "select_time", "postpone_time", "time_custom", "toggle_points", "confirm_order"}
        or data.startswith(("start_day_", "lh_", "lg_", "ls_", "ld_", "add_", "tv_"))
    )
    if ordering_action and not menu_is_active():
        await q.answer("⛔ Приём заказов сейчас закрыт.", show_alert=True)
        return
    if ordering_action and not get_user(user_id):
        await q.answer("Сначала выполните /start и поделитесь своим номером.", show_alert=True)
        return

    if data == "profile":
        await q.answer()
        await show_profile(user_id, context)
        return

    if data == "toggle_points":
        current_snapshot = context.user_data.get("checkout_snapshot")
        if not current_snapshot:
            await q.answer("Экран оформления устарел. Откройте корзину заново.", show_alert=True)
            return
        current = int(context.user_data.get("points_to_use", 0))
        context.user_data["points_to_use"] = 0 if current else 10**12
        await q.answer()
        stored_time = current_snapshot["pickup_time"]
        await _show_checkout(
            None,
            context,
            user_id,
            stored_time,
            discount=bool(current_snapshot.get("discount", False)),
        )
        return

    # ------------------------ ADMIN ------------------------
    if data.startswith("adm_") or data.startswith("setstatus_"):
        if user_id != ADMIN_ID:
            await q.answer("⛔ Доступ закрыт.", show_alert=True)
            return

        if data.startswith("setstatus_"):
            _, order_id_str, new_status = data.split("_", 2)
            order_id = int(order_id_str)
            if not set_order_status(order_id, new_status):
                await q.answer("Ошибка статуса", show_alert=True)
                return
            await q.answer(f"Статус: {ORDER_STATUSES.get(new_status)}", show_alert=True)
            order = get_order(order_id)
            if order:
                notif_map = {
                    "cooking": f"👨‍🍳 <b>Заказ #{order_id} готовится!</b>\nОжидание 10–15 минут.",
                    "ready": f"✅ <b>Заказ #{order_id} готов!</b>\nЗабирайте на 4 этаже! 🎉",
                    "delivered": (
                        f"🎉 <b>Заказ #{order_id} выдан.</b>\nПриятного аппетита!\n"
                        f"⭐ Начислено бонусов: {fmt(order['points_earned'])}"
                    ),
                    "cancelled": f"❌ <b>Заказ #{order_id} отменён.</b>\nСписанные бонусы возвращены.",
                }
                if new_status in notif_map:
                    try:
                        await context.bot.send_message(
                            chat_id=order["user_id"],
                            text=notif_map[new_status],
                            reply_markup=kb_home() if new_status == "delivered" else None,
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
            try:
                await q.message.edit_reply_markup(reply_markup=kb_order_status(order_id, new_status))
            except Exception:
                pass
            return

        await q.answer()
        if data == "adm_stats":
            count, revenue = get_today_stats()
            users_count = len(get_all_user_ids())
            active_count = len(get_active_orders())
            await q.message.reply_text(
                f"<b>📊 Статистика</b>\n\n"
                f"👥 Пользователей: <b>{users_count}</b>\n"
                f"🛒 Заказов сегодня: <b>{count}</b>\n"
                f"💰 Сумма заказов сегодня: <b>{fmt(revenue)} сум</b>\n"
                f"🔄 Активных заказов: <b>{active_count}</b>",
                parse_mode="HTML",
            )
        elif data == "adm_kitchen":
            summary = get_kitchen_summary()
            if not summary:
                await q.message.reply_text("<b>🍽 Сегодня пока нет заказов для кухни.</b>", parse_mode="HTML")
                return
            grouped = {}
            for kind, name, qty in summary:
                grouped.setdefault(kind, []).append((name, qty))
            labels = {
                "hot": "🥩 Горячее",
                "garnish": "🍚 Гарниры",
                "salad": "🥗 Салаты",
                "drink": "🥤 Напитки",
                "fresh": "🍹 Фреши",
                "other": "📦 Прочее",
            }
            blocks = ["<b>🍽 Сводка для кухни</b>"]
            for kind in ["hot", "garnish", "salad", "drink", "fresh", "other"]:
                if kind in grouped:
                    blocks.append(f"\n<b>{labels[kind]}</b>")
                    blocks.extend([f"• {esc(name)} — <b>{qty} шт.</b>" for name, qty in grouped[kind]])
            await q.message.reply_text("\n".join(blocks), parse_mode="HTML")
        elif data == "adm_orders":
            orders = get_active_orders()
            if not orders:
                await q.message.reply_text("<b>📋 Сейчас нет активных заказов.</b>", parse_mode="HTML")
                return
            for o in orders[:15]:
                comment_line = f"\n📝 {esc(o['comment'])}" if o.get("comment") else ""
                txt = (
                    f"<b>Заказ #{o['order_id']}</b> | {ORDER_STATUSES.get(o['status'], o['status'])}\n"
                    f"📅 {display_date(o['pickup_date'] or o['created_at'][:10])}\n"
                    f"🕒 {o['pickup_time']}\n"
                    f"💰 {fmt(o['total'])} сум\n"
                    f"<i>{esc(o['items'][:700])}</i>{comment_line}"
                )
                await q.message.reply_text(
                    txt, reply_markup=kb_order_status(o["order_id"], o["status"]), parse_mode="HTML"
                )
        elif data == "adm_postmenu":
            post_kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Пн", callback_data="adm_postday_mon"),
                    InlineKeyboardButton("Вт", callback_data="adm_postday_tue"),
                    InlineKeyboardButton("Ср", callback_data="adm_postday_wed"),
                ],
                [
                    InlineKeyboardButton("Чт", callback_data="adm_postday_thu"),
                    InlineKeyboardButton("Пт", callback_data="adm_postday_fri"),
                ],
            ])
            await q.message.reply_text(
                "<b>📣 Какой пост опубликовать в канал?</b>",
                reply_markup=post_kb,
                parse_mode="HTML",
            )
        elif data.startswith("adm_postday_"):
            await publish_day_post(data.rsplit("_", 1)[1], context, q.message)
        elif data == "adm_broadcast":
            context.user_data["state"] = "BROADCAST"
            await q.message.reply_text("<b>📢 Отправьте сообщение для рассылки — текст или фото.\nЧтобы отменить, напишите «отмена».</b>", parse_mode="HTML")
        elif data == "adm_add":
            cats = [c for c in get_all_categories() if c["id"] not in LUNCH_CAT_IDS]
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(c["name"], callback_data=f"adm_addcat_{c['id']}")] for c in cats
            ])
            await q.message.reply_text("<b>Выберите раздел, куда добавить блюдо:</b>", reply_markup=kb, parse_mode="HTML")
        elif data.startswith("adm_addcat_"):
            cat_id = data.split("_", 2)[2]
            context.user_data["state"] = "DISH_NAME"
            context.user_data["new_dish"] = {"cat_id": cat_id}
            await q.message.reply_text("<b>Введите название нового блюда:</b>", parse_mode="HTML")
        elif data == "adm_del":
            cats = [c for c in get_all_categories() if c["id"] not in LUNCH_CAT_IDS]
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(c["name"], callback_data=f"adm_delcat_{c['id']}")] for c in cats
            ])
            await q.message.reply_text("<b>Выберите раздел, из которого удалить блюдо:</b>", reply_markup=kb, parse_mode="HTML")
        elif data.startswith("adm_delcat_"):
            cat_id = data.split("_", 2)[2]
            items = get_items(cat_id)
            if not items:
                await q.message.reply_text("<b>В этом разделе пока нет блюд.</b>", parse_mode="HTML")
                return
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(i["name"], callback_data=f"adm_delitem_{i['id']}")] for i in items
            ])
            await q.message.reply_text("<b>Выберите блюдо, которое нужно удалить:</b>", reply_markup=kb, parse_mode="HTML")
        elif data.startswith("adm_delitem_"):
            delete_dish(data.split("_")[2])
            await q.message.reply_text("<b>✅ Блюдо удалено из меню.</b>", parse_mode="HTML")
        elif data == "adm_export":
            rows = get_all_orders_for_export()
            if not rows:
                await q.message.reply_text("Нет данных для экспорта.")
                return
            fname = f"report_{local_now().strftime('%Y%m%d_%H%M')}.csv"
            text_buffer = StringIO(newline="")
            w = csv.writer(text_buffer, delimiter=";")
            w.writerow([
                "ID", "Создан", "Дата выдачи", "Телефон", "Состав", "Сумма", "Статус",
                "Время выдачи", "Комментарий", "Скидка", "Бонусы списаны", "Бонусы начислены",
            ])
            for r in rows:
                phone = str(r["phone"] or "")
                if phone and not phone.startswith("+"):
                    phone = "+" + phone
                w.writerow([
                    r["order_id"], r["created_at"], r["pickup_date"] or "", f'="{phone}"',
                    r["items"].replace("\n", " | "), r["total"],
                    ORDER_STATUSES.get(r["status"], r["status"]), r["pickup_time"], r["comment"] or "",
                    r["discount_amount"],
                    r["points_used"], r["points_earned"],
                ])
            document = BytesIO(text_buffer.getvalue().encode("utf-8-sig"))
            document.name = fname
            await context.bot.send_document(
                chat_id=user_id,
                document=document,
                caption="<b>📥 Отчёт готов.</b>",
                parse_mode="HTML",
            )
        elif data == "adm_toggle":
            new_state = not menu_is_active()
            set_menu_active(new_state)
            status = "ОТКРЫТ ✅" if new_state else "ЗАКРЫТ ⛔"
            await q.message.reply_text(f"Приём заказов: {status}")
        return

    # ------------------------ NAVIGATION ------------------------
    if data == "home":
        await q.answer()
        context.user_data["state"] = None
        reset_lunch_session(context)
        await show_main(user_id, context)
        return

    if data == "nav_drinks":
        await q.answer()
        await send_or_edit(user_id, last,
                           "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?q=80&w=1200&auto=format&fit=crop",
                           "<b>🥤 Напитки</b>\n\nВыберите категорию:", kb_drinks(), context)
        return

    if data == "nav_week":
        await q.answer()
        await send_or_edit(user_id, last, MAIN_BANNER,
                           "<b>🗓 Меню на неделю</b>\n\nВыберите день:", kb_week(), context)
        return

    if data == "lunch_today":
        pickup_date = next_business_date()
        pickup_day = datetime.strptime(pickup_date, "%Y-%m-%d").weekday()
        day_id = WEEKDAYS[pickup_day][0]
        if not cart_accepts_date(user_id, pickup_date):
            await q.answer(
                "В корзине уже есть заказ на другую дату. Сначала очистите корзину.",
                show_alert=True,
            )
            return
        if pickup_date != local_now().date().isoformat():
            await q.answer(
                f"Открыт предзаказ на {display_date(pickup_date)}.",
                show_alert=True,
            )
        else:
            await q.answer()
        reset_lunch_session(context)
        context.user_data["lunch"]["day_id"] = day_id
        context.user_data["lunch"]["pickup_date"] = pickup_date
        cfg, hot = get_lunch_config(day_id)
        if not hot or not cfg:
            await q.message.reply_text("❌ Меню на этот день пока не настроено.")
            return
        day_name = get_category(day_id)["name"]
        caption = build_day_caption(day_id, day_name, pickup_date=pickup_date)
        await send_or_edit(
            user_id, last, get_day_poster(day_id, cfg), caption, kb_lunch_hot(hot), context
        )
        return

    if data.startswith("day_"):
        day_id = data.split("_", 1)[1]
        cfg, hot = get_lunch_config(day_id)
        if not cfg or not hot:
            await q.answer("Меню дня не настроено.", show_alert=True)
            return
        await q.answer()
        context.user_data["preview_day"] = day_id
        pickup_date = next_date_for_day(day_id)
        day_name = get_category(day_id)["name"]
        caption = build_day_caption(day_id, day_name, pickup_date=pickup_date)
        await send_or_edit(user_id, last, get_day_poster(day_id, cfg), caption,
                           InlineKeyboardMarkup([
                               [InlineKeyboardButton("🍱 Заказать этот обед", callback_data=f"start_day_{day_id}")],
                               [InlineKeyboardButton("🔙 Назад", callback_data="nav_week")],
                           ]), context)
        return

    if data.startswith("start_day_"):
        day_id = data.split("_", 2)[2]
        pickup_date = next_date_for_day(day_id)
        if not pickup_date:
            await q.answer("Некорректный день.", show_alert=True)
            return
        if not cart_accepts_date(user_id, pickup_date):
            await q.answer(
                "В корзине уже есть заказ на другую дату. Сначала очистите корзину.",
                show_alert=True,
            )
            return
        cfg, hot = get_lunch_config(day_id)
        if not cfg or not hot:
            await q.answer("Меню дня не настроено.", show_alert=True)
            return
        reset_lunch_session(context)
        context.user_data["lunch"]["day_id"] = day_id
        context.user_data["lunch"]["pickup_date"] = pickup_date
        await q.answer()
        caption = build_day_caption(
            day_id, get_category(day_id)["name"], pickup_date=pickup_date
        )
        await send_or_edit(
            user_id, last, get_day_poster(day_id, cfg), caption, kb_lunch_hot(hot), context
        )
        return

    # ------------------------ LUNCH FLOW ------------------------
    if data.startswith("lh_"):
        hot_id = int(data.split("_", 1)[1])
        session = lunch_session(context)
        cfg, hot = get_lunch_config(session["day_id"] or current_day()[0])
        selected = next((h for h in hot if h["id"] == hot_id), None)
        if not selected:
            await q.answer("Блюдо недоступно.", show_alert=True)
            return
        session["hot_id"] = hot_id
        session["hot_name"] = selected["name"]
        session["hot_price"] = selected["price"]
        session["hot_image"] = selected.get("image")
        await q.answer()
        caption = (
            f"<b>2️⃣ Выберите гарнир</b>\n\n"
            f"🔥 {selected['name']}\n"
            f"Цена комплекса зависит от выбранного горячего блюда.\n\n"
            f"🍚 {cfg['garnish1']}\n🌾 {cfg['garnish2']}\n🥔 {cfg['garnish3']}"
        )
        await send_or_edit(
            user_id, last, selected.get("image") or get_day_poster(session["day_id"], cfg),
            caption, kb_lunch_garnishes(cfg), context,
        )
        return

    if data == "lunch_hot_back":
        session = lunch_session(context)
        day_id = session.get("day_id") or current_day()[0]
        cfg, hot = get_lunch_config(day_id)
        await q.answer()
        pickup_date = session.get("pickup_date") or next_date_for_day(day_id)
        caption = build_day_caption(
            day_id, get_category(day_id)["name"],
            pickup_date=pickup_date,
        )
        await send_or_edit(
            user_id, last, get_day_poster(day_id, cfg),
            caption, kb_lunch_hot(hot), context,
        )
        return

    if data.startswith("lg_"):
        try:
            garnish_index = int(data.split("_", 1)[1])
        except ValueError:
            await q.answer("Некорректный гарнир.", show_alert=True)
            return
        session = lunch_session(context)
        cfg, _ = get_lunch_config(session["day_id"])
        garnish = get_garnish_by_index(cfg, garnish_index) if cfg else None
        if not garnish:
            await q.answer("Такого гарнира нет.", show_alert=True)
            return
        session["garnish"] = garnish
        session["garnish_index"] = garnish_index
        session["salad_code"] = None
        session["salad_name"] = None
        session["drink_code"] = None
        session["drink_name"] = None
        await q.answer()
        caption = (
            f"<b>3️⃣ Салат — по желанию</b>\n\n"
            f"🔥 {session['hot_name']}\n"
            f"🍚 Гарнир: {garnish}\n\n"
            f"🥗 Сегодня: {cfg['salad']}\n"
            f"{cfg.get('salad_description') or ''}\n"
            f"Если салат не хотите, просто выберите «Без салата»."
        )
        await send_or_edit(
            user_id, last, cfg.get("salad_image") or session.get("hot_image") or LUNCH_BANNER,
            caption, kb_lunch_salad(), context,
        )
        return

    if data == "lunch_salad_back":
        session = lunch_session(context)
        cfg = get_lunch_config(session.get("day_id") or current_day()[0])[0]
        await q.answer()
        caption = (
            f"<b>2️⃣ Выберите гарнир</b>\n\n"
            f"🔥 {session['hot_name']}\n\n"
            f"🍚 {cfg['garnish1']}\n🌾 {cfg['garnish2']}\n🥔 {cfg['garnish3']}"
        )
        await send_or_edit(
            user_id, last, session.get("hot_image") or get_day_poster(session.get("day_id"), cfg),
            caption, kb_lunch_garnishes(cfg), context,
        )
        return

    if data in {"ls_keep", "ls_none"}:
        session = lunch_session(context)
        cfg = get_lunch_config(session.get("day_id") or current_day()[0])[0]
        if not cfg or not session.get("garnish"):
            await q.answer("Сначала выберите гарнир.", show_alert=True)
            return
        session["salad_code"] = "keep" if data == "ls_keep" else "none"
        session["salad_name"] = cfg["salad"] if data == "ls_keep" else None
        await q.answer("🥗 Салат оставлен" if data == "ls_keep" else "🚫 Без салата")
        salad_text = cfg["salad"] if data == "ls_keep" else "🚫 Без салата"
        caption = (
            f"<b>4️⃣ Выберите напиток</b>\n\n"
            f"🔥 {session['hot_name']}\n"
            f"🍚 Гарнир: {session['garnish']}\n"
            f"🥗 Салат: {salad_text}\n\n"
            f"🥤 Напиток — по желанию: Шербет, Айс-ти или без напитка."
        )
        await send_or_edit(
            user_id, last, cfg.get("salad_image") or session.get("hot_image") or LUNCH_BANNER,
            caption, kb_lunch_drinks(), context,
        )
        return

    if data == "lunch_drink_back":
        session = lunch_session(context)
        cfg = get_lunch_config(session.get("day_id") or current_day()[0])[0]
        await q.answer()
        caption = (
            f"<b>3️⃣ Салат — по желанию</b>\n\n"
            f"🔥 {esc(session['hot_name'])}\n"
            f"🍚 Гарнир: {esc(session['garnish'])}\n\n"
            f"🥗 Сегодня: {esc(cfg['salad'])}\n"
            f"{esc(cfg.get('salad_description') or '')}\n"
            f"Если салат не хотите, выберите «Без салата»."
        )
        await send_or_edit(
            user_id, last, cfg.get("salad_image") or session.get("hot_image") or LUNCH_BANNER,
            caption, kb_lunch_salad(), context,
        )
        return

    if data.startswith("ld_"):
        drink_code = data.split("_", 1)[1]
        drink_name = LUNCH_DRINKS.get(drink_code)
        if drink_code not in LUNCH_DRINKS:
            await q.answer("Такого варианта напитка нет. Выберите один из предложенных.", show_alert=True)
            return
        session = lunch_session(context)
        cfg, _ = get_lunch_config(session["day_id"])
        if not cfg or not session.get("garnish") or session.get("salad_code") is None:
            await q.answer("Сначала выберите салат — затем напиток.", show_alert=True)
            return
        session["drink_code"] = drink_code
        session["drink_name"] = drink_name
        combo_id = lunch_combo_item_id(session)
        combo_name = lunch_combo_name(cfg, session)
        pickup_date = session.get("pickup_date") or next_date_for_day(session["day_id"])
        if not cart_accepts_date(user_id, pickup_date):
            await q.answer(
                "В корзине уже есть заказ на другую дату. Сначала очистите корзину.",
                show_alert=True,
            )
            return
        update_cart(user_id, combo_id, combo_name, session["hot_price"], 1, pickup_date)

        context.user_data["lunch_components"] = [
            ("hot", session["hot_name"], 1, session["hot_price"]),
            ("garnish", session["garnish"], 1, 0),
        ] + ([] if session.get("salad_code") == "none" else [("salad", cfg["salad"], 1, 0)]) \
          + ([] if drink_code == "none" else [("drink", drink_name, 1, 0)])
        await q.answer(f"✅ {drink_name}")
        await send_or_edit(
            user_id,
            last,
            CART_BANNER,
            f"<b>✅ Комплекс добавлен в корзину</b>\n"
            f"📅 {display_date(pickup_date)}\n\n{esc(combo_name)}\n\n💰 {fmt(session['hot_price'])} сум",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Перейти в корзину", callback_data="cart_view")],
                [InlineKeyboardButton("🍹 Добавить фреш", callback_data="cat_fresh_drinks")],
                [InlineKeyboardButton("🏠 В меню", callback_data="home")],
            ]),
            context,
        )
        return

    if data == "lunch_combo_done":
        session = lunch_session(context)
        cfg = get_lunch_config(session.get("day_id") or current_day()[0])[0]
        if not cfg or session.get("drink_code") is None or session.get("salad_code") is None or not session.get("garnish"):
            await q.answer("Сначала соберите комплекс.", show_alert=True)
            return
        combo_name = lunch_combo_name(cfg, session)
        await q.answer()
        await send_or_edit(
            user_id, last, CART_BANNER,
            f"<b>🍱 Ваш комплекс готов</b>\n\n{combo_name}\n\n💰 {fmt(session['hot_price'])} сум",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Перейти в корзину", callback_data="cart_view")],
                [InlineKeyboardButton("🍹 Добавить ещё фреш", callback_data="cat_fresh_drinks")],
                [InlineKeyboardButton("🏠 В меню", callback_data="home")],
            ]),
            context,
        )
        return

    # ------------------------ CATEGORIES / CART ------------------------
    if data.startswith("cat_"):
        cat_id = data[4:]
        items = get_items(cat_id)
        cat = get_category(cat_id)
        if not items or not cat:
            await q.answer("Раздел пуст.", show_alert=True)
            return
        await q.answer()
        caption = f"<b>{esc(cat['name'])}</b>\n\n" + "\n\n".join(
            [f"▪️ <b>{esc(i['name'])}</b> — {fmt(i['price'])} сум\n<i>{esc(i['description'])}</i>" for i in items]
        )
        caption = caption[:4000]
        markup = kb_category(user_id, cat_id, items)
        # Если пользователь пришёл из собранного комплекса, позволяем вернуться
        # прямо к готовому комплексу, не теряя выбранные горячее/гарнир/напиток.
        session = lunch_session(context)
        if cat_id == "fresh_drinks" and session.get("drink_code") and session.get("garnish"):
            rows = list(markup.inline_keyboard[:-1])
            rows.append([InlineKeyboardButton("🛒 Корзина", callback_data="cart_view"),
                         InlineKeyboardButton("🔙 К комплексу", callback_data="lunch_combo_done")])
            markup = InlineKeyboardMarkup(rows)
        await send_or_edit(user_id, last, cat["banner"], caption, markup, context)
        return

    if data.startswith("add_") or data.startswith("rm_"):
        action = "add" if data.startswith("add_") else "rm"
        parts = data.split("_")
        item_id = parts[-1]
        cat_id = "_".join(parts[1:-1])
        item = next((i for i in get_items(cat_id) if str(i["id"]) == item_id), None)
        if not item:
            await q.answer()
            return
        current = get_cart(user_id).get(item_id, {}).get("count", 0)
        new_cnt = current + (1 if action == "add" else -1)
        if new_cnt > 20:
            await q.answer("Максимум 20 одинаковых позиций.", show_alert=True)
            return
        pickup_date = get_cart_pickup_date(user_id)
        update_cart(user_id, item_id, item["name"], item["price"], max(new_cnt, 0), pickup_date)
        await q.answer("➕ Добавлено" if action == "add" else "➖ Удалено")
        await context.bot.edit_message_reply_markup(
            chat_id=user_id, message_id=last, reply_markup=kb_category(user_id, cat_id, get_items(cat_id))
        )
        return

    if data == "cart_view":
        await q.answer()
        lines, lunch, other, _ = get_cart_summary(user_id)
        if not lines:
            await send_or_edit(user_id, last, CART_BANNER, "<b>🛒 Корзина пуста!</b>", kb_main(), context)
            return
        total = lunch + other
        pickup_date = get_cart_pickup_date(user_id)
        await send_or_edit(
            user_id,
            last,
            CART_BANNER,
            f"<b>🛒 Ваш заказ</b>\n"
            f"📅 Дата выдачи: <b>{display_date(pickup_date)}</b>\n\n"
            f"{lines}\n\n<b>Итого: {fmt(total)} сум</b>\n\nПерейти к оформлению?",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Оформить заказ", callback_data="select_time")],
                [InlineKeyboardButton("🗑 Очистить корзину", callback_data="cart_clear"),
                 InlineKeyboardButton("🔙 В меню", callback_data="home")],
            ]),
            context,
        )
        return

    if data == "cart_clear":
        await q.answer("Очищено")
        clear_cart(user_id)
        reset_lunch_session(context)
        await show_main(user_id, context)
        return

    if data == "select_time":
        lines, lunch, _, _ = get_cart_summary(user_id)
        if not lines:
            await q.answer("Корзина пуста.", show_alert=True)
            return
        pickup_date = get_cart_pickup_date(user_id)
        if not pickup_date:
            await q.answer("В корзине позиции на разные даты.", show_alert=True)
            return
        context.user_data["state"] = None
        context.user_data["pickup_date"] = pickup_date
        is_today = pickup_date == local_now().date().isoformat()
        time_hint = (
            "Выберите доступный вариант выдачи:"
            if is_today
            else "Заказ оформляется заранее. Выберите удобное время:"
        )
        await q.answer()
        await send_or_edit(
            user_id, last, CART_BANNER,
            f"<b>🕒 Выберите время выдачи заказа</b>\n\n"
            f"📅 <b>{display_pickup_date(pickup_date)}</b>\n"
            f"{time_hint}\n\n"
            f"Обычная выдача: 11:00–16:00.",
            kb_time(pickup_date, has_lunch=lunch > 0), context
        )
        return

    if data == "postpone_time":
        await q.answer()
        pickup_date = context.user_data.get("pickup_date") or get_cart_pickup_date(user_id)
        await send_or_edit(
            user_id, last, CART_BANNER,
            f"<b>🕒 Выберите время выдачи заказа</b>\n\n"
            f"📅 <b>{display_pickup_date(pickup_date)}</b>\n"
            f"Выберите удобное время выдачи или укажите своё:",
            kb_postpone_time(pickup_date), context
        )
        return

    if data == "time_custom":
        await q.answer()
        context.user_data["state"] = "CUSTOM_TIME"
        pickup_date = context.user_data.get("pickup_date") or get_cart_pickup_date(user_id)
        await send_or_edit(
            user_id, last, CART_BANNER,
            f"<b>✍️ Укажите своё время</b>\n\n"
            f"📅 <b>{display_pickup_date(pickup_date)}</b>\n"
            f"Напишите время выдачи в формате <b>ЧЧ:ММ</b>, например <b>14:45</b>.",
            InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="select_time")]]),
            context,
        )
        return

    # ------------------------ PICKUP TIME / CHECKOUT ------------------------
    if data.startswith("tv_"):
        time_val = data[3:]
        pickup_date = context.user_data.get("pickup_date") or get_cart_pickup_date(user_id)
        if time_val == "discount":
            if pickup_date != local_now().date().isoformat() or local_now().hour != 16:
                await q.answer(
                    "⚠️ Скидка доступна только для заказов на сегодня с 16:00 до 17:00.",
                    show_alert=True,
                )
                return
            _, lunch, _, _ = get_cart_summary(user_id)
            if lunch == 0:
                await q.answer("⚠️ Скидка действует только на комплексные обеды. В корзине нет комплексного обеда.", show_alert=True)
                return
            await q.answer()
            context.user_data["points_to_use"] = 0
            await _show_checkout(None, context, user_id, "16:00–17:00", discount=True)
        else:
            if time_val == "Сейчас (В очереди)":
                now_time = local_now().time().replace(tzinfo=None)
                if pickup_date != local_now().date().isoformat():
                    await q.answer(
                        f"Заказ назначен на {display_date(pickup_date)}. "
                        "Выберите время выдачи для этой даты.",
                        show_alert=True,
                    )
                    return
                if not (t_time(11, 0) <= now_time < t_time(17, 0)):
                    await q.answer(
                        "«Забрать сейчас» доступно сегодня с 11:00 до 17:00.",
                        show_alert=True,
                    )
                    return
            else:
                try:
                    selected_time = datetime.strptime(time_val, "%H:%M").time()
                except ValueError:
                    await q.answer("Некорректное время.", show_alert=True)
                    return
                if not pickup_time_is_available(pickup_date, selected_time):
                    await q.answer("Это время уже прошло.", show_alert=True)
                    return
            await q.answer()
            context.user_data["points_to_use"] = 0
            await _show_checkout(None, context, user_id, time_val)
        return

    if data == "paid":
        await q.answer(
            "Эта кнопка из старой версии больше не действует. Откройте корзину заново.",
            show_alert=True,
        )
        return

    if data == "confirm_order":
        await q.answer()
        lines, lunch, other, items_str = get_cart_summary(user_id)
        if not lines:
            await context.bot.send_message(chat_id=user_id, text="⚠️ Корзина уже пуста.")
            return
        snapshot = context.user_data.get("checkout_snapshot")
        request_token = context.user_data.get("request_token")
        pickup_date = get_cart_pickup_date(user_id)
        if not snapshot or not request_token:
            await context.bot.send_message(
                chat_id=user_id,
                text="⚠️ Экран оформления устарел. Откройте корзину и подтвердите заказ заново.",
            )
            return
        if (
            snapshot.get("items_str") != items_str
            or snapshot.get("base") != lunch + other
            or snapshot.get("pickup_date") != pickup_date
        ):
            await context.bot.send_message(
                chat_id=user_id,
                text="⚠️ Корзина изменилась после расчёта. Откройте её и проверьте сумму заново.",
            )
            return
        final = int(snapshot["final"])
        pickup_time = snapshot["pickup_time"]
        discount_amount = int(snapshot["discount_amount"])

        components = []
        for item_id, item in get_cart(user_id).items():
            if str(item_id).startswith("lunch_"):
                parts = str(item_id).split("_")
                if len(parts) == 6 and parts[3].startswith("g") and parts[4].startswith("s"):
                    day_id = parts[1]
                    try:
                        hot_id = int(parts[2])
                        garnish_index = int(parts[3][1:])
                        salad_code = parts[4][1:]
                    except ValueError:
                        hot_id = None
                        garnish_index = None
                        salad_code = None
                    drink_code = parts[5]
                    drink_name = LUNCH_DRINKS.get(drink_code)
                    cfg, hot_items = get_lunch_config(day_id)
                    hot = next((h for h in hot_items if h["id"] == hot_id), None)
                    garnish = get_garnish_by_index(cfg, garnish_index) if cfg and garnish_index else None
                    if cfg and hot and garnish and salad_code in {"keep", "none"} and drink_name:
                        qty = item["count"]
                        components.extend([
                            ("hot", hot["name"], qty, hot["price"]),
                            ("garnish", garnish, qty, 0),
                        ])
                        if salad_code != "none":
                            components.append(("salad", cfg["salad"], qty, 0))
                        if drink_code != "none":
                            components.append(("drink", drink_name, qty, 0))
            else:
                components.append(("other", item["name"], item["count"], item["price"]))

        # Фреши определяем по категории menu_items, а не по названию.
        conn = _conn()
        fresh_ids = {str(r["id"]) for r in conn.execute(
            "SELECT id FROM menu_items WHERE cat_id='fresh_drinks'"
        ).fetchall()}
        conn.close()
        fresh_names = {item["name"] for item_id, item in get_cart(user_id).items() if str(item_id) in fresh_ids}
        components = [
            ("fresh" if item_name in fresh_names and item_type == "other" else item_type,
             item_name, qty, unit_price)
            for item_type, item_name, qty, unit_price in components
        ]

        points_to_use = int(snapshot["points_to_use"])
        order_id, points_used, points_earned, qr_token, created = create_order(
            user_id,
            items_str,
            final,
            pickup_time,
            pickup_date,
            request_token,
            discount_amount=discount_amount,
            components=components,
            points_used=points_to_use,
        )
        if not created:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"ℹ️ Заказ #{order_id} уже был создан. Повторное оформление не выполнено.",
            )
            return
        clear_cart(user_id)
        reset_lunch_session(context)
        context.user_data["lunch_components"] = []

        name = esc(q.from_user.first_name + (f" {q.from_user.last_name}" if q.from_user.last_name else ""))
        username = f" (@{esc(q.from_user.username)})" if q.from_user.username else ""
        balance_after = get_points_balance(user_id)
        bot_info = await context.bot.get_me()
        pickup_link = get_pickup_link(bot_info.username, qr_token)
        qr_image = build_qr_image(pickup_link)
        text = (
            f"<b>✅ Заказ #{order_id} принят!</b>\n\n{lines}\n\n"
            f"📍 Место выдачи: 4 этаж, кухня\n"
            f"📅 Дата: {display_date(pickup_date)}\n"
            f"🕒 Время: {pickup_time}\n"
            f"💰 Оплата через Click: {fmt(final)} сум\n\n"
            f"⭐ Списано бонусов: {fmt(points_used)}\n"
            f"⭐ Будет начислено после выдачи: +{fmt(points_earned)}\n"
            f"⭐ Текущий баланс: {fmt(balance_after)} бонусов\n\n"
            f"📱 Покажите QR-код сотруднику при получении.\n"
            f"Спасибо, что выбираете нас ❤️\nБудем рады видеть вас снова!"
        )
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=last)
        except Exception:
            pass
        try:
            msg = await context.bot.send_photo(chat_id=user_id, photo=qr_image, caption=text, parse_mode="HTML")
        except Exception:
            msg = await context.bot.send_message(chat_id=user_id, text=text + f"\n\nQR: {pickup_link}", parse_mode="HTML")
        context.user_data["last_msg_id"] = msg.message_id
        context.user_data["points_to_use"] = 0
        context.user_data["request_token"] = None
        context.user_data["checkout_snapshot"] = None

        order_notification_chat_id = ORDER_CHANNEL_ID or ADMIN_ID
        if order_notification_chat_id:
            user_row = get_user(user_id)
            phone = user_row["phone"] if user_row else "нет"
            adm_txt = (
                f"🚨 <b>Новый заказ #{order_id}!</b>\n"
                f"👤 {name}{username}\n📞 {esc(phone)}\n"
                f"📅 {display_date(pickup_date)}\n🕒 {pickup_time}\n"
                f"💰 {fmt(final)} сум — клиент подтвердил оплату через Click\n"
                f"⭐ Списано баллов: {fmt(points_used)}\n"
                f"⭐ Будет начислено после выдачи: {fmt(points_earned)}\n\n"
                f"<b>Состав:</b>\n{lines}"
            )
            try:
                await context.bot.send_message(
                    chat_id=order_notification_chat_id,
                    text=adm_txt,
                    reply_markup=kb_order_status(order_id, "new"),
                    parse_mode="HTML",
                )
            except Exception:
                logging.exception(
                    "Не удалось отправить уведомление о заказе #%s",
                    order_id,
                )
        return

    await q.answer()

# ============================================================
# COMMANDS / SERVER
# ============================================================
async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start", "Главное меню"),
        BotCommand("app", "Открыть мини‑приложение"),
        BotCommand("admin", "Панель администратора"),
        BotCommand("post", "Опубликовать пост в канал"),
        BotCommand("myid", "Узнать свой Telegram ID"),
    ])


async def health(request):
    return web.Response(text="OK")


async def handle_error(update, context):
    error = context.error
    logging.error(
        "Необработанная ошибка Telegram-обработчика",
        exc_info=(type(error), error, error.__traceback__),
    )


async def main():
    if not TOKEN or TOKEN == "ВАШ_ТОКЕН":
        raise RuntimeError("BOT_TOKEN не установлен. Задайте переменную окружения перед запуском.")
    if ADMIN_ID <= 0:
        logging.warning("ADMIN_ID не установлен: административные функции будут недоступны.")

    init_db()
    app_bot = Application.builder().token(TOKEN).post_init(post_init).build()

    app_bot.add_handler(CommandHandler("start", cmd_start))
    app_bot.add_handler(CommandHandler("app", cmd_app))
    app_bot.add_handler(CommandHandler("admin", cmd_admin))
    app_bot.add_handler(CommandHandler("post", cmd_post))
    app_bot.add_handler(CommandHandler("myid", cmd_myid))
    app_bot.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app_bot.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app_bot.add_handler(CallbackQueryHandler(btn))
    app_bot.add_error_handler(handle_error)

    web_app = web.Application()
    web_app.router.add_get("/", health)
    runner = web.AppRunner(web_app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080))).start()

    initialized = False
    try:
        await app_bot.initialize()
        initialized = True
        await app_bot.start()
        await app_bot.updater.start_polling()
        logging.info(">>> Бот запущен <<<")
        await asyncio.Event().wait()
    finally:
        if app_bot.updater and app_bot.updater.running:
            await app_bot.updater.stop()
        if app_bot.running:
            await app_bot.stop()
        if initialized:
            await app_bot.shutdown()
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
