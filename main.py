import os
import logging
import asyncio
import sqlite3
import csv
from datetime import datetime, timedelta
from aiohttp import web
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    InputMediaPhoto,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН")
ADMIN_ID_STR = os.getenv("ADMIN_ID", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel")

# Настройки для оплаты Click
CLICK_SERVICE_ID = "52528"
CLICK_MERCHANT_ID = "20421"
QR_FILE_NAME = "qr.jpg"

# Профессиональные изображения для баннеров
MAIN_BANNER = "https://images.unsplash.com/photo-1498837167922-41cfa6f318ba?q=80&w=1200&auto=format&fit=crop"
CART_BANNER = "https://images.unsplash.com/photo-1556742044-3c52d6e88c62?q=80&w=1200&auto=format&fit=crop"
LUNCH_BANNER = "https://images.unsplash.com/photo-1543339308-43e59d6b73a6?q=80&w=1200&auto=format&fit=crop"
MONDAY_BANNER = "https://images.unsplash.com/photo-1548943487-a2e4f43b4850?q=80&w=1200&auto=format&fit=crop"

try:
    ADMIN_ID = int(ADMIN_ID_STR.strip())
except (ValueError, TypeError):
    ADMIN_ID = None

DB_NAME = 'delivery_bot_v18.db'
menu_active = True

# ==================== ДАННЫЕ МЕНЮ ====================
DEFAULT_CATEGORIES = [
    ('breakfasts', 'Завтраки', 'https://images.unsplash.com/photo-1533089860892-a7c6f0a88666?q=80&w=1200&auto=format&fit=crop'),
    ('hot_drinks', 'Горячие напитки', 'https://images.unsplash.com/photo-1497935586351-b67a49e012bf?q=80&w=1200&auto=format&fit=crop'),
    ('cold_drinks', 'Холодные напитки', 'https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?q=80&w=1200&auto=format&fit=crop'),
    ('fresh_drinks', 'Фреши', 'https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?q=80&w=1200&auto=format&fit=crop'),
    ('mon', 'Понедельник', MONDAY_BANNER), 
    ('tue', 'Вторник', LUNCH_BANNER), 
    ('wed', 'Среда', LUNCH_BANNER),
    ('thu', 'Четверг', LUNCH_BANNER), 
    ('fri', 'Пятница', LUNCH_BANNER)
]

DEFAULT_ITEMS = [
    ('breakfasts', 'Яичница с сосисками', 'Классический сытный завтрак из яиц и сосисок.', 40000, ''),
    ('breakfasts', 'Омлет', 'Пышный свежеприготовленный омлет.', 35000, ''),
    ('breakfasts', 'Гренки 4 шт', 'Золотистые поджаренные гренки.', 20000, ''),
    ('breakfasts', 'Овсяная каша', 'Вкусная и полезная овсяная каша.', 25000, ''),
    ('breakfasts', 'Сендвич с говядиной и сыром', 'Сытный сендвич с говядиной и расплавленным сыром.', 32000, ''),
    
    ('hot_drinks', 'Американо', 'Классический черный кофе.', 18000, ''),
    ('hot_drinks', 'Капучино', 'Кофе с пышной молочной пеной.', 20000, ''),
    ('hot_drinks', 'Латте', 'Мягкий кофейный напиток с большим количеством молока.', 22000, ''),
    ('hot_drinks', 'Флэт Уайт', 'Насыщенный кофе с бархатистой молочной пеной.', 30000, ''),
    
    ('cold_drinks', 'Кола 0.25 / Кола (Zero)', 'Освежающая газировка.', 13000, ''),
    ('cold_drinks', 'Fanta 0.25', 'Апельсиновая газировка.', 12000, ''),
    ('cold_drinks', 'Мохито', 'Охлаждающий напиток.', 20000, ''),
    ('cold_drinks', 'Chortoq 0.25 (с газом)', 'Минеральная газированная вода.', 12000, ''),
    
    ('fresh_drinks', 'Яблочный фреш', 'Свежевыжатый сок из зеленых яблок (250 мл).', 30000, ''),
    ('fresh_drinks', 'Морковно-яблочный фреш', 'Витаминный заряд (250 мл).', 30000, ''),
    ('fresh_drinks', 'Фреш Детокс', 'Свекла, яблоко, морковь (250 мл).', 32000, ''),

    ('mon', '🥩 Жаркое + Салат + Шербет', 'Сытное жаркое из говядины, витаминный салат и Шербет.', 62000, ''),
    ('mon', '🍗 Курица Карри + Салат + Шербет', 'Курица карри (рис и пюре), витаминный салат и Шербет.', 58000, ''),
    
    ('tue', '🥩 Говядина с овощами + Салат + Айс-ти', 'Сочная говядина (рис/гречка), Французский салат и Айс-ти.', 62000, ''),
    ('tue', '🍗 Куриные котлеты + Салат + Айс-ти', 'Куриные котлеты (рис/гречка), Французский салат и Айс-ти.', 58000, ''),
    
    ('wed', '🥩 Бефстроганов + Салат + Шербет', 'Бефстроганов (пюре/рис/карт.), Овощной салат и Шербет.', 62000, ''),
    ('wed', '🍗 Отбивная + Салат + Шербет', 'Отбивная с сыром (пюре/рис/карт.), Овощной салат и Шербет.', 58000, ''),
    
    # ИСПРАВЛЕНО ДЛЯ ЧЕТВЕРГА (Салат на выбор)
    ('thu', '🥩 Плов + Ачик-чучук или соленья + Айс-ти', 'Плов, салат Ачик-чучук или соленья и Айс-ти.', 62000, ''),
    ('thu', '🍗 Куриный Ган-пан + Ачик-чучук или соленья + Айс-ти', 'Ган-пан (пюре/перловка), Ачик-чучук или соленья и Айс-ти.', 58000, ''),
    
    ('fri', '🥩 Гуляш + Салат Греческий + Шербет', 'Сытный гуляш (рис/гречка/овощи), Греческий салат и Шербет.', 62000, ''),
    ('fri', '🍗 Казан-кебаб + Салат + Шербет', 'Куриный казан-кебаб (рис/гречка/овощи), Греческий салат и Шербет.', 58000, '')
]

# ==================== РАБОТА С БД ====================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, phone TEXT, orders_count INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS active_orders (user_id INTEGER, item_id TEXT, item_name TEXT, price INTEGER, count INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS order_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, date TEXT, items TEXT, total INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS menu_categories (id TEXT PRIMARY KEY, name TEXT, banner TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS menu_items (id INTEGER PRIMARY KEY AUTOINCREMENT, cat_id TEXT, name TEXT, description TEXT, price INTEGER, image TEXT)''')
    conn.commit()
    conn.close()
    seed_menu_if_empty()

def seed_menu_if_empty():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM menu_categories")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO menu_categories VALUES (?, ?, ?)", DEFAULT_CATEGORIES)
        cursor.executemany("INSERT INTO menu_items (cat_id, name, description, price, image) VALUES (?, ?, ?, ?, ?)", DEFAULT_ITEMS)
    conn.commit()
    conn.close()

