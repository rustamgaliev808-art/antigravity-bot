import os
import logging
import asyncio
import sqlite3
import csv
from datetime import datetime, time as t_time
from collections import Counter
from aiohttp import web
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    InputMediaPhoto,
    KeyboardButton,
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

TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel")
TZ_OFFSET = int(os.getenv("TZ_OFFSET", "5"))

CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID", "52528")
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "20421")
QR_FILE_NAME = "qr.jpg"

DB_NAME = os.getenv("DB_NAME", "click_lunch_v7.db")

MAIN_BANNER = "https://images.unsplash.com/photo-1498837167922-41cfa6f318ba?q=80&w=1200&auto=format&fit=crop"
CART_BANNER = "https://images.unsplash.com/photo-1556742044-3c52d6e88c62?q=80&w=1200&auto=format&fit=crop"
LUNCH_BANNER = "https://images.unsplash.com/photo-1543339308-43e59d6b73a6?q=80&w=1200&auto=format&fit=crop"
MON_BANNER = "https://images.unsplash.com/photo-1548943487-a2e4f43b4850?q=80&w=1200&auto=format&fit=crop"
FRESH_BANNER = "https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?q=80&w=1200&auto=format&fit=crop"
DISCOUNT_BANNER = "https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?q=80&w=1200&auto=format&fit=crop"

WEEKDAYS = {
    0: ("mon", "Понедельник"),
    1: ("tue", "Вторник"),
    2: ("wed", "Среда"),
    3: ("thu", "Четверг"),
    4: ("fri", "Пятница"),
}

LUNCH_CAT_IDS = {"mon", "tue", "wed", "thu", "fri"}

LUNCH_DRINKS = {
    "sherbet": "Шербет",
    "iced_tea": "Айс-ти",
}

ORDER_STATUSES = {
    "paid": "💳 Оплачен",
    "cooking": "👨‍🍳 Готовится",
    "ready": "✅ Готов к выдаче",
    "delivered": "🎉 Выдан",
}

# ============================================================
# DEFAULT MENU
# ============================================================
DEFAULT_CATEGORIES = [
    ("breakfasts", "Завтраки", "https://images.unsplash.com/photo-1533089860892-a7c6f0a88666?q=80&w=1200&auto=format&fit=crop"),
    ("hot_drinks", "Горячие напитки", "https://images.unsplash.com/photo-1497935586351-b67a49e012bf?q=80&w=1200&auto=format&fit=crop"),
    ("cold_drinks", "Холодные напитки", "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?q=80&w=1200&auto=format&fit=crop"),
    ("fresh_drinks", "Фреши", "https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?q=80&w=1200&auto=format&fit=crop"),
    ("mon", "Понедельник", MON_BANNER),
    ("tue", "Вторник", LUNCH_BANNER),
    ("wed", "Среда", LUNCH_BANNER),
    ("thu", "Четверг", LUNCH_BANNER),
    ("fri", "Пятница", LUNCH_BANNER),
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
    ("cold_drinks", "⚡🔞 Энергетик 18+ 0.5", "Тонизирующий напиток", 18000, ""),
    ("cold_drinks", "🐂 RedBull 0.25", "Классический энергетик в фирменной банке.", 32000, ""),

    ("fresh_drinks", "🍎 Яблочный фреш", "Свежевыжатый яблочный сок, 250 мл.", 27000, ""),
    ("fresh_drinks", "🥕 Морковный фреш", "Свежевыжатый морковный сок, 250 мл.", 16000, ""),
    ("fresh_drinks", "❤️ Свекольный фреш", "Свежевыжатый свекольный сок, 250 мл.", 16000, ""),
    ("fresh_drinks", "🍎🥕 Яблоко + Морковь", "Микс яблочного и морковного сока, 250 мл.", 19000, ""),
    ("fresh_drinks", "🍎❤️ Яблоко + Свёкла", "Микс яблочного и свекольного сока, 250 мл.", 19000, ""),
    ("fresh_drinks", "🥒🍎 Огурец + Яблоко", "Освежающий микс огурца и яблока, 250 мл.", 26000, ""),
]

DEFAULT_LUNCH = {
    "mon": {
        "hot": [
            ("🥩", "Говядина с овощами", "Говядина с овощами в соусе.", 63000),
            ("🍗", "Куриный казан-кебаб", "Курица с пряностями.", 58000),
        ],
        "salad": "Витаминный салат",
        "drink": "Шербет или Айс-ти",
        "garnishes": ["Рис", "Гречка", "Картофель"],
    },
    "tue": {
        "hot": [
            ("🥩", "Жаркое из говядины", "Сочное жаркое из говядины.", 63000),
            ("🍗", "Куриные котлеты", "Домашние куриные котлеты.", 58000),
        ],
        "salad": "Французский салат",
        "drink": "Шербет или Айс-ти",
        "garnishes": ["Перловка", "Пюре", "Рис"],
    },
    "wed": {
        "hot": [
            ("🥩", "Бефстроганов", "Нежная говядина в соусе.", 63000),
            ("🍗", "Куриная отбивная с сыром", "Куриная отбивная под сыром.", 58000),
        ],
        "salad": "Овощной салат",
        "drink": "Шербет или Айс-ти",
        "garnishes": ["Рис", "Гречка", "Картофель"],
    },
    "thu": {
        "hot": [
            ("🥩", "Плов из говядины", "Плов из говядины с морковью и специями.", 63000),
            ("🍗", "Куриный Ган-пан", "Курица в фирменной подаче.", 58000),
        ],
        "salad": "Ачик-чучук",
        "drink": "Шербет или Айс-ти",
        "garnishes": ["Рис", "Пюре", "Овощи"],
    },
    "fri": {
        "hot": [
            ("🥩", "Гуляш из говядины", "Сытный гуляш из говядины.", 63000),
            ("🍗", "Курица в соусе карри", "Курица в мягком соусе карри.", 58000),
        ],
        "salad": "Греческий салат",
        "drink": "Шербет или Айс-ти",
        "garnishes": ["Рис", "Пюре", "Овощи печёные"],
    },
}

# ============================================================
# TIME / HELPERS
# ============================================================
def local_now():
    ts = datetime.utcnow().timestamp() + TZ_OFFSET * 3600
    return datetime.utcfromtimestamp(ts)


def fmt(amount):
    return f"{amount:,}".replace(",", " ")


def current_day():
    return WEEKDAYS.get(local_now().weekday(), ("mon", "Понедельник"))

