import os
import logging
import asyncio
import sqlite3
import csv
from datetime import datetime
from collections import Counter
from aiohttp import web
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand,
    InputMediaPhoto, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN      = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН")
ADMIN_ID   = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel")
TZ_OFFSET  = int(os.getenv("TZ_OFFSET", "5"))

CLICK_SERVICE_ID  = os.getenv("CLICK_SERVICE_ID", "52528")
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "20421")
QR_FILE_NAME      = "qr.jpg"

DB_NAME     = "click_lunch_v5.db"
menu_active = True

MAIN_BANNER  = "https://images.unsplash.com/photo-1498837167922-41cfa6f318ba?q=80&w=1200&auto=format&fit=crop"
CART_BANNER  = "https://images.unsplash.com/photo-1556742044-3c52d6e88c62?q=80&w=1200&auto=format&fit=crop"
LUNCH_BANNER = "https://images.unsplash.com/photo-1543339308-43e59d6b73a6?q=80&w=1200&auto=format&fit=crop"
MON_BANNER   = "https://images.unsplash.com/photo-1548943487-a2e4f43b4850?q=80&w=1200&auto=format&fit=crop"

DEFAULT_CATEGORIES = [
    ('breakfasts',  'Завтраки',        'https://images.unsplash.com/photo-1533089860892-a7c6f0a88666?q=80&w=1200&auto=format&fit=crop'),
    ('hot_drinks',  'Горячие напитки', 'https://images.unsplash.com/photo-1497935586351-b67a49e012bf?q=80&w=1200&auto=format&fit=crop'),
    ('cold_drinks', 'Холодные напитки','https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?q=80&w=1200&auto=format&fit=crop'),
    ('fresh_drinks','Фреши',           'https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?q=80&w=1200&auto=format&fit=crop'),
    ('mon', 'Понедельник', MON_BANNER),
    ('tue', 'Вторник',     LUNCH_BANNER),
    ('wed', 'Среда',       LUNCH_BANNER),
    ('thu', 'Четверг',     LUNCH_BANNER),
    ('fri', 'Пятница',     LUNCH_BANNER),
]

DEFAULT_ITEMS = [
    # Завтраки
    ('breakfasts', 'Яичница с сосисками', 'Классический сытный завтрак из яиц и сосисок.', 40000, ''),
    ('breakfasts', 'Омлет',               'Пышный свежеприготовленный омлет.',              35000, ''),
    ('breakfasts', 'Гренки 4 шт',         'Золотистые поджаренные гренки.',                 20000, ''),
    ('breakfasts', 'Овсяная каша',        'Вкусная и полезная каша.',                       25000, ''),
    ('breakfasts', 'Сэндвич с говядиной', 'Сытный сэндвич с говядиной и расплавленным сыром.', 32000, ''),
    # Горячие напитки
    ('hot_drinks', '☕ Американо',   'Классический чёрный кофе (двойная порция эспрессо + вода).',        15000, ''),
    ('hot_drinks', '☕🥛 Капучино',  'Эспрессо с молоком и плотной молочной пенкой (150 мл молока).',    24000, ''),
    ('hot_drinks', '☕🥛 Латте',     'Мягкий кофейный напиток с большим количеством молока (200 мл).',    27000, ''),
    ('hot_drinks', '☕✨ Флэт Уайт', 'Насыщенный эспрессо с бархатистой молочной микропенкой (160 мл).', 24500, ''),
    # Холодные напитки
    ('cold_drinks', '🥤 Кола 0.25 / Zero', 'Освежающая газировка.',          13000, ''),
    ('cold_drinks', '🍊 Fanta 0.25',        'Апельсиновая газировка.',        12000, ''),
    ('cold_drinks', '🍹 Мохито',            'Охлаждающий напиток.',           20000, ''),
    ('cold_drinks', '💧 Chortoq (с газом)', 'Минеральная газированная вода.', 12000, ''),
    # Фреши
    ('fresh_drinks', '🍎 Яблочный фреш',     'Свежевыжатый яблочный сок (250 мл).',         27000, ''),
    ('fresh_drinks', '🥕 Морковный фреш',     'Свежевыжатый морковный сок (250 мл).',        16000, ''),
    ('fresh_drinks', '❤️ Свекольный фреш',    'Свежевыжатый свекольный сок (250 мл).',       16000, ''),
    ('fresh_drinks', '🍎🥕 Яблоко + Морковь', 'Микс яблочного и морковного сока (250 мл).',  19000, ''),
    ('fresh_drinks', '🍎❤️ Яблоко + Свёкла',  'Микс яблочного и свекольного сока (250 мл).', 19000, ''),
    ('fresh_drinks', '🥒🍎 Огурец + Яблоко',  'Освежающий микс огурца и яблока (250 мл).',   26000, ''),
    # Понедельник
    ('mon', '🥩 Говядина с овощами + Салат + Шербет',
     'Говядина с овощами (рис/гречка), салат Витаминный, шербет.', 63000, ''),
    ('mon', '🍗 Куриный казан-кебаб + Салат + Шербет',
     'Куриный казан-кебаб, салат Витаминный, шербет.', 58000, ''),
    # Вторник
    ('tue', '🥩 Жаркое из говядины + Салат + Айс-ти',
     'Жаркое из говядины с картофелем, салат Французский, айс-ти.', 63000, ''),
    ('tue', '🍗 Куриные котлеты + Салат + Айс-ти',
     'Куриные котлеты (перловка/пюре), салат Французский, айс-ти.', 58000, ''),
    # Среда
    ('wed', '🥩 Бефстроганов + Салат + Шербет',
     'Бефстроганов (рис/гречка/картофель по домашнему), салат Овощной, шербет.', 63000, ''),
    ('wed', '🍗 Куриная отбивная с сыром + Салат + Шербет',
     'Куриная отбивная с сыром (рис/гречка/картофель по домашнему), салат Овощной, шербет.', 58000, ''),
    # Четверг
    ('thu', '🥩 Плов из говядины + Ачик-чучук + Айс-ти',
     'Плов из говядины, салат Ачик-чучук и соленья, айс-ти.', 63000, ''),
    ('thu', '🍗 Куриный Ган-пан + Ачик-чучук + Айс-ти',
     'Куриный Ган-пан (рис/пюре), салат Ачик-чучук или соленья, айс-ти.', 58000, ''),
    # Пятница
    ('fri', '🥩 Гуляш из говядины + Салат + Шербет',
     'Гуляш из говядины (рис/пюре/овощи печёные), салат Греческий, шербет.', 63000, ''),
    ('fri', '🍗 Курица в соусе карри + Салат + Шербет',
     'Курица в соусе карри (рис/пюре/овощи печёные), салат Греческий, шербет.', 58000, ''),
]