def get_categories():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM menu_categories")
    cats = [{"id": r[0], "name": r[1]} for r in cursor.fetchall()]
    conn.close()
    return cats

def get_category_info(cat_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, banner FROM menu_categories WHERE id = ?", (cat_id,))
    row = cursor.fetchone()
    conn.close()
    return {"id": row[0], "name": row[1], "banner": row[2]} if row else None

def get_items_by_cat(cat_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, price, image FROM menu_items WHERE cat_id = ?", (cat_id,))
    items = [{"id": str(r[0]), "name": r[1], "description": r[2], "price": r[3], "image": r[4]} for r in cursor.fetchall()]
    conn.close()
    return items

def save_new_dish(data):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO menu_items (cat_id, name, description, price, image) VALUES (?, ?, ?, ?, ?)", 
                   (data['cat_id'], data['name'], data['desc'], data['price'], data['photo']))
    conn.commit()
    conn.close()

def delete_item(item_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
    cursor.execute("DELETE FROM active_orders WHERE item_id = ?", (item_id,))
    conn.commit()
    conn.close()

def get_user_db(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_user_db(user_id, phone):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, phone, orders_count) VALUES (?, ?, ?)", (user_id, phone, 0))
    conn.commit()
    conn.close()

def get_all_user_ids():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    ids = [r[0] for r in cursor.fetchall()]
    conn.close()
    return ids

def save_order_history(user_id, items_str, total):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO order_history (user_id, date, items, total) VALUES (?, ?, ?, ?)", (user_id, date_str, items_str, total))
    cursor.execute("UPDATE users SET orders_count = orders_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_orders_for_export():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT o.id, o.date, u.phone, o.items, o.total FROM order_history o LEFT JOIN users u ON o.user_id = u.user_id ORDER BY o.id DESC")
    data = cursor.fetchall()
    conn.close()
    return data

def update_cart_db(user_id, item_id, item_name, price, count):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if count == 0:
        cursor.execute("DELETE FROM active_orders WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    else:
        cursor.execute("INSERT OR REPLACE INTO active_orders (user_id, item_id, item_name, price, count) VALUES (?, ?, ?, ?, ?)", (user_id, item_id, item_name, price, count))
    conn.commit()
    conn.close()

def get_cart_db(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT item_id, item_name, price, count FROM active_orders WHERE user_id = ?", (user_id,))
    cart_items = cursor.fetchall()
    conn.close()
    cart = {}
    for item in cart_items: cart[item[0]] = {"name": item[1], "price": item[2], "count": item[3]}
    return cart

def clear_cart_db(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM active_orders WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_order_summary(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT item_id, item_name, price, count FROM active_orders WHERE user_id = ?", (user_id,))
    cart_items = cursor.fetchall()
    
    if not cart_items:
        conn.close()
        return None, 0, 0, ""
        
    cursor.execute("SELECT id, cat_id FROM menu_items")
    cat_map = {str(r[0]): r[1] for r in cursor.fetchall()}
    conn.close()
    
    formatted_lines = []
    short_lines = []
    total_discountable = 0      
    total_non_discountable = 0  
    
    for item_id, name, price, cnt in cart_items:
        total_price = price * cnt
        formatted_lines.append(f"• {name} x{cnt} — {total_price:,} сум".replace(",", " "))
        short_lines.append(f"{name} x{cnt}")
        
        cat_id = cat_map.get(str(item_id))
        if cat_id in ['mon', 'tue', 'wed', 'thu', 'fri']:
            total_discountable += total_price
        else:
            total_non_discountable += total_price
            
    return "\n".join(formatted_lines), total_discountable, total_non_discountable, ", ".join(short_lines)

# ==================== КЛАВИАТУРЫ ====================
def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🍳 Завтраки", callback_data="cat_breakfasts")],
        [InlineKeyboardButton("🍱 Комплексный обед дня", callback_data="lunch_today")],
        [InlineKeyboardButton("🥤 Напитки", callback_data="nav_drinks")],
        [InlineKeyboardButton("🗓 Меню на неделю", callback_data="nav_week")],
        [InlineKeyboardButton("🛒 Корзина", callback_data="cart_list")]
    ])

def get_drinks_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("☕️ Горячие напитки", callback_data="cat_hot_drinks")],
        [InlineKeyboardButton("🧊 Холодные напитки", callback_data="cat_cold_drinks")],
        [InlineKeyboardButton("🍹 Фреши", callback_data="cat_fresh_drinks")],
        [InlineKeyboardButton("🔙 Назад", callback_data="home")]
    ])

def get_week_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Пн", callback_data="cat_mon"), InlineKeyboardButton("Вт", callback_data="cat_tue"), InlineKeyboardButton("Ср", callback_data="cat_wed")],
        [InlineKeyboardButton("Чт", callback_data="cat_thu"), InlineKeyboardButton("Пт", callback_data="cat_fri")],
        [InlineKeyboardButton("🔙 Назад", callback_data="home")]
    ])