# ============================================================
# DATABASE
# ============================================================
def _conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _conn()
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON")

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        phone TEXT,
        orders_count INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS cart (
        user_id INTEGER,
        item_id TEXT,
        item_name TEXT,
        price INTEGER,
        count INTEGER,
        PRIMARY KEY (user_id, item_id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        items TEXT NOT NULL,
        total INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'paid',
        pickup_time TEXT,
        created_at TEXT NOT NULL,
        discount_amount INTEGER NOT NULL DEFAULT 0
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
        active INTEGER NOT NULL DEFAULT 1
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS order_components (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        component_type TEXT NOT NULL,
        component_name TEXT NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE
    )""")

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
    if c.execute("SELECT COUNT(*) AS n FROM menu_categories").fetchone()["n"] == 0:
        c.executemany("INSERT INTO menu_categories(id,name,banner) VALUES (?,?,?)", DEFAULT_CATEGORIES)
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
            "INSERT OR IGNORE INTO lunch_config(day_id,salad,drink,garnish1,garnish2,garnish3) VALUES (?,?,?,?,?,?)",
            (day_id, cfg["salad"], cfg["drink"], *cfg["garnishes"]),
        )
        existing = c.execute("SELECT COUNT(*) AS n FROM lunch_hot WHERE day_id=?", (day_id,)).fetchone()["n"]
        if existing == 0:
            for emoji, name, desc, price in cfg["hot"]:
                c.execute(
                    "INSERT INTO lunch_hot(day_id,emoji,name,description,price,active) VALUES (?,?,?,?,?,1)",
                    (day_id, emoji, name, desc, price),
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
        "INSERT INTO users(user_id,phone) VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET phone=excluded.phone",
        (user_id, phone),
    )
    conn.commit()
    conn.close()


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


# ✅ ФИХ #1: id возвращается как str — сравнение в btn() корректно
def get_items(cat_id):
    conn = _conn()
    rows = conn.execute(
        "SELECT id,name,description,price,image FROM menu_items WHERE cat_id=? ORDER BY id",
        (cat_id,),
    ).fetchall()
    conn.close()
    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "description": r["description"],
            "price": r["price"],
            "image": r["image"],
        }
        for r in rows
    ]


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
        "SELECT id,emoji,name,description,price FROM lunch_hot WHERE day_id=? AND active=1 ORDER BY id",
        (day_id,),
    ).fetchall()
    conn.close()
    return (dict(cfg) if cfg else None), [dict(x) for x in hot]


# ── Редактирование меню недели из /admin ──
def update_lunch_hot_dish(hot_id, name, price):
    conn = _conn()
    conn.execute("UPDATE lunch_hot SET name=?, price=? WHERE id=?", (name, price, hot_id))
    conn.commit()
    conn.close()


def update_lunch_salad(day_id, salad):
    conn = _conn()
    conn.execute("UPDATE lunch_config SET salad=? WHERE day_id=?", (salad, day_id))
    conn.commit()
    conn.close()


def update_lunch_garnishes(day_id, g1, g2, g3):
    conn = _conn()
    conn.execute(
        "UPDATE lunch_config SET garnish1=?, garnish2=?, garnish3=? WHERE day_id=?",
        (g1, g2, g3, day_id),
    )
    conn.commit()
    conn.close()


def get_cart(user_id):
    conn = _conn()
    rows = conn.execute(
        "SELECT item_id,item_name,price,count FROM cart WHERE user_id=? ORDER BY rowid",
        (user_id,),
    ).fetchall()
    conn.close()
    return {
        r["item_id"]: {"name": r["item_name"], "price": r["price"], "count": r["count"]}
        for r in rows
    }


def update_cart(user_id, item_id, item_name, price, count):
    conn = _conn()
    if count <= 0:
        conn.execute("DELETE FROM cart WHERE user_id=? AND item_id=?", (user_id, item_id))
    else:
        conn.execute(
            "INSERT INTO cart(user_id,item_id,item_name,price,count) VALUES (?,?,?,?,?) "
            "ON CONFLICT(user_id,item_id) DO UPDATE SET item_name=excluded.item_name,"
            "price=excluded.price,count=excluded.count",
            (user_id, item_id, item_name, price, count),
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
    conn = _conn()
    cat_map = {
        str(r["id"]): r["cat_id"]
        for r in conn.execute("SELECT id,cat_id FROM menu_items").fetchall()
    }
    conn.close()
    lines, short, lunch_total, other_total = [], [], 0, 0
    for item_id, data in cart.items():
        subtotal = data["price"] * data["count"]
        lines.append(f"• <b>{data['name']}</b> x{data['count']} — <b>{fmt(subtotal)} сум</b>")
        short.append(f"{data['name']} x{data['count']}")
        if str(item_id).startswith("lunch_") or cat_map.get(str(item_id)) in LUNCH_CAT_IDS:
            lunch_total += subtotal
        else:
            other_total += subtotal
    return "\n".join(lines), lunch_total, other_total, ", ".join(short)

# ============================================================
# ORDER STORAGE
# ============================================================
def create_order(user_id, items_str, total, pickup_time, discount_amount=0, components=None):
    components = components or []
    conn = _conn()
    now = local_now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders(user_id,items,total,status,pickup_time,created_at,discount_amount) VALUES (?,?,?,?,?,?,?)",
        (user_id, items_str, total, "paid", pickup_time, now, discount_amount),
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
    cur.execute("UPDATE users SET orders_count=orders_count+1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    return order_id


def set_order_status(order_id, status):
    if status not in ORDER_STATUSES:
        return False
    conn = _conn()
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
        "SELECT order_id,user_id,items,total,status,pickup_time,created_at FROM orders "
        "WHERE status!='delivered' ORDER BY "
        "CASE pickup_time WHEN 'Сейчас (В очереди)' THEN '00:00' ELSE pickup_time END, order_id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_today_stats():
    today = local_now().strftime("%Y-%m-%d")
    conn = _conn()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt, COALESCE(SUM(total),0) AS total FROM orders WHERE substr(created_at,1,10)=?",
        (today,),
    ).fetchone()
    conn.close()
    return row["cnt"], row["total"]


def get_kitchen_summary():
    today = local_now().strftime("%Y-%m-%d")
    conn = _conn()
    rows = conn.execute(
        "SELECT oi.item_type, oi.item_name, SUM(oi.quantity) AS qty "
        "FROM order_items oi JOIN orders o ON o.order_id=oi.order_id "
        "WHERE substr(o.created_at,1,10)=? AND o.status IN ('paid','cooking') "
        "GROUP BY oi.item_type, oi.item_name ORDER BY oi.item_type, qty DESC",
        (today,),
    ).fetchall()
    conn.close()
    return [(r["item_type"], r["item_name"], r["qty"]) for r in rows]


def get_all_orders_for_export():
    conn = _conn()
    rows = conn.execute(
        "SELECT o.order_id,o.created_at,u.phone,o.items,o.total,o.status,o.pickup_time,o.discount_amount "
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
            "day_id": None, "hot_id": None, "hot_name": None, "hot_price": 0,
            "garnish": None, "garnish_index": None, "drink_code": None, "drink_name": None,
        },
    )


def reset_lunch_session(context):
    context.user_data["lunch"] = {
        "day_id": None, "hot_id": None, "hot_name": None, "hot_price": 0,
        "garnish": None, "garnish_index": None, "drink_code": None, "drink_name": None,
    }


def lunch_combo_item_id(session):
    if (
        not session.get("day_id") or not session.get("hot_id")
        or not session.get("garnish_index") or not session.get("drink_code")
    ):
        return None
    return (
        f"lunch_{session['day_id']}_{session['hot_id']}"
        f"_g{session['garnish_index']}_{session['drink_code']}"
    )


def lunch_combo_name(cfg, session):
    return (
        f"🍱 {session['hot_name']} + {session['garnish']} + "
        f"{cfg['salad']} + {session['drink_name']}"
    )


def get_garnish_by_index(cfg, index):
    return {1: cfg["garnish1"], 2: cfg["garnish2"], 3: cfg["garnish3"]}.get(index)

# ============================================================
# KEYBOARDS
# ============================================================
def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🍱 Комплексный обед сегодня", callback_data="lunch_today")],
        [InlineKeyboardButton("🍳 Завтраки", callback_data="cat_breakfasts"),
         InlineKeyboardButton("🥤 Напитки", callback_data="nav_drinks")],
        [InlineKeyboardButton("🗓 Меню на неделю", callback_data="nav_week")],
        [InlineKeyboardButton("🛒 Корзина", callback_data="cart_view")],
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
        rows.append([InlineKeyboardButton(
            f"🍽 {item['name']} — {fmt(item['price'])} сум", callback_data="ignore")])
        if count:
            rows.append([
                InlineKeyboardButton("➖", callback_data=f"rm_{cat_id}_{iid}"),
                InlineKeyboardButton(f"{count} шт", callback_data="ignore"),
                InlineKeyboardButton("➕", callback_data=f"add_{cat_id}_{iid}"),
            ])
        else:
            label = "➕ Добавить фреш" if cat_id == "fresh_drinks" else "➕ Добавить"
            rows.append([InlineKeyboardButton(label, callback_data=f"add_{cat_id}_{iid}")])
    back = "nav_drinks" if cat_id in {"hot_drinks", "cold_drinks", "fresh_drinks"} else "home"
    rows.append([
        InlineKeyboardButton("🛒 Корзина", callback_data="cart_view"),
        InlineKeyboardButton("🔙 Назад", callback_data=back),
    ])
    return InlineKeyboardMarkup(rows)


def kb_lunch_hot(hot_items):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"{h['emoji']} {h['name']} — {fmt(h['price'])} сум",
            callback_data=f"lh_{h['id']}")]
        for h in hot_items
    ] + [[InlineKeyboardButton("🔙 В меню", callback_data="home")]])


def kb_lunch_garnishes(cfg):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🍚 {cfg['garnish1']}", callback_data="lg_1")],
        [InlineKeyboardButton(f"🌾 {cfg['garnish2']}", callback_data="lg_2")],
        [InlineKeyboardButton(f"🥔 {cfg['garnish3']}", callback_data="lg_3")],
        [InlineKeyboardButton("🔙 Назад", callback_data="lunch_hot_back")],
    ])


def kb_lunch_drinks():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🥤 Шербет", callback_data="ld_sherbet")],
        [InlineKeyboardButton("🧊 Айс-ти", callback_data="ld_iced_tea")],
        [InlineKeyboardButton("🔙 Назад к гарнирам", callback_data="lunch_drink_back")],
    ])


def kb_time():
    """Первый экран выбора выдачи: сейчас, отложить или скидка."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏃 Забрать сейчас", callback_data="tv_Сейчас (В очереди)")],
        [InlineKeyboardButton("🕒 Отложить", callback_data="postpone_time")],
        [InlineKeyboardButton("🔥 Скидка 20% (16:00–17:00)", callback_data="tv_discount")],
        [InlineKeyboardButton("🔙 Назад в корзину", callback_data="cart_view")],
    ])