LUNCH_CAT_IDS = {'mon', 'tue', 'wed', 'thu', 'fri'}

ORDER_STATUSES = {
    'paid':      '💳 Оплачен',
    'cooking':   '👨‍🍳 Готовится',
    'ready':     '✅ Готов к выдаче',
    'delivered': '🎉 Выдан',
}

def _conn():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = _conn(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, phone TEXT, orders_count INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS cart (
        user_id INTEGER, item_id TEXT, item_name TEXT, price INTEGER, count INTEGER,
        PRIMARY KEY (user_id, item_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, items TEXT, total INTEGER,
        status TEXT DEFAULT 'paid', pickup_time TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS menu_categories (
        id TEXT PRIMARY KEY, name TEXT, banner TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS menu_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cat_id TEXT, name TEXT, description TEXT, price INTEGER, image TEXT)''')
    conn.commit(); conn.close()
    _seed_menu()

def _seed_menu():
    conn = _conn(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM menu_categories")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO menu_categories VALUES (?,?,?)", DEFAULT_CATEGORIES)
        c.executemany("INSERT INTO menu_items (cat_id,name,description,price,image) VALUES (?,?,?,?,?)", DEFAULT_ITEMS)
    conn.commit(); conn.close()

def get_user(user_id):
    conn = _conn(); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone(); conn.close(); return row

def add_user(user_id, phone):
    conn = _conn(); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id,phone) VALUES (?,?)", (user_id, phone))
    conn.commit(); conn.close()

def get_all_user_ids():
    conn = _conn(); c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    ids = [r[0] for r in c.fetchall()]; conn.close(); return ids

def get_all_categories():
    conn = _conn(); c = conn.cursor()
    c.execute("SELECT id, name FROM menu_categories")
    cats = [{"id": r[0], "name": r[1]} for r in c.fetchall()]; conn.close(); return cats

def get_category(cat_id):
    conn = _conn(); c = conn.cursor()
    c.execute("SELECT id, name, banner FROM menu_categories WHERE id=?", (cat_id,))
    row = c.fetchone(); conn.close()
    return {"id": row[0], "name": row[1], "banner": row[2]} if row else None

def get_items(cat_id):
    conn = _conn(); c = conn.cursor()
    c.execute("SELECT id, name, description, price, image FROM menu_items WHERE cat_id=?", (cat_id,))
    items = [{"id": str(r[0]), "name": r[1], "description": r[2], "price": r[3], "image": r[4]}
             for r in c.fetchall()]; conn.close(); return items

def add_dish(cat_id, name, desc, price, photo):
    conn = _conn(); c = conn.cursor()
    c.execute("INSERT INTO menu_items (cat_id,name,description,price,image) VALUES (?,?,?,?,?)",
              (cat_id, name, desc, price, photo))
    conn.commit(); conn.close()

def delete_dish(item_id):
    conn = _conn(); c = conn.cursor()
    c.execute("DELETE FROM menu_items WHERE id=?", (item_id,))
    c.execute("DELETE FROM cart WHERE item_id=?", (item_id,))
    conn.commit(); conn.close()

def get_cart(user_id):
    conn = _conn(); c = conn.cursor()
    c.execute("SELECT item_id, item_name, price, count FROM cart WHERE user_id=?", (user_id,))
    cart = {r[0]: {"name": r[1], "price": r[2], "count": r[3]} for r in c.fetchall()}
    conn.close(); return cart

def update_cart(user_id, item_id, item_name, price, count):
    conn = _conn(); c = conn.cursor()
    if count == 0:
        c.execute("DELETE FROM cart WHERE user_id=? AND item_id=?", (user_id, item_id))
    else:
        c.execute("INSERT OR REPLACE INTO cart VALUES (?,?,?,?,?)",
                  (user_id, item_id, item_name, price, count))
    conn.commit(); conn.close()

def clear_cart(user_id):
    conn = _conn(); c = conn.cursor()
    c.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit(); conn.close()

def get_cart_summary(user_id):
    conn = _conn(); c = conn.cursor()
    c.execute("SELECT item_id, item_name, price, count FROM cart WHERE user_id=?", (user_id,))
    rows = c.fetchall()
    c.execute("SELECT id, cat_id FROM menu_items")
    cat_map = {str(r[0]): r[1] for r in c.fetchall()}
    conn.close()
    if not rows:
        return None, 0, 0, ""
    lines, short, lunch_total, other_total = [], [], 0, 0
    for item_id, name, price, cnt in rows:
        subtotal = price * cnt
        lines.append(f"• <b>{name}</b> x{cnt} — <b>{subtotal:,} сум</b>".replace(",", " "))
        short.append(f"{name} x{cnt}")
        if cat_map.get(item_id) in LUNCH_CAT_IDS:
            lunch_total += subtotal
        else:
            other_total += subtotal
    return "\n".join(lines), lunch_total, other_total, ", ".join(short)

def create_order(user_id, items_str, total, pickup_time):
    conn = _conn(); c = conn.cursor()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO orders (user_id,items,total,status,pickup_time,created_at) VALUES (?,?,?,?,?,?)",
              (user_id, items_str, total, 'paid', pickup_time, now))
    order_id = c.lastrowid
    c.execute("UPDATE users SET orders_count = orders_count + 1 WHERE user_id=?", (user_id,))
    conn.commit(); conn.close()
    return order_id

def set_order_status(order_id, status):
    conn = _conn(); c = conn.cursor()
    c.execute("UPDATE orders SET status=? WHERE order_id=?", (status, order_id))
    conn.commit(); conn.close()

def get_active_orders():
    conn = _conn(); c = conn.cursor()
    c.execute("SELECT order_id, user_id, items, total, status, pickup_time FROM orders WHERE status != 'delivered' ORDER BY order_id")
    rows = c.fetchall(); conn.close()
    return [{"order_id": r[0], "user_id": r[1], "items": r[2], "total": r[3],
             "status": r[4], "pickup_time": r[5]} for r in rows]

def get_kitchen_summary():
    conn = _conn(); c = conn.cursor()
    c.execute("SELECT items FROM orders WHERE status IN ('paid','cooking')")
    rows = c.fetchall(); conn.close()
    counter = Counter()
    for (items_str,) in rows:
        for part in items_str.split(", "):
            if " x" in part:
                name, qty_str = part.rsplit(" x", 1)
                try: counter[name.strip()] += int(qty_str.strip())
                except: counter[part.strip()] += 1
            else:
                counter[part.strip()] += 1
    return counter

def get_all_orders_for_export():
    conn = _conn(); c = conn.cursor()
    c.execute("""SELECT o.order_id, o.created_at, u.phone, o.items, o.total, o.status, o.pickup_time
                 FROM orders o LEFT JOIN users u ON o.user_id = u.user_id ORDER BY o.order_id DESC""")
    rows = c.fetchall(); conn.close(); return rows

def get_today_stats():
    tz_delta = TZ_OFFSET * 3600
    today = datetime.utcfromtimestamp(datetime.utcnow().timestamp() + tz_delta).strftime("%Y-%m-%d")
    conn = _conn(); c = conn.cursor()
    c.execute("SELECT COUNT(*), COALESCE(SUM(total),0) FROM orders WHERE created_at LIKE ?", (f"{today}%",))
    row = c.fetchone(); conn.close()
    return row[0], row[1]

def local_now():
    ts = datetime.utcnow().timestamp() + TZ_OFFSET * 3600
    return datetime.utcfromtimestamp(ts)

def fmt(amount):
    return f"{amount:,}".replace(",", " ")

def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🍱 Комплексный обед (Сегодня)", callback_data="lunch_today")],
        [InlineKeyboardButton("🍳 Завтраки",       callback_data="cat_breakfasts"),
         InlineKeyboardButton("🥤 Напитки",        callback_data="nav_drinks")],
        [InlineKeyboardButton("🗓 Меню на неделю", callback_data="nav_week")],
        [InlineKeyboardButton("🛒 Корзина",        callback_data="cart_view")],
    ])

def kb_drinks():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("☕ Горячие напитки",  callback_data="cat_hot_drinks")],
        [InlineKeyboardButton("🧊 Холодные напитки", callback_data="cat_cold_drinks")],
        [InlineKeyboardButton("🍹 Фреши",            callback_data="cat_fresh_drinks")],
        [InlineKeyboardButton("🔙 Назад",            callback_data="home")],
    ])

def kb_week():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Пн", callback_data="cat_mon"),
         InlineKeyboardButton("Вт", callback_data="cat_tue"),
         InlineKeyboardButton("Ср", callback_data="cat_wed")],
        [InlineKeyboardButton("Чт", callback_data="cat_thu"),
         InlineKeyboardButton("Пт", callback_data="cat_fri")],
        [InlineKeyboardButton("🔙 Назад", callback_data="home")],
    ])

def kb_category(user_id, cat_id, items):
    cart = get_cart(user_id)
    rows = []
    for item in items:
        iid = str(item['id'])
        cnt = cart.get(iid, {}).get('count', 0)
        rows.append([InlineKeyboardButton(
            f"🍽 {item['name']} — {fmt(item['price'])} сум", callback_data="ignore")])
        if cnt > 0:
            rows.append([
                InlineKeyboardButton("➖", callback_data=f"rm_{cat_id}_{iid}"),
                InlineKeyboardButton(f"{cnt} шт", callback_data="ignore"),
                InlineKeyboardButton("➕", callback_data=f"add_{cat_id}_{iid}"),
            ])
        else:
            rows.append([InlineKeyboardButton("➕ Добавить", callback_data=f"add_{cat_id}_{iid}")])
    back = "nav_drinks" if cat_id in {'hot_drinks','cold_drinks','fresh_drinks'} else \
           ("nav_week" if cat_id in LUNCH_CAT_IDS else "home")
    rows.append([InlineKeyboardButton("🛒 Корзина", callback_data="cart_view"),
                 InlineKeyboardButton("🔙 Назад",   callback_data=back)])
    return InlineKeyboardMarkup(rows)

def kb_time():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏃 Забрать сейчас",           callback_data="tv_Сейчас (В очереди)")],
        [InlineKeyboardButton("11:00", callback_data="tv_11:00"),
         InlineKeyboardButton("12:00", callback_data="tv_12:00"),
         InlineKeyboardButton("13:00", callback_data="tv_13:00")],
        [InlineKeyboardButton("14:00", callback_data="tv_14:00"),
         InlineKeyboardButton("15:00", callback_data="tv_15:00"),
         InlineKeyboardButton("16:00", callback_data="tv_16:00")],
        [InlineKeyboardButton("🔥 Скидка 20% (16:00-17:00)", callback_data="tv_discount")],
        [InlineKeyboardButton("✍️ Своё время",               callback_data="time_custom")],
        [InlineKeyboardButton("🔙 Назад в корзину",          callback_data="cart_view")],
    ])

def kb_order_status(order_id, current_status):
    flow = ['paid', 'cooking', 'ready', 'delivered']
    idx = flow.index(current_status) if current_status in flow else -1
    if idx >= 0 and idx < len(flow) - 1:
        next_s = flow[idx + 1]
        return InlineKeyboardMarkup([[InlineKeyboardButton(
            f"➡️ {ORDER_STATUSES[next_s]}",
            callback_data=f"setstatus_{order_id}_{next_s}")]])
    return None

async def send_or_edit(chat_id, msg_id, photo, caption, markup, context):
    try:
        media = InputMediaPhoto(media=photo, caption=caption, parse_mode='HTML')
        await context.bot.edit_message_media(chat_id=chat_id, message_id=msg_id,
                                              media=media, reply_markup=markup)
    except Exception:
        try: await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except: pass
        try:
            msg = await context.bot.send_photo(chat_id=chat_id, photo=photo,
                                                caption=caption, reply_markup=markup, parse_mode='HTML')
        except Exception:
            msg = await context.bot.send_message(chat_id=chat_id, text=caption,
                                                  reply_markup=markup, parse_mode='HTML')
        context.user_data['last_msg_id'] = msg.message_id

async def show_main(chat_id, context):
    try: await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data.get('last_msg_id'))
    except: pass
    caption = "<b>🏠 Главное меню</b>\n\n🍽 Выберите нужный раздел для заказа."
    try:
        msg = await context.bot.send_photo(chat_id=chat_id, photo=MAIN_BANNER,
                                            caption=caption, reply_markup=kb_main(), parse_mode='HTML')
    except Exception:
        msg = await context.bot.send_message(chat_id=chat_id, text=caption,
                                              reply_markup=kb_main(), parse_mode='HTML')
    context.user_data['last_msg_id'] = msg.message_id

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_db()
    if not get_user(user_id):
        kb = ReplyKeyboardMarkup([[KeyboardButton("📱 Поделиться номером", request_contact=True)]],
                                  resize_keyboard=True, one_time_keyboard=True)
        await context.bot.send_message(chat_id=user_id,
            text="👋 <b>Добро пожаловать в Click Обеды!</b>\n\nДля начала поделитесь номером телефона 👇",
            reply_markup=kb, parse_mode='HTML')
    else:
        await show_main(user_id, context)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.contact:
        add_user(user_id, update.message.contact.phone_number)
        await update.message.reply_text("✅ Номер сохранён!", reply_markup=ReplyKeyboardRemove())
        await show_main(user_id, context)

async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(f"<b>Ваш Telegram ID:</b>\n<code>{uid}</code>", parse_mode='HTML')

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет доступа."); return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика",              callback_data="adm_stats")],
        [InlineKeyboardButton("🍽 Сводка для кухни",       callback_data="adm_kitchen")],
        [InlineKeyboardButton("📋 Активные заказы",        callback_data="adm_orders")],
        [InlineKeyboardButton("📢 Рассылка",               callback_data="adm_broadcast")],
        [InlineKeyboardButton("➕ Добавить блюдо",         callback_data="adm_add"),
         InlineKeyboardButton("🗑 Удалить блюдо",         callback_data="adm_del")],
        [InlineKeyboardButton("📥 Экспорт в CSV",          callback_data="adm_export")],
        [InlineKeyboardButton("⛔ Вкл/Выкл приём заказов", callback_data="adm_toggle")],
    ])
    await update.message.reply_text("👑 <b>Панель администратора</b>", reply_markup=kb, parse_mode='HTML')

async def cmd_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID: return
    weekday = local_now().weekday()
    posts = {
        0: (
            f"<b>🌟 Понедельник — вкусное начало недели!\n\n"
            f"• 🥩 Говядина с овощами (рис/гречка) + Витаминный салат + Шербет — {fmt(63000)} сум\n"
            f"• 🍗 Куриный казан-кебаб + Витаминный салат + Шербет — {fmt(58000)} сум</b>",
            MON_BANNER
        ),
        1: (
            f"<b>😋 Вторник — время обеда!\n\n"
            f"• 🥩 Жаркое из говядины с картофелем + Французский салат + Айс-ти — {fmt(63000)} сум\n"
            f"• 🍗 Куриные котлеты (перловка/пюре) + Французский салат + Айс-ти — {fmt(58000)} сум</b>",
            LUNCH_BANNER
        ),
        2: (
            f"<b>🍽 Среда — экватор недели!\n\n"
            f"• 🥩 Бефстроганов (рис/гречка/картофель по дом.) + Овощной салат + Шербет — {fmt(63000)} сум\n"
            f"• 🍗 Куриная отбивная с сыром + Овощной салат + Шербет — {fmt(58000)} сум</b>",
            LUNCH_BANNER
        ),
        3: (
            f"<b>🍚 Четверг — день Плова!\n\n"
            f"• 🥩 Плов из говядины + Ачик-чучук и соленья + Айс-ти — {fmt(63000)} сум\n"
            f"• 🍗 Куриный Ган-пан (рис/пюре) + Ачик-чучук или соленья + Айс-ти — {fmt(58000)} сум</b>",
            LUNCH_BANNER
        ),
        4: (
            f"<b>🎉 Пятница — финал недели!\n\n"
            f"• 🥩 Гуляш из говядины (рис/пюре/овощи печёные) + Греческий салат + Шербет — {fmt(63000)} сум\n"
            f"• 🍗 Курица в соусе карри (рис/пюре/овощи печёные) + Греческий салат + Шербет — {fmt(58000)} сум</b>",
            LUNCH_BANNER
        ),
    }
    if weekday not in posts:
        await update.message.reply_text("Сегодня выходной, постов нет."); return
    text, photo = posts[weekday]
    bot_info = await context.bot.get_me()
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🥗 Заказать обед",
                                     url=f"https://t.me/{bot_info.username}")]])
    try:
        await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=text,
                                      reply_markup=markup, parse_mode='HTML')
        await update.message.reply_text(f"✅ Пост опубликован в {CHANNEL_ID}.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text    = update.message.text
    state   = context.user_data.get('state')
    if state == 'CUSTOM_TIME':
        context.user_data['state'] = None
        await _show_payment(update.message, context, user_id, text, reply=True)
        return
    if user_id == ADMIN_ID:
        if text.lower() == 'отмена':
            context.user_data['state'] = None
            await update.message.reply_text("❌ Отменено."); return
        if state == 'BROADCAST':
            await _do_broadcast(update, context); return
        if state == 'DISH_NAME':
            context.user_data['new_dish']['name'] = text
            context.user_data['state'] = 'DISH_DESC'
            await update.message.reply_text("✏️ Введите описание:"); return
        if state == 'DISH_DESC':
            context.user_data['new_dish']['desc'] = text
            context.user_data['state'] = 'DISH_PRICE'
            await update.message.reply_text("💰 Введите цену (только цифры):"); return
        if state == 'DISH_PRICE':
            if not text.isdigit():
                await update.message.reply_text("⚠️ Только цифры!"); return
            context.user_data['new_dish']['price'] = int(text)
            context.user_data['state'] = 'DISH_PHOTO'
            await update.message.reply_text("🖼 Отправьте ссылку на фото или само фото:"); return
        if state == 'DISH_PHOTO':
            context.user_data['new_dish']['photo'] = text
            _save_dish(context)
            await update.message.reply_text("✅ Блюдо добавлено!"); return

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID: return
    state = context.user_data.get('state')
    if state == 'BROADCAST':
        await _do_broadcast(update, context)
    elif state == 'DISH_PHOTO':
        context.user_data['new_dish']['photo'] = update.message.photo[-1].file_id
        _save_dish(context)
        await update.message.reply_text("✅ Блюдо добавлено!")

def _save_dish(context):
    d = context.user_data.get('new_dish', {})
    add_dish(d.get('cat_id',''), d.get('name',''), d.get('desc',''), d.get('price',0), d.get('photo',''))
    context.user_data['state'] = None

async def _do_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_user_ids()
    count = 0
    msg = await update.message.reply_text("⏳ Рассылка начата...")
    for uid in users:
        try:
            await context.bot.copy_message(chat_id=uid, from_chat_id=update.message.chat_id,
                                            message_id=update.message.message_id)
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    context.user_data['state'] = None
    await msg.edit_text(f"✅ Рассылка завершена! Доставлено: <b>{count}</b>", parse_mode='HTML')

async def _show_payment(source, context, user_id, pickup_time, discount=False, reply=False):
    lines, lunch_total, other_total, _ = get_cart_summary(user_id)
    if not lines: return
    base = lunch_total + other_total
    if discount:
        disc_amt = int(lunch_total * 0.2)
        final    = base - disc_amt
        time_str = f"{pickup_time} (скидка 20% на обеды: -{fmt(disc_amt)} сум)"
    else:
        final    = base
        time_str = pickup_time
    context.user_data['pickup_time'] = time_str
    context.user_data['final_total'] = final
    click_url = (f"https://my.click.uz/services/pay/"
                 f"?service_id={CLICK_SERVICE_ID}&merchant_id={CLICK_MERCHANT_ID}&amount={final}")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Оплатить через Click", url=click_url)],
        [InlineKeyboardButton("✅ Я оплатил(а)",          callback_data="paid")],
        [InlineKeyboardButton("🔙 Назад",                  callback_data="select_time")],
    ])
    caption = (f"<b>🧾 Счёт сформирован\n\n"
               f"Сумма к оплате: {fmt(final)} сум\n"
               f"Время выдачи: {time_str}\n\n"
               f"Нажмите кнопку для оплаты в приложении Click.</b>")
    last_mid = context.user_data.get('last_msg_id')
    try: await context.bot.delete_message(chat_id=user_id, message_id=last_mid)
    except: pass
    if reply:
        try:
            msg = await source.reply_photo(photo=CART_BANNER, caption=caption, reply_markup=kb, parse_mode='HTML')
        except:
            msg = await source.reply_text(text=caption, reply_markup=kb, parse_mode='HTML')
    else:
        try:
            if os.path.exists(QR_FILE_NAME):
                with open(QR_FILE_NAME, "rb") as f:
                    msg = await context.bot.send_photo(chat_id=user_id, photo=f, caption=caption, reply_markup=kb, parse_mode='HTML')
            else:
                msg = await context.bot.send_photo(chat_id=user_id, photo=CART_BANNER, caption=caption, reply_markup=kb, parse_mode='HTML')
        except:
            msg = await context.bot.send_message(chat_id=user_id, text=caption, reply_markup=kb, parse_mode='HTML')
    context.user_data['last_msg_id'] = msg.message_id

async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global menu_active
    q       = update.callback_query
    user_id = q.from_user.id
    data    = q.data
    last    = context.user_data.get('last_msg_id', q.message.message_id)
    init_db()
    if data == "ignore":
        await q.answer(); return
    if data == "home":
        await q.answer()
        context.user_data['state'] = None
        await send_or_edit(user_id, last, MAIN_BANNER,
                           "<b>🏠 Главное меню</b>\n\nВыберите нужный раздел для заказа.",
                           kb_main(), context)
    elif data == "nav_drinks":
        await q.answer()
        await send_or_edit(user_id, last,
                           "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?q=80&w=1200&auto=format&fit=crop",
                           "<b>🥤 Напитки</b>\n\nВыберите категорию:", kb_drinks(), context)
    elif data == "nav_week":
        await q.answer()
        await send_or_edit(user_id, last, MAIN_BANNER,
                           "<b>🗓 Меню на неделю</b>\n\nВыберите день:", kb_week(), context)
    elif data == "lunch_today":
        if not menu_active:
            await q.answer("⛔ Приём заказов закрыт.", show_alert=True); return
        wd = local_now().weekday()
        day_map = {0:'mon',1:'tue',2:'wed',3:'thu',4:'fri',5:'mon',6:'mon'}
        data = f"cat_{day_map[wd]}"
        if wd >= 5:
            await q.answer("Выходной! Открываем понедельник для предзаказа 🤫", show_alert=True)
        else:
            await q.answer()
    if data.startswith("cat_"):
        cat_id = data[4:]
        items  = get_items(cat_id)
        cat    = get_category(cat_id)
        if not items or not cat:
            await q.answer("Раздел пуст."); return
        try: await q.answer()
        except: pass
        lines = []
        for item in items:
            price_str = f" — {fmt(item['price'])} сум" if item['price'] > 0 else ""
            lines.append(f"▪️ <b>{item['name']}</b>{price_str}\n<i>{item['description']}</i>")
        caption = f"<b>{cat['name']}</b>\n\n" + "\n\n".join(lines)
        if len(caption) > 1020:
            caption = caption[:1020] + "…"
        await send_or_edit(user_id, last, cat['banner'], caption,
                           kb_category(user_id, cat_id, items), context)
    elif data.startswith("add_") or data.startswith("rm_"):
        action  = "add" if data.startswith("add_") else "rm"
        parts   = data.split("_")
        item_id = parts[-1]
        cat_id  = "_".join(parts[1:-1])
        items   = get_items(cat_id)
        item    = next((i for i in items if i['id'] == item_id), None)
        if not item: await q.answer(); return
        current = get_cart(user_id).get(item_id, {}).get('count', 0)
        new_cnt = current + (1 if action == "add" else -1)
        update_cart(user_id, item_id, item['name'], item['price'], max(new_cnt, 0))
        await q.answer(f"➕ {item['name']}" if action == "add" else "➖ Удалено")
        await context.bot.edit_message_reply_markup(chat_id=user_id, message_id=last,
                                                     reply_markup=kb_category(user_id, cat_id, items))
    elif data == "cart_view":
        await q.answer()
        lines, lunch, other, _ = get_cart_summary(user_id)
        if not lines:
            await send_or_edit(user_id, last, CART_BANNER, "<b>🛒 Корзина пуста!</b>", kb_main(), context)
            return
        total   = lunch + other
        caption = f"<b>🛒 Ваш заказ:</b>\n\n{lines}\n\n<b>Итого: {fmt(total)} сум</b>\n\nПерейти к оформлению?"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Оформить заказ",    callback_data="select_time")],
            [InlineKeyboardButton("🗑 Очистить корзину", callback_data="cart_clear"),
             InlineKeyboardButton("🔙 В меню",            callback_data="home")],
        ])
        await send_or_edit(user_id, last, CART_BANNER, caption, kb, context)
    elif data == "cart_clear":
        await q.answer("Очищено")
        clear_cart(user_id)
        await send_or_edit(user_id, last, MAIN_BANNER, "<b>Корзина очищена.</b>", kb_main(), context)
    elif data == "select_time":
        await q.answer()
        await send_or_edit(user_id, last, CART_BANNER,
                           "<b>🕒 Выберите время выдачи заказа:</b>\n\nВыдача: 10:00–16:00.",
                           kb_time(), context)
    elif data == "time_custom":
        await q.answer()
        context.user_data['state'] = 'CUSTOM_TIME'
        await send_or_edit(user_id, last, CART_BANNER,
                           "<b>✍️ Напишите желаемое время (например: 14:45):</b>",
                           InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="select_time")]]),
                           context)
    elif data.startswith("tv_"):
        time_val = data[3:]
        if time_val == "discount":
            hour = local_now().hour
            if hour != 16:
                await q.answer("⚠️ Скидка 20% действует только с 16:00 до 17:00!", show_alert=True); return
            _, lunch, _, _ = get_cart_summary(user_id)
            if lunch == 0:
                await q.answer("⚠️ Скидка только на обеды! В корзине их нет.", show_alert=True); return
            await q.answer()
            await _show_payment(None, context, user_id, "16:00–17:00", discount=True)
        else:
            await q.answer()
            await _show_payment(None, context, user_id, time_val)
    elif data == "paid":
        await q.answer()
        lines, lunch, other, items_str = get_cart_summary(user_id)
        if not lines: return
        final       = context.user_data.get('final_total', lunch + other)
        pickup_time = context.user_data.get('pickup_time', 'Не указано')
        order_id    = create_order(user_id, items_str, final, pickup_time)
        clear_cart(user_id)
        name     = q.from_user.first_name + (f" {q.from_user.last_name}" if q.from_user.last_name else "")
        username = f" (@{q.from_user.username})" if q.from_user.username else ""
        text = (f"<b>✅ Заказ #{order_id} принят!</b>\n\n{lines}\n\n"
                f"📍 Место выдачи: 4 этаж, кухня\n🕒 Время: {pickup_time}\n\n"
                f"Мы уведомим вас, когда заказ будет готов!")
        try: await context.bot.delete_message(chat_id=user_id, message_id=last)
        except: pass
        await context.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
        if ADMIN_ID:
            user_row = get_user(user_id)
            phone    = user_row[1] if user_row else "нет"
            adm_txt  = (f"🚨 <b>Новый заказ #{order_id}!</b>\n"
                        f"👤 {name}{username}\n📞 {phone}\n"
                        f"🕒 {pickup_time}\n💰 {fmt(final)} сум\n\n"
                        f"<b>Состав:</b>\n{lines}")
            adm_kb = kb_order_status(order_id, 'paid')
            try: await context.bot.send_message(chat_id=ADMIN_ID, text=adm_txt,
                                                 reply_markup=adm_kb, parse_mode='HTML')
            except: pass
    elif data.startswith("setstatus_"):
        if user_id != ADMIN_ID:
            await q.answer("⛔ Нет доступа."); return
        _, order_id_str, new_status = data.split("_", 2)
        order_id = int(order_id_str)
        set_order_status(order_id, new_status)
        await q.answer(f"Статус: {ORDER_STATUSES.get(new_status)}", show_alert=True)
        conn = _conn(); c = conn.cursor()
        c.execute("SELECT user_id FROM orders WHERE order_id=?", (order_id,))
        row = c.fetchone(); conn.close()
        if row:
            notif_map = {
                'cooking':   f"👨‍🍳 <b>Заказ #{order_id} готовится!</b>\nОжидание 10–15 минут.",
                'ready':     f"✅ <b>Заказ #{order_id} готов!</b>\nЗабирайте на 4 этаже! 🎉",
                'delivered': f"🎉 <b>Заказ #{order_id} выдан.</b>\nПриятного аппетита!",
            }
            if new_status in notif_map:
                try: await context.bot.send_message(chat_id=row[0], text=notif_map[new_status], parse_mode='HTML')
                except: pass
        new_kb = kb_order_status(order_id, new_status)
        try: await q.message.edit_reply_markup(reply_markup=new_kb)
        except: pass
    elif data.startswith("adm_"):
        if user_id != ADMIN_ID:
            await q.answer("⛔ Нет доступа."); return
        await q.answer()
        if data == "adm_stats":
            count, revenue = get_today_stats()
            users_count    = len(get_all_user_ids())
            active_count   = len(get_active_orders())
            await q.message.reply_text(
                f"<b>📊 Статистика</b>\n\n"
                f"👥 Пользователей: <b>{users_count}</b>\n"
                f"🛒 Заказов сегодня: <b>{count}</b>\n"
                f"💰 Выручка сегодня: <b>{fmt(revenue)} сум</b>\n"
                f"🔄 Активных заказов: <b>{active_count}</b>",
                parse_mode='HTML')
        elif data == "adm_kitchen":
            summary = get_kitchen_summary()
            if not summary:
                await q.message.reply_text("<b>🍽 Сводка пуста. Все заказы выданы!</b>", parse_mode='HTML')
            else:
                lines_k = "\n".join(f"• <b>{name}</b> — {cnt} шт." for name, cnt in summary.most_common())
                await q.message.reply_text(
                    f"<b>🍽 Сводка для кухни</b>\n<i>(оплачен / готовится)</i>\n\n{lines_k}",
                    parse_mode='HTML')
        elif data == "adm_orders":
            orders = get_active_orders()
            if not orders:
                await q.message.reply_text("<b>📋 Активных заказов нет.</b>", parse_mode='HTML')
            else:
                for o in orders[:10]:
                    status_label = ORDER_STATUSES.get(o['status'], o['status'])
                    txt = (f"<b>Заказ #{o['order_id']}</b> | {status_label}\n"
                           f"🕒 {o['pickup_time']}\n💰 {fmt(o['total'])} сум\n"
                           f"<i>{o['items'][:200]}</i>")
                    adm_kb = kb_order_status(o['order_id'], o['status'])
                    try: await q.message.reply_text(txt, reply_markup=adm_kb, parse_mode='HTML')
                    except: pass
        elif data == "adm_broadcast":
            context.user_data['state'] = 'BROADCAST'
            await q.message.reply_text(
                "<b>📢 Отправьте сообщение (текст или фото).\n\nДля отмены напишите 'отмена'.</b>",
                parse_mode='HTML')
        elif data == "adm_add":
            cats = get_all_categories()
            kb_cats = InlineKeyboardMarkup(
                [[InlineKeyboardButton(c['name'], callback_data=f"adm_addcat_{c['id']}")] for c in cats])
            await q.message.reply_text("<b>В какую категорию добавить?</b>", reply_markup=kb_cats, parse_mode='HTML')
        elif data.startswith("adm_addcat_"):
            cat_id = data.split("_", 2)[2]
            context.user_data['state']    = 'DISH_NAME'
            context.user_data['new_dish'] = {'cat_id': cat_id}
            await q.message.reply_text("<b>Введите название блюда:</b>", parse_mode='HTML')
        elif data == "adm_del":
            cats = get_all_categories()
            kb_cats = InlineKeyboardMarkup(
                [[InlineKeyboardButton(c['name'], callback_data=f"adm_delcat_{c['id']}")] for c in cats])
            await q.message.reply_text("<b>Из какой категории удалить?</b>", reply_markup=kb_cats, parse_mode='HTML')
        elif data.startswith("adm_delcat_"):
            cat_id = data.split("_", 2)[2]
            items  = get_items(cat_id)
            if not items:
                await q.message.reply_text("<b>Категория пуста.</b>", parse_mode='HTML'); return
            kb_items = InlineKeyboardMarkup(
                [[InlineKeyboardButton(i['name'], callback_data=f"adm_delitem_{i['id']}")] for i in items])
            await q.message.reply_text("<b>Выберите блюдо для удаления:</b>", reply_markup=kb_items, parse_mode='HTML')
        elif data.startswith("adm_delitem_"):
            item_id = data.split("_")[2]
            delete_dish(item_id)
            await q.message.reply_text("<b>✅ Блюдо удалено.</b>", parse_mode='HTML')
        elif data == "adm_export":
            rows = get_all_orders_for_export()
            if not rows:
                await q.answer("Нет данных.", show_alert=True); return
            fname = f"report_{local_now().strftime('%Y%m%d_%H%M')}.csv"
            with open(fname, mode='w', encoding='utf-8-sig', newline='') as f:
                w = csv.writer(f, delimiter=';')
                w.writerow(["ID", "Дата", "Телефон", "Состав", "Сумма (сум)", "Статус", "Время выдачи"])
                for r in rows:
                    phone = str(r[2] or '')
                    if phone and not phone.startswith('+'): phone = '+' + phone
                    w.writerow([r[0], r[1], f'="{phone}"',
                                str(r[3]).replace("\n","   |   "), r[4],
                                ORDER_STATUSES.get(r[5], r[5]), r[6]])
            with open(fname, 'rb') as f:
                await context.bot.send_document(chat_id=user_id, document=f,
                    caption="<b>📥 Отчёт готов.</b>", parse_mode='HTML')
            os.remove(fname)
        elif data == "adm_toggle":
            menu_active = not menu_active
            status = "ОТКРЫТ ✅" if menu_active else "ЗАКРЫТ ⛔"
            await q.answer(f"Приём заказов: {status}", show_alert=True)

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start", "Главное меню"),
        BotCommand("admin", "Панель администратора"),
        BotCommand("post",  "Опубликовать пост в канал"),
        BotCommand("myid",  "Узнать свой Telegram ID"),
    ])

async def health(request):
    return web.Response(text="OK")

async def main():
    init_db()
    app_bot = Application.builder().token(TOKEN).post_init(post_init).build()
    app_bot.add_handler(CommandHandler("start", cmd_start))
    app_bot.add_handler(CommandHandler("admin", cmd_admin))
    app_bot.add_handler(CommandHandler("post",  cmd_post))
    app_bot.add_handler(CommandHandler("myid",  cmd_myid))
    app_bot.add_handler(MessageHandler(filters.CONTACT,                 handle_contact))
    app_bot.add_handler(MessageHandler(filters.PHOTO,                   handle_photo))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app_bot.add_handler(CallbackQueryHandler(btn))
    web_app = web.Application()
    web_app.router.add_get("/", health)
    runner = web.AppRunner(web_app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080))).start()
    await app_bot.initialize()
    await app_bot.start()
    await app_bot.updater.start_polling()
    logging.info(">>> Бот запущен <<<")
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