def get_category_list_keyboard(user_id, cat_id, items):
    keyboard = []
    cart = get_cart_db(user_id)
    
    for item in items:
        item_id = str(item['id'])
        display_name = item['name']
        
        keyboard.append([InlineKeyboardButton(f"🍽 {display_name}", callback_data="ignore")])
        
        count = cart.get(item_id, {}).get('count', 0)
        if count > 0:
            keyboard.append([
                InlineKeyboardButton("➖", callback_data=f"list_rm_{cat_id}_{item_id}"),
                InlineKeyboardButton(f"{count} шт", callback_data="ignore"),
                InlineKeyboardButton("➕", callback_data=f"list_add_{cat_id}_{item_id}")
            ])
        else:
            keyboard.append([InlineKeyboardButton("Добавить", callback_data=f"list_add_{cat_id}_{item_id}")])

    back_data = "home"
    if cat_id in ['hot_drinks', 'cold_drinks', 'fresh_drinks']: back_data = "nav_drinks"
    elif cat_id in ['mon', 'tue', 'wed', 'thu', 'fri']: back_data = "nav_week"
        
    keyboard.append([InlineKeyboardButton("🛒 Корзина", callback_data="cart_list"), InlineKeyboardButton("🔙 Назад", callback_data=back_data)])
    return InlineKeyboardMarkup(keyboard)