def kb_postpone_time():
    """Экран отложенной выдачи: интервалы + своё время."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("11:00", callback_data="tv_11:00"),
         InlineKeyboardButton("12:00", callback_data="tv_12:00"),
         InlineKeyboardButton("13:00", callback_data="tv_13:00")],
        [InlineKeyboardButton("14:00", callback_data="tv_14:00"),
         InlineKeyboardButton("15:00", callback_data="tv_15:00"),
         InlineKeyboardButton("16:00", callback_data="tv_16:00")],
        [InlineKeyboardButton("✍️ Указать своё время", callback_data="time_custom")],
        [InlineKeyboardButton("🔙 Назад", callback_data="select_time")],
    ])


def kb_order_status(order_id, current_status):
    flow = ["paid", "cooking", "ready", "delivered"]
    if current_status not in flow:
        return None
    idx = flow.index(current_status)
    if idx >= len(flow) - 1:
        return None
    next_s = flow[idx + 1]
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"➡️ {ORDER_STATUSES[next_s]}", callback_data=f"setstatus_{order_id}_{next_s}")
    ]])


# ── Клавиатуры для редактирования меню недели ──
def kb_admin_week():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Пн", callback_data="adm_wday_mon"),
         InlineKeyboardButton("Вт", callback_data="adm_wday_tue"),
         InlineKeyboardButton("Ср", callback_data="adm_wday_wed")],
        [InlineKeyboardButton("Чт", callback_data="adm_wday_thu"),
         InlineKeyboardButton("Пт", callback_data="adm_wday_fri")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adm_back")],
    ])


def kb_admin_day(day_id, cfg, hot):
    rows = []
    for h in hot:
        rows.append([InlineKeyboardButton(
            f"✏️ {h['emoji']} {h['name']} — {fmt(h['price'])} сум",
            callback_data=f"adm_edithot_{h['id']}_{day_id}")])
    if cfg:
        rows.append([InlineKeyboardButton(
            f"✏️ 🥗 Салат: {cfg['salad']}",
            callback_data=f"adm_editsalad_{day_id}")])
        rows.append([InlineKeyboardButton(
            f"✏️ 🍚 Гарниры: {cfg['garnish1']} / {cfg['garnish2']} / {cfg['garnish3']}",
            callback_data=f"adm_editgarnish_{day_id}")])
    rows.append([InlineKeyboardButton("🔙 Назад к дням", callback_data="adm_week")])
    return InlineKeyboardMarkup(rows)

# ============================================================
# TELEGRAM RENDER
# ============================================================
async def send_or_edit(chat_id, msg_id, photo, caption, markup, context):
    # Безопасная обрезка caption до лимита Telegram для фото (1024 символа)
    if caption and len(caption) > 1020:
        cut = caption[:1017]
        if "<" in cut[900:]:
            cut = cut[:cut.rfind("<", 900)]
        caption = cut + "…"
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
                chat_id=chat_id, photo=photo, caption=caption,
                reply_markup=markup, parse_mode="HTML",
            )
        else:
            msg = await context.bot.send_message(
                chat_id=chat_id, text=caption, reply_markup=markup, parse_mode="HTML",
            )
        context.user_data["last_msg_id"] = msg.message_id
    except Exception:
        msg = await context.bot.send_message(
            chat_id=chat_id, text=caption, reply_markup=markup, parse_mode="HTML",
        )
        context.user_data["last_msg_id"] = msg.message_id


async def show_main(chat_id, context):
    await send_or_edit(
        chat_id, context.user_data.get("last_msg_id"), MAIN_BANNER,
        "<b>🏠 Главное меню</b>\n\n🍽 Выберите нужный раздел для заказа.",
        kb_main(), context,
    )

# ============================================================
# COMMANDS / CONTACT
# ============================================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ✅ ФИХ #3: init_db() убран отсюда — вызывается только в main()
    user_id = update.effective_user.id
    if not get_user(user_id):
        kb = ReplyKeyboardMarkup(
            [[KeyboardButton("📱 Поделиться номером", request_contact=True)]],
            resize_keyboard=True, one_time_keyboard=True,
        )
        await context.bot.send_message(
            chat_id=user_id,
            text="👋 <b>Добро пожаловать!</b>\n\nДля начала поделитесь номером телефона 👇",
            reply_markup=kb, parse_mode="HTML",
        )
        return
    await show_main(user_id, context)


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        add_user(update.effective_user.id, update.message.contact.phone_number)
        await update.message.reply_text("✅ Номер сохранён!", reply_markup=ReplyKeyboardRemove())
        await show_main(update.effective_user.id, context)


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"<b>Ваш Telegram ID:</b>\n<code>{update.effective_user.id}</code>",
        parse_mode="HTML",
    )


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет доступа.")
        return
    await _show_admin_panel(update.message.chat_id, context)


async def _show_admin_panel(chat_id, context):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton("🍽 Сводка для кухни", callback_data="adm_kitchen")],
        [InlineKeyboardButton("📋 Активные заказы", callback_data="adm_orders")],
        [InlineKeyboardButton("✏️ Меню на неделю", callback_data="adm_week")],
        [InlineKeyboardButton("📤 Посты в канал", callback_data="adm_posts")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast")],
        [InlineKeyboardButton("➕ Добавить блюдо", callback_data="adm_add"),
         InlineKeyboardButton("🗑 Удалить блюдо", callback_data="adm_del")],
        [InlineKeyboardButton("📥 Экспорт CSV", callback_data="adm_export")],
        [InlineKeyboardButton("⛔ Вкл/Выкл приём заказов", callback_data="adm_toggle")],
    ])
    await context.bot.send_message(
        chat_id=chat_id,
        text="👑 <b>Панель администратора</b>",
        reply_markup=kb, parse_mode="HTML",
    )



async def cmd_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    wd = local_now().weekday()
    if wd >= 5:
        await update.message.reply_text("Сегодня выходной, постов нет.")
        return
    ok = await _send_lunch_post(context.bot)
    if ok:
        await update.message.reply_text(f"✅ Пост «Обеды» опубликован в {CHANNEL_ID}.")
    else:
        await update.message.reply_text("❌ Ошибка публикации обедов.")


# ============================================================
# SHARED POST FUNCTIONS  (используются и из расписания, и из /admin)
# ============================================================
async def _send_lunch_post(bot) -> bool:
    """Публикует меню дня. Возвращает True при успехе."""
    wd = local_now().weekday()
    if wd >= 5:
        return False
    day_id, day_name = WEEKDAYS[wd]
    cfg, hot = get_lunch_config(day_id)
    lines = [f"<b>🍱 Комплексный обед — {day_name}</b>", ""]
    for h in hot:
        lines.append(f"{h['emoji']} <b>{h['name']}</b> — {fmt(h['price'])} сум")
    if cfg:
        lines += [
            "",
            f"🥗 Салат: {cfg['salad']}",
            "🥤 Напиток: Шербет или Айс-ти",
            f"🍚 Гарниры: {cfg['garnish1']} / {cfg['garnish2']} / {cfg['garnish3']}",
            "",
            "📍 Место выдачи: 4 этаж, кухня",
            "🕒 Заказ до 15:00 | Выдача: 11:00–16:00",
        ]
    bot_info = await bot.get_me()
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🍱 Заказать обед", url=f"https://t.me/{bot_info.username}")
    ]])
    try:
        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=MON_BANNER if wd == 0 else LUNCH_BANNER,
            caption="\n".join(lines),
            reply_markup=markup, parse_mode="HTML",
        )
        return True
    except Exception as e:
        logging.error(f"[POST LUNCH] Ошибка: {e}")
        return False


async def _send_fresh_post(bot) -> bool:
    """Публикует пост с фрешами. Возвращает True при успехе."""
    items = get_items("fresh_drinks")
    if not items:
        return False
    lines = ["<b>🍹 Свежевыжатые соки — только сегодня!</b>", ""]
    for i in items:
        lines.append(f"{i['name']} — <b>{fmt(i['price'])} сум</b>")
    lines += [
        "",
        "🌿 Всё свежевыжато прямо при вас!",
        "✅ Натуральные, без сахара и консервантов.",
        "",
        "📍 Место выдачи: 4 этаж, кухня",
    ]
    bot_info = await bot.get_me()
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🍹 Заказать фреш", url=f"https://t.me/{bot_info.username}")
    ]])
    try:
        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=FRESH_BANNER,
            caption="\n".join(lines),
            reply_markup=markup, parse_mode="HTML",
        )
        return True
    except Exception as e:
        logging.error(f"[POST FRESH] Ошибка: {e}")
        return False


async def _send_discount_post(bot) -> bool:
    """Публикует пост о скидке 16:00–17:00. Возвращает True при успехе."""
    wd = local_now().weekday()
    if wd >= 5:
        return False
    day_id, day_name = WEEKDAYS[wd]
    cfg, hot = get_lunch_config(day_id)
    lines = [
        "🔥 <b>СКИДКА 20% — только сейчас!</b>",
        "",
        f"С <b>16:00 до 17:00</b> — скидка <b>20%</b> на комплексные обеды ({day_name})!",
        "",
    ]
    for h in hot:
        original = h["price"]
        discounted = int(original * 0.8)
        lines.append(
            f"{h['emoji']} {h['name']}\n"
            f"   <s>{fmt(original)}</s> → <b>{fmt(discounted)} сум</b>"
        )
    lines += [
        "",
        "⏰ Успей заказать — акция длится <b>1 час</b>!",
        "📍 Место выдачи: 4 этаж, кухня",
    ]
    bot_info = await bot.get_me()
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔥 Заказать со скидкой", url=f"https://t.me/{bot_info.username}")
    ]])
    try:
        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=DISCOUNT_BANNER,
            caption="\n".join(lines),
            reply_markup=markup, parse_mode="HTML",
        )
        return True
    except Exception as e:
        logging.error(f"[POST DISCOUNT] Ошибка: {e}")
        return False


# ── Job-обёртки для планировщика ──
async def job_post_lunch(context):
    await _send_lunch_post(context.bot)
    logging.info("[SCHEDULER] Пост «Обеды» отправлен.")


async def job_post_fresh(context):
    await _send_fresh_post(context.bot)
    logging.info("[SCHEDULER] Пост «Фреши» отправлен.")


async def job_post_discount(context):
    await _send_discount_post(context.bot)
    logging.info("[SCHEDULER] Пост «Скидки» отправлен.")



# ============================================================
# TEXT / PHOTO HANDLERS
# ============================================================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text or ""
    state = context.user_data.get("state")

    if state == "CUSTOM_TIME":
        context.user_data["state"] = None
        await _show_payment(update.message, context, user_id, text, reply=True)
        return

    if user_id != ADMIN_ID:
        return

    if text.lower() == "отмена":
        context.user_data["state"] = None
        await update.message.reply_text("❌ Отменено.")
        return

    # ── Редактирование горячего блюда: "Название / 63000" ──
    if state == "EDIT_HOT":
        hot_id = context.user_data.get("editing_hot_id")
        day_id = context.user_data.get("editing_day_id")
        if "/" not in text:
            await update.message.reply_text(
                "⚠️ Формат: <b>Название блюда / Цена</b>\n"
                "Например: <code>Говядина тушёная / 65000</code>\n\n"
                "Для отмены напишите <b>отмена</b>",
                parse_mode="HTML",
            )
            return
        parts = text.split("/", 1)
        name = parts[0].strip()
        price_str = parts[1].strip().replace(" ", "")
        if not price_str.isdigit():
            await update.message.reply_text("⚠️ Цена должна быть числом. Попробуйте снова:")
            return
        update_lunch_hot_dish(hot_id, name, int(price_str))
        context.user_data["state"] = None
        cfg, hot = get_lunch_config(day_id)
        await update.message.reply_text(
            f"✅ Блюдо обновлено!\n\n<b>{name}</b> — {fmt(int(price_str))} сум",
            parse_mode="HTML",
            reply_markup=kb_admin_day(day_id, cfg, hot),
        )
        return

    # ── Редактирование салата ──
    if state == "EDIT_SALAD":
        day_id = context.user_data.get("editing_day_id")
        update_lunch_salad(day_id, text.strip())
        context.user_data["state"] = None
        cfg, hot = get_lunch_config(day_id)
        await update.message.reply_text(
            f"✅ Салат обновлён: <b>{text.strip()}</b>",
            parse_mode="HTML",
            reply_markup=kb_admin_day(day_id, cfg, hot),
        )
        return

    # ── Редактирование гарниров: "Рис, Пюре, Гречка" ──
    if state == "EDIT_GARNISHES":
        day_id = context.user_data.get("editing_day_id")
        parts = [p.strip() for p in text.split(",")]
        if len(parts) != 3:
            await update.message.reply_text(
                "⚠️ Нужно ровно <b>3 гарнира через запятую</b>.\n"
                "Например: <code>Рис, Пюре, Гречка</code>\n\n"
                "Для отмены напишите <b>отмена</b>",
                parse_mode="HTML",
            )
            return
        update_lunch_garnishes(day_id, parts[0], parts[1], parts[2])
        context.user_data["state"] = None
        cfg, hot = get_lunch_config(day_id)
        await update.message.reply_text(
            f"✅ Гарниры обновлены: <b>{' / '.join(parts)}</b>",
            parse_mode="HTML",
            reply_markup=kb_admin_day(day_id, cfg, hot),
        )
        return

    if state == "BROADCAST":
        await _do_broadcast(update, context)
        return
    if state == "DISH_NAME":
        context.user_data["new_dish"]["name"] = text
        context.user_data["state"] = "DISH_DESC"
        await update.message.reply_text("✏️ Введите описание:")
        return
    if state == "DISH_DESC":
        context.user_data["new_dish"]["desc"] = text
        context.user_data["state"] = "DISH_PRICE"
        await update.message.reply_text("💰 Введите цену (только цифры):")
        return
    if state == "DISH_PRICE":
        if not text.isdigit():
            await update.message.reply_text("⚠️ Только цифры!")
            return
        context.user_data["new_dish"]["price"] = int(text)
        context.user_data["state"] = "DISH_PHOTO"
        await update.message.reply_text("🖼 Отправьте ссылку на фото или само фото:")
        return
    if state == "DISH_PHOTO":
        context.user_data["new_dish"]["photo"] = text
        _save_dish(context)
        await update.message.reply_text("✅ Блюдо добавлено!")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    state = context.user_data.get("state")
    if state == "BROADCAST":
        await _do_broadcast(update, context)
    elif state == "DISH_PHOTO":
        context.user_data["new_dish"]["photo"] = update.message.photo[-1].file_id
        _save_dish(context)
        await update.message.reply_text("✅ Блюдо добавлено!")


def _save_dish(context):
    d = context.user_data.get("new_dish", {})
    add_dish(d.get("cat_id", ""), d.get("name", ""), d.get("desc", ""), d.get("price", 0), d.get("photo", ""))
    context.user_data["state"] = None


async def _do_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_user_ids()
    count = 0
    msg = await update.message.reply_text("⏳ Рассылка начата...")
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
# PAYMENT
# ============================================================
async def _show_payment(source, context, user_id, pickup_time, discount=False, reply=False):
    lines, lunch_total, other_total, _ = get_cart_summary(user_id)
    if not lines:
        return
    base = lunch_total + other_total
    if discount:
        disc_amt = int(lunch_total * 0.2)
        final = base - disc_amt
        time_str = f"{pickup_time} (скидка 20% на обеды: -{fmt(disc_amt)} сум)"
    else:
        final = base
        time_str = pickup_time
    context.user_data["pickup_time"] = time_str
    context.user_data["final_total"] = final
    click_url = (
        f"https://my.click.uz/services/pay/"
        f"?service_id={CLICK_SERVICE_ID}&merchant_id={CLICK_MERCHANT_ID}&amount={final}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Оплатить через Click", url=click_url)],
        [InlineKeyboardButton("✅ Я оплатил(а)", callback_data="paid")],
        [InlineKeyboardButton("🔙 Назад", callback_data="select_time")],
    ])
    caption = (
        f"<b>🧾 Счёт сформирован\n\n"
        f"Сумма к оплате: {fmt(final)} сум\n"
        f"Время выдачи: {time_str}\n\n"
        f"Нажмите кнопку для оплаты в приложении Click.</b>"
    )
    last_mid = context.user_data.get("last_msg_id")
    try:
        await context.bot.delete_message(chat_id=user_id, message_id=last_mid)
    except Exception:
        pass
    if reply:
        try:
            msg = await source.reply_photo(
                photo=CART_BANNER, caption=caption, reply_markup=kb, parse_mode="HTML"
            )
        except Exception:
            msg = await source.reply_text(text=caption, reply_markup=kb, parse_mode="HTML")
    else:
        try:
            if os.path.exists(QR_FILE_NAME):
                with open(QR_FILE_NAME, "rb") as f:
                    msg = await context.bot.send_photo(
                        chat_id=user_id, photo=f, caption=caption,
                        reply_markup=kb, parse_mode="HTML",
                    )
            else:
                msg = await context.bot.send_photo(
                    chat_id=user_id, photo=CART_BANNER, caption=caption,
                    reply_markup=kb, parse_mode="HTML",
                )
        except Exception:
            msg = await context.bot.send_message(
                chat_id=user_id, text=caption, reply_markup=kb, parse_mode="HTML"
            )
    context.user_data["last_msg_id"] = msg.message_id

# ============================================================
# MAIN CALLBACK HANDLER
# ============================================================
async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    data = q.data
    # ✅ ФИХ #3: init_db() убран отсюда
    last = context.user_data.get("last_msg_id", q.message.message_id)

    if data == "ignore":
        await q.answer()
        return

    # ──────────── ADMIN ────────────
    if data.startswith("adm_") or data.startswith("setstatus_"):
        if user_id != ADMIN_ID:
            await q.answer("⛔ Нет доступа.", show_alert=True)
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
                    "delivered": f"🎉 <b>Заказ #{order_id} выдан.</b>\nПриятного аппетита!",
                }
                if new_status in notif_map:
                    try:
                        await context.bot.send_message(
                            chat_id=order["user_id"], text=notif_map[new_status], parse_mode="HTML"
                        )
                    except Exception:
                        pass
            try:
                await q.message.edit_reply_markup(reply_markup=kb_order_status(order_id, new_status))
            except Exception:
                pass
            return

        await q.answer()

        # ── Назад в панель ──
        if data == "adm_back":
            await _show_admin_panel(user_id, context)
            return

        # ── Посты в канал — меню выбора ──
        if data == "adm_posts":
            await q.message.reply_text(
                "<b>📤 Посты в канал</b>\n\n"
                "Выберите пост для публикации прямо сейчас.\n\n"
                "🕒 Автоматически:\n"
                "• 10:00 → Фреши\n"
                "• 11:00 → Обеды\n"
                "• 16:00 → Скидки",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🍱 Пост: Обеды", callback_data="adm_postlunch")],
                    [InlineKeyboardButton("🍹 Пост: Фреши", callback_data="adm_postfresh")],
                    [InlineKeyboardButton("🔥 Пост: Скидка 20%", callback_data="adm_postdiscount")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="adm_back")],
                ]),
                parse_mode="HTML",
            )
            return

        if data == "adm_postlunch":
            ok = await _send_lunch_post(context.bot)
            await q.answer(
                "✅ Пост «Обеды» опубликован!" if ok else "❌ Ошибка или выходной день.",
                show_alert=True,
            )
            return

        if data == "adm_postfresh":
            ok = await _send_fresh_post(context.bot)
            await q.answer(
                "✅ Пост «Фреши» опубликован!" if ok else "❌ Ошибка публикации.",
                show_alert=True,
            )
            return

        if data == "adm_postdiscount":
            ok = await _send_discount_post(context.bot)
            await q.answer(
                "✅ Пост «Скидки» опубликован!" if ok else "❌ Ошибка или выходной день.",
                show_alert=True,
            )
            return

        # ── Меню на неделю — выбор дня ──
        if data == "adm_week":
            await q.message.reply_text(
                "<b>✏️ Меню на неделю</b>\n\nВыберите день для редактирования:",
                reply_markup=kb_admin_week(), parse_mode="HTML",
            )
            return

        # ── Выбор конкретного дня ──
        if data.startswith("adm_wday_"):
            day_id = data.split("_", 2)[2]
            cfg, hot = get_lunch_config(day_id)
            day_name = next((v[1] for v in WEEKDAYS.values() if v[0] == day_id), day_id)
            if not cfg or not hot:
                await q.message.reply_text("❌ Меню дня не найдено.")
                return
            await q.message.reply_text(
                f"<b>📅 {day_name}</b>\n\nНажмите на строку чтобы изменить:",
                reply_markup=kb_admin_day(day_id, cfg, hot), parse_mode="HTML",
            )
            return

        # ── Редактировать горячее блюдо ──
        if data.startswith("adm_edithot_"):
            parts = data.split("_")
            hot_id = int(parts[2])
            day_id = parts[3]
            cfg, hot = get_lunch_config(day_id)
            dish = next((h for h in hot if h["id"] == hot_id), None)
            if not dish:
                await q.message.reply_text("❌ Блюдо не найдено.")
                return
            context.user_data["state"] = "EDIT_HOT"
            context.user_data["editing_hot_id"] = hot_id
            context.user_data["editing_day_id"] = day_id
            await q.message.reply_text(
                f"<b>✏️ Редактирование блюда</b>\n\n"
                f"Текущее: <b>{dish['name']}</b> — {fmt(dish['price'])} сум\n\n"
                f"Отправьте в формате:\n<code>Название блюда / Цена</code>\n\n"
                f"Например: <code>Говядина тушёная / 65000</code>\n\n"
                f"Для отмены напишите <b>отмена</b>",
                parse_mode="HTML",
            )
            return

        # ── Редактировать салат ──
        if data.startswith("adm_editsalad_"):
            day_id = data.split("_", 2)[2]
            cfg, _ = get_lunch_config(day_id)
            context.user_data["state"] = "EDIT_SALAD"
            context.user_data["editing_day_id"] = day_id
            await q.message.reply_text(
                f"<b>✏️ Редактирование салата</b>\n\n"
                f"Текущий: <b>{cfg['salad']}</b>\n\n"
                f"Введите новое название салата:\n\n"
                f"Для отмены напишите <b>отмена</b>",
                parse_mode="HTML",
            )
            return

        # ── Редактировать гарниры ──
        if data.startswith("adm_editgarnish_"):
            day_id = data.split("_", 2)[2]
            cfg, _ = get_lunch_config(day_id)
            context.user_data["state"] = "EDIT_GARNISHES"
            context.user_data["editing_day_id"] = day_id
            await q.message.reply_text(
                f"<b>✏️ Редактирование гарниров</b>\n\n"
                f"Текущие: <b>{cfg['garnish1']} / {cfg['garnish2']} / {cfg['garnish3']}</b>\n\n"
                f"Введите 3 гарнира через запятую:\n"
                f"<code>Рис, Пюре, Гречка</code>\n\n"
                f"Для отмены напишите <b>отмена</b>",
                parse_mode="HTML",
            )
            return

        if data == "adm_stats":
            count, revenue = get_today_stats()
            await q.message.reply_text(
                f"<b>📊 Статистика</b>\n\n"
                f"👥 Пользователей: <b>{len(get_all_user_ids())}</b>\n"
                f"🛒 Заказов сегодня: <b>{count}</b>\n"
                f"💰 Выручка сегодня: <b>{fmt(revenue)} сум</b>\n"
                f"🔄 Активных заказов: <b>{len(get_active_orders())}</b>",
                parse_mode="HTML",
            )
        elif data == "adm_kitchen":
            summary = get_kitchen_summary()
            if not summary:
                await q.message.reply_text("<b>🍽 Сводка пуста.</b>", parse_mode="HTML")
                return
            grouped = {}
            for kind, name, qty in summary:
                grouped.setdefault(kind, []).append((name, qty))
            labels = {
                "hot": "🥩 Горячее", "garnish": "🍚 Гарниры", "salad": "🥗 Салаты",
                "drink": "🥤 Напитки", "fresh": "🍹 Фреши", "other": "📦 Прочее",
            }
            blocks = ["<b>🍽 Сводка для кухни</b>"]
            for kind in ["hot", "garnish", "salad", "drink", "fresh", "other"]:
                if kind in grouped:
                    blocks.append(f"\n<b>{labels[kind]}</b>")
                    blocks.extend([f"• {name} — <b>{qty} шт.</b>" for name, qty in grouped[kind]])
            await q.message.reply_text("\n".join(blocks), parse_mode="HTML")
        elif data == "adm_orders":
            orders = get_active_orders()
            if not orders:
                await q.message.reply_text("<b>📋 Активных заказов нет.</b>", parse_mode="HTML")
                return
            for o in orders[:15]:
                txt = (
                    f"<b>Заказ #{o['order_id']}</b> | {ORDER_STATUSES.get(o['status'], o['status'])}\n"
                    f"🕒 {o['pickup_time']}\n💰 {fmt(o['total'])} сум\n"
                    f"<i>{o['items'][:700]}</i>"
                )
                try:
                    await q.message.reply_text(
                        txt, reply_markup=kb_order_status(o["order_id"], o["status"]), parse_mode="HTML"
                    )
                except Exception:
                    pass
        elif data == "adm_broadcast":
            context.user_data["state"] = "BROADCAST"
            await q.message.reply_text(
                "<b>📢 Отправьте сообщение (текст или фото).\nДля отмены — 'отмена'.</b>",
                parse_mode="HTML",
            )
        elif data == "adm_add":
            cats = [c for c in get_all_categories() if c["id"] not in LUNCH_CAT_IDS]
            await q.message.reply_text(
                "<b>В какую категорию добавить?</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(c["name"], callback_data=f"adm_addcat_{c['id']}")] for c in cats
                ]),
                parse_mode="HTML",
            )
        elif data.startswith("adm_addcat_"):
            cat_id = data.split("_", 2)[2]
            context.user_data["state"] = "DISH_NAME"
            context.user_data["new_dish"] = {"cat_id": cat_id}
            await q.message.reply_text("<b>Введите название блюда:</b>", parse_mode="HTML")
        elif data == "adm_del":
            cats = [c for c in get_all_categories() if c["id"] not in LUNCH_CAT_IDS]
            await q.message.reply_text(
                "<b>Из какой категории удалить?</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(c["name"], callback_data=f"adm_delcat_{c['id']}")] for c in cats
                ]),
                parse_mode="HTML",
            )
        elif data.startswith("adm_delcat_"):
            cat_id = data.split("_", 2)[2]
            items = get_items(cat_id)
            if not items:
                await q.message.reply_text("<b>Категория пуста.</b>", parse_mode="HTML")
                return
            await q.message.reply_text(
                "<b>Выберите блюдо для удаления:</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(i["name"], callback_data=f"adm_delitem_{i['id']}")] for i in items
                ]),
                parse_mode="HTML",
            )
        elif data.startswith("adm_delitem_"):
            delete_dish(data.split("_")[2])
            await q.message.reply_text("<b>✅ Блюдо удалено.</b>", parse_mode="HTML")
        elif data == "adm_export":
            rows = get_all_orders_for_export()
            if not rows:
                await q.answer("Нет данных.", show_alert=True)
                return
            fname = f"report_{local_now().strftime('%Y%m%d_%H%M')}.csv"
            with open(fname, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["ID", "Дата", "Телефон", "Состав", "Сумма", "Статус", "Время выдачи", "Скидка"])
                for r in rows:
                    phone = str(r["phone"] or "")
                    if phone and not phone.startswith("+"):
                        phone = "+" + phone
                    w.writerow([
                        r["order_id"], r["created_at"], f'="{phone}"',
                        r["items"].replace("\n", " | "), r["total"],
                        ORDER_STATUSES.get(r["status"], r["status"]),
                        r["pickup_time"], r["discount_amount"],
                    ])
            with open(fname, "rb") as f:
                await context.bot.send_document(
                    chat_id=user_id, document=f,
                    caption="<b>📥 Отчёт готов.</b>", parse_mode="HTML",
                )
            try:
                os.remove(fname)
            except OSError:
                pass
        elif data == "adm_toggle":
            new_state = not menu_is_active()
            set_menu_active(new_state)
            status = "ОТКРЫТ ✅" if new_state else "ЗАКРЫТ ⛔"
            await q.answer(f"Приём заказов: {status}", show_alert=True)
        return

    # ──────────── NAVIGATION ────────────
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
        if not menu_is_active():
            await q.answer("⛔ Приём заказов закрыт.", show_alert=True)
            return
        wd = local_now().weekday()
        day_id = WEEKDAYS.get(wd, ("mon", "Понедельник"))[0]
        if wd >= 5:
            day_id = "mon"
            await q.answer("Выходной! Открываем понедельник для предзаказа 🤫", show_alert=True)
        else:
            await q.answer()
        reset_lunch_session(context)
        context.user_data["lunch"]["day_id"] = day_id
        cfg, hot = get_lunch_config(day_id)
        if not hot or not cfg:
            await q.message.reply_text("❌ Меню дня ещё не настроено.")
            return
        cat = get_category(day_id)
        caption = (
            f"<b>🍱 {cat['name']}</b>\n\nВыберите горячее блюдо:\n\n" +
            "\n".join([
                f"{h['emoji']} <b>{h['name']}</b> — {fmt(h['price'])} сум\n{h['description']}"
                for h in hot
            ])
        )
        await send_or_edit(user_id, last, cat["banner"], caption, kb_lunch_hot(hot), context)
        return

    if data.startswith("day_"):
        day_id = data.split("_", 1)[1]
        cfg, hot = get_lunch_config(day_id)
        if not cfg or not hot:
            await q.answer("Меню дня не настроено.", show_alert=True)
            return
        await q.answer()
        cat = get_category(day_id)
        caption = (
            f"<b>{cat['name']}</b>\n\n" +
            "\n".join([f"{h['emoji']} <b>{h['name']}</b> — {fmt(h['price'])} сум" for h in hot]) +
            f"\n\n🥗 Салат: {cfg['salad']}\n🥤 Напиток: Шербет или Айс-ти\n"
            f"🍚 Гарниры: {cfg['garnish1']} / {cfg['garnish2']} / {cfg['garnish3']}"
        )
        await send_or_edit(user_id, last, cat["banner"], caption,
                           InlineKeyboardMarkup([
                               [InlineKeyboardButton("🍱 Заказать этот обед", callback_data=f"start_day_{day_id}")],
                               [InlineKeyboardButton("🔙 Назад", callback_data="nav_week")],
                           ]), context)
        return

    if data.startswith("start_day_"):
        day_id = data.split("_", 2)[2]
        cfg, hot = get_lunch_config(day_id)
        if not cfg or not hot:
            await q.answer("Меню дня не настроено.", show_alert=True)
            return
        reset_lunch_session(context)
        context.user_data["lunch"]["day_id"] = day_id
        await q.answer()
        cat = get_category(day_id)
        caption = "<b>1️⃣ Выберите горячее блюдо</b>\n\n" + "\n".join(
            [f"{h['emoji']} {h['name']} — {fmt(h['price'])} сум" for h in hot]
        )
        await send_or_edit(user_id, last, cat["banner"], caption, kb_lunch_hot(hot), context)
        return

    # ──────────── LUNCH FLOW ────────────
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
        await q.answer()
        caption = (
            f"<b>2️⃣ Выберите гарнир</b>\n\n"
            f"🔥 {selected['name']}\n"
            f"Цена комплекса зависит от выбранного горячего блюда.\n\n"
            f"🍚 {cfg['garnish1']}\n🌾 {cfg['garnish2']}\n🥔 {cfg['garnish3']}"
        )
        await send_or_edit(user_id, last, LUNCH_BANNER, caption, kb_lunch_garnishes(cfg), context)
        return

    if data == "lunch_hot_back":
        session = lunch_session(context)
        cfg, hot = get_lunch_config(session.get("day_id") or current_day()[0])
        await q.answer()
        caption = "<b>1️⃣ Выберите горячее блюдо</b>\n\n" + "\n".join(
            [f"{h['emoji']} {h['name']} — {fmt(h['price'])} сум" for h in hot]
        )
        await send_or_edit(user_id, last, LUNCH_BANNER, caption, kb_lunch_hot(hot), context)
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
        session["drink_code"] = None
        session["drink_name"] = None
        await q.answer()
        caption = (
            f"<b>3️⃣ Выберите напиток к комплексу</b>\n\n"
            f"🔥 {session['hot_name']}\n"
            f"🍚 Гарнир: {garnish}\n"
            f"🥗 Салат: {cfg['salad']}\n\n"
            f"🥤 На выбор: Шербет или Айс-ти"
        )
        await send_or_edit(user_id, last, LUNCH_BANNER, caption, kb_lunch_drinks(), context)
        return

    if data == "lunch_drink_back":
        session = lunch_session(context)
        cfg = get_lunch_config(session.get("day_id") or current_day()[0])[0]
        await q.answer()
        caption = (
            f"<b>2️⃣ Выберите гарнир</b>\n\n"
            f"🔥 {session['hot_name']}\n\n"
            f"🍚 {cfg['garnish1']}\n🌾 {cfg['garnish2']}\n🥔 {cfg['garnish3']}"
        )
        await send_or_edit(user_id, last, LUNCH_BANNER, caption, kb_lunch_garnishes(cfg), context)
        return

    if data.startswith("ld_"):
        drink_code = data.split("_", 1)[1]
        drink_name = LUNCH_DRINKS.get(drink_code)
        if not drink_name:
            await q.answer("Такого напитка нет.", show_alert=True)
            return
        session = lunch_session(context)
        cfg, _ = get_lunch_config(session["day_id"])
        if not cfg or not session.get("garnish"):
            await q.answer("Сначала выберите гарнир.", show_alert=True)
            return
        session["drink_code"] = drink_code
        session["drink_name"] = drink_name
        combo_id = lunch_combo_item_id(session)
        combo_name = lunch_combo_name(cfg, session)
        update_cart(user_id, combo_id, combo_name, session["hot_price"], 1)
        context.user_data["lunch_components"] = [
            ("hot", session["hot_name"], 1, session["hot_price"]),
            ("garnish", session["garnish"], 1, 0),
            ("salad", cfg["salad"], 1, 0),
            ("drink", drink_name, 1, 0),
        ]
        await q.answer(f"✅ {drink_name}")
        await send_or_edit(
            user_id, last, CART_BANNER,
            f"<b>✅ Комплексный обед добавлен</b>\n\n{combo_name}\n\n💰 {fmt(session['hot_price'])} сум",
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
        if not cfg or not session.get("drink_code") or not session.get("garnish"):
            await q.answer("Сначала соберите комплекс.", show_alert=True)
            return
        combo_name = lunch_combo_name(cfg, session)
        await q.answer()
        await send_or_edit(
            user_id, last, CART_BANNER,
            f"<b>🍱 Комплекс готов</b>\n\n{combo_name}\n\n💰 {fmt(session['hot_price'])} сум",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Перейти в корзину", callback_data="cart_view")],
                [InlineKeyboardButton("🍹 Добавить ещё фреш", callback_data="cat_fresh_drinks")],
                [InlineKeyboardButton("🏠 В меню", callback_data="home")],
            ]),
            context,
        )
        return

    # ──────────── CATEGORIES / CART ────────────
    if data.startswith("cat_"):
        cat_id = data[4:]
        items = get_items(cat_id)
        cat = get_category(cat_id)
        if not items or not cat:
            await q.answer("Раздел пуст.", show_alert=True)
            return
        await q.answer()
        caption = f"<b>{cat['name']}</b>\n\n" + "\n\n".join(
            [f"▪️ <b>{i['name']}</b> — {fmt(i['price'])} сум\n<i>{i['description']}</i>" for i in items]
        )
        markup = kb_category(user_id, cat_id, items)
        session = lunch_session(context)
        if cat_id == "fresh_drinks" and session.get("drink_code") and session.get("garnish"):
            # ✅ ФИХ #2: list() — tuple не поддерживает append
            rows = list(markup.inline_keyboard[:-1])
            rows.append([
                InlineKeyboardButton("🛒 Корзина", callback_data="cart_view"),
                InlineKeyboardButton("🔙 К комплексу", callback_data="lunch_combo_done"),
            ])
            markup = InlineKeyboardMarkup(rows)
        await send_or_edit(user_id, last, cat["banner"], caption, markup, context)
        return

    if data.startswith("add_") or data.startswith("rm_"):
        action = "add" if data.startswith("add_") else "rm"
        parts = data.split("_")
        item_id = parts[-1]
        cat_id = "_".join(parts[1:-1])
        items = get_items(cat_id)
        # ✅ ФИХ #1: get_items() возвращает id как str — сравнение корректно
        item = next((i for i in items if i["id"] == item_id), None)
        if not item:
            await q.answer()
            return
        current = get_cart(user_id).get(item_id, {}).get("count", 0)
        new_cnt = current + (1 if action == "add" else -1)
        if new_cnt > 20:
            await q.answer("Максимум 20 одинаковых позиций.", show_alert=True)
            return
        update_cart(user_id, item_id, item["name"], item["price"], max(new_cnt, 0))
        await q.answer("➕ Добавлено" if action == "add" else "➖ Удалено")
        await context.bot.edit_message_reply_markup(
            chat_id=user_id, message_id=last,
            reply_markup=kb_category(user_id, cat_id, get_items(cat_id)),
        )
        return

    if data == "cart_view":
        await q.answer()
        lines, lunch, other, _ = get_cart_summary(user_id)
        if not lines:
            await send_or_edit(user_id, last, CART_BANNER, "<b>🛒 Корзина пуста!</b>", kb_main(), context)
            return
        total = lunch + other
        await send_or_edit(
            user_id, last, CART_BANNER,
            f"<b>🛒 Ваш заказ:</b>\n\n{lines}\n\n<b>Итого: {fmt(total)} сум</b>\n\nПерейти к оформлению?",
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
        await q.answer()
        await send_or_edit(
            user_id, last, CART_BANNER,
            "<b>🕒 Выберите время выдачи заказа:</b>\n\nВыдача: 10:00–16:00.",
            kb_time(), context,
        )
        return

    if data == "postpone_time":
        await q.answer()
        await send_or_edit(
            user_id, last, CART_BANNER,
            "<b>🕒 Отложить заказ</b>\n\nВыберите удобное время выдачи или укажите своё:",
            kb_postpone_time(), context,
        )
        return

    if data == "time_custom":
        await q.answer()
        context.user_data["state"] = "CUSTOM_TIME"
        await send_or_edit(
            user_id, last, CART_BANNER,
            "<b>✍️ Укажите своё время</b>\n\nНапишите время выдачи в формате <b>ЧЧ:ММ</b>, например <b>14:45</b>.",
            InlineKeyboardMarkup([[InlineKeyboardButton("❌ Назад", callback_data="postpone_time")]]),
            context,
        )
        return

    if data.startswith("tv_"):
        time_val = data[3:]
        if time_val == "discount":
            hour = local_now().hour
            if hour != 16:
                await q.answer("⚠️ Скидка 20% действует только с 16:00 до 17:00!", show_alert=True)
                return
            _, lunch, _, _ = get_cart_summary(user_id)
            if lunch == 0:
                await q.answer("⚠️ Скидка только на обеды! В корзине их нет.", show_alert=True)
                return
            await q.answer()
            await _show_payment(None, context, user_id, "16:00–17:00", discount=True)
        else:
            await q.answer()
            await _show_payment(None, context, user_id, time_val)
        return

    if data == "paid":
        await q.answer()
        lines, lunch, other, items_str = get_cart_summary(user_id)
        if not lines:
            return
        final = context.user_data.get("final_total", lunch + other)
        pickup_time = context.user_data.get("pickup_time", "Не указано")
        discount_amount = max(0, (lunch + other) - final)

        components = []
        cart_snapshot = get_cart(user_id)

        # Определяем id фрешей по категории из menu_items
        conn = _conn()
        fresh_ids = {
            str(r["id"]) for r in conn.execute(
                "SELECT id FROM menu_items WHERE cat_id='fresh_drinks'"
            ).fetchall()
        }
        conn.close()
        fresh_names = {
            item["name"] for item_id, item in cart_snapshot.items() if str(item_id) in fresh_ids
        }

        for item_id, item in cart_snapshot.items():
            if str(item_id).startswith("lunch_"):
                parts = str(item_id).split("_")
                if len(parts) == 5 and parts[3].startswith("g"):
                    day_id = parts[1]
                    try:
                        hot_id = int(parts[2])
                        garnish_index = int(parts[3][1:])
                    except ValueError:
                        hot_id = None
                        garnish_index = None
                    drink_code = parts[4]
                    drink_name = LUNCH_DRINKS.get(drink_code)
                    cfg, hot_items = get_lunch_config(day_id)
                    hot = next((h for h in hot_items if h["id"] == hot_id), None)
                    garnish = get_garnish_by_index(cfg, garnish_index) if cfg and garnish_index else None
                    if cfg and hot and garnish and drink_name:
                        qty = item["count"]
                        components.extend([
                            ("hot", hot["name"], qty, hot["price"]),
                            ("garnish", garnish, qty, 0),
                            ("salad", cfg["salad"], qty, 0),
                            ("drink", drink_name, qty, 0),
                        ])
            else:
                components.append(("other", item["name"], item["count"], item["price"]))

        # Переклассифицируем фреши из "other" → "fresh"
        components = [
            (
                "fresh" if item_name in fresh_names and item_type == "other" else item_type,
                item_name, qty, unit_price,
            )
            for item_type, item_name, qty, unit_price in components
        ]

        order_id = create_order(
            user_id, items_str, final, pickup_time,
            discount_amount=discount_amount, components=components,
        )
        clear_cart(user_id)
        reset_lunch_session(context)
        context.user_data["lunch_components"] = []

        name = q.from_user.first_name + (f" {q.from_user.last_name}" if q.from_user.last_name else "")
        username = f" (@{q.from_user.username})" if q.from_user.username else ""
        text = (
            f"<b>✅ Заказ #{order_id} принят!</b>\n\n{lines}\n\n"
            f"📍 Место выдачи: 4 этаж, кухня\n"
            f"🕒 Время: {pickup_time}\n\n"
            f"Мы уведомим вас, когда заказ будет готов!"
        )
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=last)
        except Exception:
            pass
        msg = await context.bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
        context.user_data["last_msg_id"] = msg.message_id

        if ADMIN_ID:
            user_row = get_user(user_id)
            phone = user_row["phone"] if user_row else "нет"
            adm_txt = (
                f"🚨 <b>Новый заказ #{order_id}!</b>\n"
                f"👤 {name}{username}\n📞 {phone}\n"
                f"🕒 {pickup_time}\n💰 {fmt(final)} сум\n\n"
                f"<b>Состав:</b>\n{lines}"
            )
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID, text=adm_txt,
                    reply_markup=kb_order_status(order_id, "paid"), parse_mode="HTML",
                )
            except Exception:
                pass
        return

    await q.answer()

# ============================================================
# SETUP / SERVER
# ============================================================
async def post_init(application: Application):
    # Команды для всех пользователей
    await application.bot.set_my_commands([
        BotCommand("start", "Главное меню"),
        BotCommand("myid", "Узнать свой Telegram ID"),
    ], scope=BotCommandScopeDefault())

    # /admin и /post — только у администратора в меню
    if ADMIN_ID:
        try:
            await application.bot.set_my_commands([
                BotCommand("start", "Главное меню"),
                BotCommand("admin", "👑 Панель администратора"),
                BotCommand("post", "📢 Опубликовать пост в канал"),
                BotCommand("myid", "Узнать свой Telegram ID"),
            ], scope=BotCommandScopeChat(chat_id=ADMIN_ID))
        except Exception as e:
            logging.warning(f"Не удалось установить команды для админа: {e}")

    # ── Автоматические посты по расписанию (UTC, Пн–Пт) ──
    # TZ_OFFSET = 5, поэтому: UTC = UZT_time - 5h
    # 10:00 UZT = 05:00 UTC → Фреши
    # 11:00 UZT = 06:00 UTC → Обеды
    # 16:00 UZT = 11:00 UTC → Скидки
    jq = application.job_queue
    if jq:
        jq.run_daily(
            job_post_fresh,
            time=t_time(5, 0),        # 10:00 Ташкент
            days=(0, 1, 2, 3, 4),     # Пн–Пт
            name="auto_post_fresh",
        )
        jq.run_daily(
            job_post_lunch,
            time=t_time(6, 0),        # 11:00 Ташкент
            days=(0, 1, 2, 3, 4),     # Пн–Пт
            name="auto_post_lunch",
        )
        jq.run_daily(
            job_post_discount,
            time=t_time(11, 0),       # 16:00 Ташкент
            days=(0, 1, 2, 3, 4),     # Пн–Пт
            name="auto_post_discount",
        )
        logging.info("[SCHEDULER] Авторасписание постов зарегистрировано.")
    else:
        logging.warning("[SCHEDULER] JobQueue недоступна — автопосты не запланированы.")



async def health(request):
    return web.Response(text="OK")


async def main():
    # ✅ ФИХ #3: init_db() только здесь — один раз при запуске
    init_db()
    if not TOKEN or TOKEN == "ВАШ_ТОКЕН":
        logging.warning("BOT_TOKEN не установлен.")

    app_bot = Application.builder().token(TOKEN).post_init(post_init).build()
    app_bot.add_handler(CommandHandler("start", cmd_start))
    app_bot.add_handler(CommandHandler("admin", cmd_admin))
    app_bot.add_handler(CommandHandler("post", cmd_post))
    app_bot.add_handler(CommandHandler("myid", cmd_myid))
    app_bot.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app_bot.add_handler(CallbackQueryHandler(btn))

    web_app = web.Application()
    web_app.router.add_get("/", health)
    runner = web.AppRunner(web_app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080))).start()

    await app_bot.initialize()
    await app_bot.start()
    if app_bot.job_queue:
        await app_bot.job_queue.start()
    await app_bot.updater.start_polling()
    logging.info(">>> Бот запущен <<<")

    while True:
        await asyncio.sleep(3600)



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