# ==================== ОТПРАВКА СООБЩЕНИЙ ====================
async def edit_media_message(chat_id, message_id, photo_source, caption, reply_markup, context):
    try:
        if not photo_source: raise ValueError("No photo")
        media = InputMediaPhoto(media=photo_source, caption=caption, parse_mode='HTML')
        await context.bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=reply_markup)
    except Exception as e:
        try: await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception: pass
        try:
            if photo_source:
                msg = await context.bot.send_photo(chat_id=chat_id, photo=photo_source, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
            else:
                msg = await context.bot.send_message(chat_id=chat_id, text=caption, reply_markup=reply_markup, parse_mode='HTML')
        except Exception:
            msg = await context.bot.send_message(chat_id=chat_id, text=caption, reply_markup=reply_markup, parse_mode='HTML')
        context.user_data['last_msg_id'] = msg.message_id

async def render_start(chat_id, context):
    caption = "<b>Главное меню\n\nВыберите нужный раздел для заказа.</b>"
    try: await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data.get('last_msg_id'))
    except Exception: pass
    
    try:
        msg = await context.bot.send_photo(chat_id=chat_id, photo=MAIN_BANNER, caption=caption, reply_markup=get_main_keyboard(), parse_mode='HTML')
    except Exception:
        msg = await context.bot.send_message(chat_id=chat_id, text=caption, reply_markup=get_main_keyboard(), parse_mode='HTML')
    context.user_data['last_msg_id'] = msg.message_id

# ==================== БАЗОВЫЕ ХЕНДЛЕРЫ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_db()
    if not get_user_db(user_id):
        keyboard = [[KeyboardButton("📱 Поделиться номером", request_contact=True)]]
        await context.bot.send_message(chat_id=user_id, text="<b>Для начала работы, пожалуйста, поделитесь номером телефона.</b>", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True), parse_mode='HTML')
    else:
        await render_start(user_id, context)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    contact = update.message.contact
    if contact:
        add_user_db(user_id, contact.phone_number)
        await update.message.reply_text("<b>✅ Номер сохранен.</b>", reply_markup=ReplyKeyboardRemove(), parse_mode='HTML')
        await render_start(user_id, context)

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = f"<b>Ваш Telegram ID:\n<code>{user_id}</code>\n\nСкопируйте его и вставьте в переменную ADMIN_ID в Railway.</b>"
    await update.message.reply_text(text, parse_mode='HTML')

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not ADMIN_ID or user_id != ADMIN_ID: 
        await update.message.reply_text("<b>⛔ У вас нет прав администратора.</b>", parse_mode='HTML')
        return
    
    keyboard = [
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("➕ Добавить блюдо", callback_data="admin_add_dish"), InlineKeyboardButton("🗑 Удалить", callback_data="admin_del_dish")],
        [InlineKeyboardButton("📊 Скачать отчет (Excel)", callback_data="admin_export_excel")],
        [InlineKeyboardButton("⛔ Открыть/Закрыть заказы", callback_data="admin_toggle")]
    ]
    await update.message.reply_text("<b>👑 Панель администратора\nУправление меню и отчетами.</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def post_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not ADMIN_ID or user_id != ADMIN_ID: return

    weekday = datetime.now().weekday()
    posts_by_day = {
        0: ("<b>Понедельник — продуктивное начало!\n\nВ комплекс уже включен Витаминный салат и Шербет!\n\nНа выбор:\n• 🥩 Жаркое с картофелем — 62 000 сум\n• 🍗 Курица Карри — 58 000 сум</b>", MONDAY_BANNER),
        1: ("<b>Вторник — время вкусного обеда!\n\nВ комплекс уже включен Французский салат и Айс-ти!\n\nНа выбор:\n• 🥩 Говядина с овощами — 62 000 сум\n• 🍗 Куриные котлеты — 58 000 сум</b>", LUNCH_BANNER),
        2: ("<b>Среда — экватор недели!\n\nВ комплекс уже включен Овощной салат и Шербет!\n\nНа выбор:\n• 🥩 Бефстроганов — 62 000 сум\n• 🍗 Куриная отбивная — 58 000 сум</b>", LUNCH_BANNER),
        3: ("<b>Четверг — день Плова!\n\nВ комплекс уже включен Салат (Ачик-чучук или соленья) и Айс-ти!\n\nНа выбор:\n• 🥩 Плов из говядины — 62 000 сум\n• 🍗 Куриный Ган-пан — 58 000 сум</b>", LUNCH_BANNER),
        4: ("<b>Пятница — завершаем неделю вкусно!\n\nВ комплекс уже включен Греческий салат и Шербет!\n\nНа выбор:\n• 🥩 Гуляш из говядины — 62 000 сум\n• 🍗 Куриный казан-кебаб — 58 000 сум</b>", LUNCH_BANNER)
    }

    if weekday not in posts_by_day:
        await update.message.reply_text("<b>Сегодня выходной! Готовых текстов нет.</b>", parse_mode='HTML')
        return

    text, photo = posts_by_day[weekday]
    bot_info = await context.bot.get_me()
    bot_url = f"https://t.me/{bot_info.username}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🥗 Заказать обед", url=bot_url)]])

    try:
        await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=text, reply_markup=keyboard, parse_mode='HTML')
        await update.message.reply_text(f"<b>✅ Пост отправлен в канал {CHANNEL_ID}.</b>", parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"<b>❌ Ошибка отправки: {e}</b>", parse_mode='HTML')

async def run_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_user_ids()
    count = 0
    msg = await update.message.reply_text("<b>⏳ Рассылка начата...</b>", parse_mode='HTML')
    for uid in users:
        try:
            await context.bot.copy_message(chat_id=uid, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
            count += 1
            await asyncio.sleep(0.05)
        except Exception: pass
    context.user_data['admin_state'] = None
    await msg.edit_text(f"<b>✅ Рассылка завершена!\nУспешно отправлено: {count} пользователям.</b>", parse_mode='HTML')

# === ОБРАБОТЧИК ТЕКСТА ===
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    state = context.user_data.get('user_state')
    if state == 'WAITING_CUSTOM_TIME':
        time_str = update.message.text
        context.user_data['user_state'] = None
        context.user_data['pickup_time'] = time_str
        
        _, disc, non_disc, _ = get_order_summary(user_id)
        base_total = disc + non_disc
        context.user_data['final_total'] = base_total
        
        click_url = f"https://my.click.uz/services/pay/?service_id={CLICK_SERVICE_ID}&merchant_id={CLICK_MERCHANT_ID}&amount={base_total}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Оплатить через Click", url=click_url)], 
            [InlineKeyboardButton("✅ Оплата завершена", callback_data="paid_order")],
            [InlineKeyboardButton("🔙 Назад", callback_data="select_time")]
        ])
        
        formatted_total = f"{base_total:,}".replace(",", " ")
        caption = f"<b>🧾 Счет сформирован\n\nСумма к оплате: {formatted_total} сум\nВремя выдачи: {time_str}\n\nПожалуйста, перейдите по ссылке для оплаты.</b>"
        
        try:
            msg = await update.message.reply_photo(photo=CART_BANNER, caption=caption, reply_markup=kb, parse_mode='HTML')
            context.user_data['last_msg_id'] = msg.message_id
        except Exception:
            msg = await update.message.reply_text(text=caption, reply_markup=kb, parse_mode='HTML')
            context.user_data['last_msg_id'] = msg.message_id
        return

    # Админ
    if ADMIN_ID and user_id == ADMIN_ID:
        text = update.message.text
        admin_state = context.user_data.get('admin_state')
        if text.lower() == 'отмена':
            context.user_data['admin_state'] = None
            await update.message.reply_text("<b>❌ Отменено.</b>", parse_mode='HTML')
            return
        if admin_state == 'WAITING_BROADCAST':
            await run_broadcast(update, context)
            return
        elif admin_state == 'WAITING_DISH_NAME':
            context.user_data['new_dish']['name'] = text
            context.user_data['admin_state'] = 'WAITING_DISH_DESC'
            await update.message.reply_text("<b>✏️ Введите описание блюда:</b>", parse_mode='HTML')
            return
        elif admin_state == 'WAITING_DISH_DESC':
            context.user_data['new_dish']['desc'] = text
            context.user_data['admin_state'] = 'WAITING_DISH_PRICE'
            await update.message.reply_text("<b>💰 Введите цену (только цифры):</b>", parse_mode='HTML')
            return
        elif admin_state == 'WAITING_DISH_PRICE':
            if not text.isdigit():
                await update.message.reply_text("<b>⚠️ Только цифры.</b>", parse_mode='HTML')
                return
            context.user_data['new_dish']['price'] = int(text)
            context.user_data['admin_state'] = 'WAITING_DISH_PHOTO'
            await update.message.reply_text("<b>🖼 Отправьте ссылку или картинку:</b>", parse_mode='HTML')
            return
        elif admin_state == 'WAITING_DISH_PHOTO':
            context.user_data['new_dish']['photo'] = text 
            save_new_dish(context.user_data['new_dish'])
            context.user_data['admin_state'] = None
            await update.message.reply_text("<b>✅ Блюдо добавлено!</b>", parse_mode='HTML')
            return

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_ID and user_id == ADMIN_ID:
        state = context.user_data.get('admin_state')
        if state == 'WAITING_BROADCAST':
            await run_broadcast(update, context)
        elif state == 'WAITING_DISH_PHOTO':
            photo_id = update.message.photo[-1].file_id
            context.user_data['new_dish']['photo'] = photo_id
            save_new_dish(context.user_data['new_dish'])
            context.user_data['admin_state'] = None
            await update.message.reply_text("<b>✅ Блюдо добавлено!</b>", parse_mode='HTML')

# ==================== ОСНОВНОЙ ОБРАБОТЧИК КНОПОК ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    init_db()
    last_msg_id = context.user_data.get('last_msg_id')

    if data == "ignore":
        await query.answer()
        return

    # ВЕТКА АДМИНА
    if data.startswith("admin_"):
        if not ADMIN_ID or user_id != ADMIN_ID: return
        if data == "admin_toggle":
            global menu_active
            menu_active = not menu_active
            status = "ОТКРЫТ" if menu_active else "ЗАКРЫТ"
            await query.answer(f"Заказы: {status}", show_alert=True)
        elif data == "admin_broadcast":
            context.user_data['admin_state'] = 'WAITING_BROADCAST'
            await query.message.reply_text("<b>Отправьте сообщение (текст/фото). Для отмены напишите 'отмена'.</b>", parse_mode='HTML')
        elif data == "admin_add_dish":
            cats = get_categories()
            kb = [[InlineKeyboardButton(c['name'], callback_data=f"admin_addcat_{c['id']}")] for c in cats]
            await query.message.reply_text("<b>В какую категорию?</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
        elif data.startswith("admin_addcat_"):
            cat_id = data.split("_")[2]
            context.user_data['admin_state'] = 'WAITING_DISH_NAME'
            context.user_data['new_dish'] = {'cat_id': cat_id}
            await query.message.reply_text("<b>Введите название блюда:</b>", parse_mode='HTML')
        elif data == "admin_del_dish":
            cats = get_categories()
            kb = [[InlineKeyboardButton(c['name'], callback_data=f"admin_delcat_{c['id']}")] for c in cats]
            await query.message.reply_text("<b>Откуда удалить блюдо?</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
        elif data.startswith("admin_delcat_"):
            cat_id = data.split("_")[2]
            items = get_items_by_cat(cat_id)
            if not items:
                await query.message.reply_text("<b>Пусто.</b>", parse_mode='HTML')
                return
            kb = [[InlineKeyboardButton(i['name'], callback_data=f"admin_delitem_{i['id']}")] for i in items]
            await query.message.reply_text("<b>Выберите блюдо для удаления:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
        elif data.startswith("admin_delitem_"):
            item_id = data.split("_")[2]
            delete_item(item_id)
            await query.message.reply_text("<b>Удалено.</b>", parse_mode='HTML')
        elif data == "admin_export_excel":
            orders = get_all_orders_for_export()
            if not orders:
                await query.answer("Отчет пуст.", show_alert=True)
                return
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            with open(filename, mode='w', encoding='utf-8-sig', newline='') as file:
                writer = csv.writer(file, delimiter=';') 
                writer.writerow(["ID Заказа", "Дата и Время", "Телефон клиента", "Состав заказа", "Сумма (сум)"])
                for row in orders:
                    order_id, date_str, raw_phone, items_str, total = row[0], row[1], str(row[2]), str(row[3]).replace("\n", "   |   "), row[4]
                    if not raw_phone.startswith('+'): raw_phone = '+' + raw_phone
                    phone_excel = f'="{raw_phone}"' 
                    writer.writerow([order_id, date_str, phone_excel, items_str, total])
            with open(filename, 'rb') as doc:
                await context.bot.send_document(chat_id=user_id, document=doc, caption="<b>Отчет готов.\nВ Excel нажмите Ctrl+A, затем 2 раза кликните по границе любой колонки сверху.</b>", parse_mode='HTML')
            os.remove(filename)
            await query.answer("Отчет отправлен.")
        await query.answer()
        return

    # НАВИГАЦИЯ
    if data == "home":
        await query.answer()
        context.user_data['user_state'] = None
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "<b>Главное меню\n\nВыберите нужный раздел для заказа.</b>", get_main_keyboard(), context)

    elif data == "nav_drinks":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?q=80&w=1200&auto=format&fit=crop", "<b>Напитки\n\nВыберите категорию:</b>", get_drinks_keyboard(), context)

    elif data == "nav_week":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "<b>Меню на неделю\n\nПосмотрите расписание обедов:</b>", get_week_menu_keyboard(), context)

    elif data == "lunch_today":
        weekday = datetime.now().weekday()
        days_map = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri', 5: 'mon', 6: 'mon'}
        cat_id = days_map[weekday]
        if weekday >= 5:
            await query.answer("Сегодня выходной! Для тестов открываем меню Понедельника 🤫", show_alert=True)
        else:
            await query.answer()
        data = f"cat_{cat_id}" 

    # ПРОСМОТР КАТЕГОРИЙ
    if data.startswith("cat_"):
        if data != "lunch_today": 
            try: await query.answer()
            except: pass
        cat_id = data[4:] 
        items = get_items_by_cat(cat_id)
        cat_info = get_category_info(cat_id)
        if not items or not cat_info: return
        
        caption = f"<b>{cat_info['name']}\n\n"
        for item in items:
            price_str = f" — {item['price']:,} сум".replace(",", " ") if item['price'] > 0 else ""
            caption += f"• {item['name']}{price_str}\n{item['description']}\n\n"
        caption = caption.strip() + "</b>"
        
        await edit_media_message(user_id, last_msg_id, cat_info['banner'], caption, get_category_list_keyboard(user_id, cat_id, items), context)

    elif data.startswith("list_add_"):
        parts = data.split("_")
        item_id = parts[-1]
        cat_id = "_".join(parts[2:-1])
        items = get_items_by_cat(cat_id)
        item = next((i for i in items if str(i['id']) == item_id), None)
        if not item: return
        new_count = get_cart_db(user_id).get(item_id, {}).get('count', 0) + 1
        update_cart_db(user_id, item_id, item['name'], item['price'], new_count)
        await query.answer()
        await context.bot.edit_message_reply_markup(chat_id=user_id, message_id=last_msg_id, reply_markup=get_category_list_keyboard(user_id, cat_id, items))

    elif data.startswith("list_rm_"):
        parts = data.split("_")
        item_id = parts[-1]
        cat_id = "_".join(parts[2:-1])
        items = get_items_by_cat(cat_id)
        item = next((i for i in items if str(i['id']) == item_id), None)
        if not item: return
        current_count = get_cart_db(user_id).get(item_id, {}).get('count', 0)
        if current_count > 0:
            new_count = current_count - 1
            update_cart_db(user_id, item_id, item['name'], item['price'], new_count)
            await query.answer()
            await context.bot.edit_message_reply_markup(chat_id=user_id, message_id=last_msg_id, reply_markup=get_category_list_keyboard(user_id, cat_id, items))

    # КОРЗИНА И ВЫБОР ВРЕМЕНИ
    elif data == "cart_list":
        await query.answer()
        context.user_data['user_state'] = None 
        items_text, disc, non_disc, _ = get_order_summary(user_id)
        if not items_text:
            await edit_media_message(user_id, last_msg_id, CART_BANNER, "<b>Ваша корзина пуста.</b>", get_main_keyboard(), context)
            return
        total = disc + non_disc
        caption = f"<b>Ваш заказ:\n\n{items_text}\n\nИтого: {total:,} сум\n\nПерейти к оформлению?</b>".replace(",", " ")
        kb = [[InlineKeyboardButton("💳 Оформить заказ", callback_data="select_time")], [InlineKeyboardButton("🗑 Очистить корзину", callback_data="cancel_order"), InlineKeyboardButton("🔙 В меню", callback_data="home")]]
        await edit_media_message(user_id, last_msg_id, CART_BANNER, caption, InlineKeyboardMarkup(kb), context)

    elif data == "cancel_order":
        await query.answer("Очищено")
        clear_cart_db(user_id)
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "<b>Корзина очищена.</b>", get_main_keyboard(), context)

    elif data == "select_time":
        await query.answer()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏃 Забрать сейчас", callback_data="timeval_Сейчас (В порядке очереди)")],
            [InlineKeyboardButton("🕒 Отложить (выбрать время)", callback_data="time_postpone")],
            [InlineKeyboardButton("🔥 Скидка 20% (16:00 - 17:00)", callback_data="timeval_discount")],
            [InlineKeyboardButton("✍️ Указать свое время", callback_data="time_custom")],
            [InlineKeyboardButton("🔙 Назад в корзину", callback_data="cart_list")]
        ])
        caption = "<b>🕒 Выберите время выдачи заказа:\n\nВыдача осуществляется с 10:00 до 16:00.</b>"
        await edit_media_message(user_id, last_msg_id, CART_BANNER, caption, kb, context)

    elif data == "time_postpone":
        await query.answer()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("11:00", callback_data="timeval_11:00"), InlineKeyboardButton("12:00", callback_data="timeval_12:00")],
            [InlineKeyboardButton("13:00", callback_data="timeval_13:00"), InlineKeyboardButton("14:00", callback_data="timeval_14:00")],
            [InlineKeyboardButton("15:00", callback_data="timeval_15:00"), InlineKeyboardButton("16:00", callback_data="timeval_16:00")],
            [InlineKeyboardButton("🔙 Назад", callback_data="select_time")]
        ])
        caption = "<b>🕒 К какому времени собрать ваш заказ?</b>"
        await edit_media_message(user_id, last_msg_id, CART_BANNER, caption, kb, context)

    elif data == "time_custom":
        await query.answer()
        context.user_data['user_state'] = 'WAITING_CUSTOM_TIME'
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="select_time")]])
        caption = "<b>✍️ Пожалуйста, напишите желаемое время выдачи прямо сюда, в чат (например: 14:45):</b>"
        await edit_media_message(user_id, last_msg_id, CART_BANNER, caption, kb, context)

    # ОБРАБОТКА ВЫБРАННОГО ВРЕМЕНИ И СКИДКИ
    elif data.startswith("timeval_"):
        selected_time = data.split("_")[1]
        _, disc, non_disc, _ = get_order_summary(user_id)
        base_total = disc + non_disc
        
        if selected_time == "discount":
            current_hour = (datetime.utcnow().hour + 5) % 24 
            if current_hour != 16:
                await query.answer("⚠️ Скидка 20% действует строго с 16:00 до 17:00!", show_alert=True)
                return
            
            if disc == 0:
                await query.answer("⚠️ Скидка применяется только на комплексные обеды! В корзине их нет.", show_alert=True)
                return
                
            discount_amount = int(disc * 0.2)
            final_total = base_total - discount_amount
            time_str = "16:00 - 17:00 (со скидкой 20% на обеды)"
        else:
            final_total = base_total
            time_str = selected_time

        await query.answer()

        context.user_data['pickup_time'] = time_str
        context.user_data['final_total'] = final_total 
        
        click_url = f"https://my.click.uz/services/pay/?service_id={CLICK_SERVICE_ID}&merchant_id={CLICK_MERCHANT_ID}&amount={final_total}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Оплатить через Click", url=click_url)], 
            [InlineKeyboardButton("✅ Оплата завершена", callback_data="paid_order")],
            [InlineKeyboardButton("🔙 Назад", callback_data="select_time")]
        ])
        
        formatted_total = f"{final_total:,}".replace(",", " ")
        caption = f"<b>🧾 Счет сформирован\n\nСумма к оплате: {formatted_total} сум\nВремя выдачи: {time_str}\n\nПожалуйста, перейдите по ссылке для оплаты.</b>"
        
        try: await context.bot.delete_message(chat_id=user_id, message_id=last_msg_id)
        except: pass
        try:
            if os.path.exists(QR_FILE_NAME):
                with open(QR_FILE_NAME, "rb") as p: msg = await context.bot.send_photo(chat_id=user_id, photo=p, caption=caption, reply_markup=kb, parse_mode='HTML')
            else:
                msg = await context.bot.send_message(chat_id=user_id, text=caption, reply_markup=kb, parse_mode='HTML')
        except Exception: msg = await context.bot.send_message(chat_id=user_id, text=caption, reply_markup=kb, parse_mode='HTML')
        context.user_data['last_msg_id'] = msg.message_id

    elif data == "paid_order":
        await query.answer()
        items_text, disc, non_disc, items_str = get_order_summary(user_id)
        if not items_text: return
        
        base_total = disc + non_disc
        final_total = context.user_data.get('final_total', base_total)
        pickup_time = context.user_data.get('pickup_time', 'В очереди')
        
        if "со скидкой 20%" in pickup_time:
            items_str += " | ПРИМЕНЕНА СКИДКА 20%"
            
        save_order_history(user_id, items_str, final_total)
        clear_cart_db(user_id)
        
        customer_name = query.from_user.first_name
        if query.from_user.last_name: customer_name += f" {query.from_user.last_name}"
        username = f" (@{query.from_user.username})" if query.from_user.username else ""
        
        text = f"<b>✅ Заказ принят в работу!\n\nВаш заказ:\n{items_text}\n\nМесто выдачи: 4 этаж, кухня (Столовая)\nВремя выдачи: {pickup_time}\n\nСпасибо!</b>"
        try: await context.bot.delete_message(chat_id=user_id, message_id=last_msg_id)
        except: pass
        await context.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
        
        if ADMIN_ID:
            user = get_user_db(user_id)
            formatted_total = f"{final_total:,}".replace(",", " ")
            admin_text = f"<b>🚨 Новый заказ!\nИмя: {customer_name}{username}\nТел: {user[1]}\nВремя выдачи: {pickup_time}\nСумма: {formatted_total} сум\n\nСостав:\n{items_text}</b>"
            try: await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode='HTML')
            except: pass

async def post_init(application: Application):
    await application.bot.delete_my_commands()
    commands = [
        BotCommand("start", "Главное меню"),
        BotCommand("admin", "Панель Администратора")
    ]
    await application.bot.set_my_commands(commands)

async def handle_health_check(request): return web.Response(text="Bot OK")

async def main():
    app_bot = Application.builder().token(TOKEN).post_init(post_init).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("admin", admin_command))
    app_bot.add_handler(CommandHandler("myid", myid_command)) 
    app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)) 
    app_bot.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    await app_bot.initialize()
    await app_bot.start()
    await app_bot.updater.start_polling()
    while True: await asyncio.sleep(3600)

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
