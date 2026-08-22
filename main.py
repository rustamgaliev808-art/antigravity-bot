import os
import logging
import asyncio
import sqlite3
import csv
from datetime import datetime
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

DB_NAME = 'delivery_bot_v13.db'
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

    ('mon', '▪️ Жаркое с картофелем (Говядина)', 'Сытное домашнее жаркое с картофелем и витаминным салатом.', 62000, ''),
    ('mon', '▪️ Курица в карри соусе (Курица)', 'Нежная курица в соусе карри. Подается с рисом, пюре и витаминным салатом.', 58000, ''),
    
    ('tue', '▪️ Говядина с овощами (Говядина)', 'Сочная говядина с овощами (на выбор: рис/гречка) и Французским салатом.', 62000, ''),
    ('tue', '▪️ Куриные котлеты (Курица)', 'Домашние куриные котлеты (на выбор: рис/гречка) и Французский салат.', 58000, ''),
    
    ('wed', '▪️ Бефстроганов (Говядина)', 'Бефстроганов (гарнир: пюре/рис/гречка/картофель) и Овощной салат.', 62000, ''),
    ('wed', '▪️ Куриная отбивная (Курица)', 'Отбивная с томатом и сыром (гарнир: пюре/рис/гречка/картофель) и Овощной салат.', 58000, ''),
    
    ('thu', '▪️ Плов из говядины (Говядина)', 'Традиционный плов, подается с салатом Ачик-чучук или соленьями.', 62000, ''),
    ('thu', '▪️ Куриный Ган-пан (Курица)', 'Куриный Ган-пан (на выбор: пюре/перловка) с салатом Ачик-чучук или соленьями.', 58000, ''),
    
    ('fri', '▪️ Гуляш из говядины (Говядина)', 'Сытный гуляш (на выбор: рис/гречка/овощи) и салат Греческий.', 62000, ''),
    ('fri', '▪️ Куриный казан-кебаб (Курица)', 'Куриный казан-кебаб (на выбор: рис/гречка/овощи) и салат Греческий.', 58000, '')
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
    cart = get_cart_db(user_id)
    if not cart: return None, 0, ""
    formatted_lines, short_lines, total = [], [], 0
    for item_id, data in cart.items():
        name, unit_price, cnt = data['name'], data['price'], data['count']
        total_price = unit_price * cnt
        formatted_lines.append(f"• {name} x{cnt} — {total_price:,} сум".replace(",", " "))
        short_lines.append(f"{name} x{cnt}")
        total += total_price
    return "\n".join(formatted_lines), total, ", ".join(short_lines)

# ==================== КЛАВИАТУРЫ ====================
def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Завтраки", callback_data="cat_breakfasts")],
        [InlineKeyboardButton("Комплексный обед дня", callback_data="lunch_today")],
        [InlineKeyboardButton("Напитки", callback_data="nav_drinks")],
        [InlineKeyboardButton("Недельное меню (предзаказ)", callback_data="nav_week")],
        [InlineKeyboardButton("Корзина", callback_data="cart_list")]
    ])

def get_drinks_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Горячие напитки", callback_data="cat_hot_drinks")],
        [InlineKeyboardButton("Холодные напитки", callback_data="cat_cold_drinks")],
        [InlineKeyboardButton("Фреши", callback_data="cat_fresh_drinks")],
        [InlineKeyboardButton("Назад", callback_data="home")]
    ])

def get_week_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Пн", callback_data="cat_mon"), InlineKeyboardButton("Вт", callback_data="cat_tue"), InlineKeyboardButton("Ср", callback_data="cat_wed")],
        [InlineKeyboardButton("Чт", callback_data="cat_thu"), InlineKeyboardButton("Пт", callback_data="cat_fri")],
        [InlineKeyboardButton("Назад", callback_data="home")]
    ])

def get_category_list_keyboard(user_id, cat_id, items):
    keyboard = []
    cart = get_cart_db(user_id)
    
    for item in items:
        item_id = str(item['id'])
        display_name = item['name']
        is_complex = cat_id in ['mon', 'tue', 'wed', 'thu', 'fri']
        
        keyboard.append([InlineKeyboardButton(display_name, callback_data="ignore")])
        
        if is_complex:
            count_ice = cart.get(f"{item_id}_icetea", {}).get('count', 0)
            count_sherbet = cart.get(f"{item_id}_sherbet", {}).get('count', 0)
            total_count = count_ice + count_sherbet
            
            if total_count == 0:
                keyboard.append([InlineKeyboardButton("🛒 Выбрать напиток", callback_data=f"drinksel_{item_id}")])
            else:
                keyboard.append([InlineKeyboardButton(f"🛒 В корзине: {total_count} шт (Изменить)", callback_data=f"drinksel_{item_id}")])
        else:
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
        
    keyboard.append([InlineKeyboardButton("Корзина", callback_data="cart_list"), InlineKeyboardButton("Назад", callback_data=back_data)])
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
    caption = "<b>Главное меню</b>\n\nВыберите нужный раздел для заказа."
    try: await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data.get('last_msg_id'))
    except Exception: pass
    
    try:
        msg = await context.bot.send_photo(chat_id=chat_id, photo=MAIN_BANNER, caption=caption, reply_markup=get_main_keyboard(), parse_mode='HTML')
    except Exception:
        msg = await context.bot.send_message(chat_id=chat_id, text=caption, reply_markup=get_main_keyboard(), parse_mode='HTML')
    context.user_data['last_msg_id'] = msg.message_id


# ==================== БАЗОВЫЕ ХЕНДЛЕРЫ ====================
# ВАЖНО: ВОТ ЭТО ФУНКЦИЯ КОТОРАЯ ТЕРЯЛАСЬ!
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_db()
    if not get_user_db(user_id):
        keyboard = [[KeyboardButton("Поделиться номером", request_contact=True)]]
        await context.bot.send_message(chat_id=user_id, text="Для начала работы, пожалуйста, поделитесь номером телефона.", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True))
    else:
        await render_start(user_id, context)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    contact = update.message.contact
    if contact:
        add_user_db(user_id, contact.phone_number)
        await update.message.reply_text("Номер сохранен.", reply_markup=ReplyKeyboardRemove())
        await render_start(user_id, context)

# ==================== КОМАНДЫ АДМИНА ====================
async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = f"Ваш Telegram ID:\n<code>{user_id}</code>\n\nСкопируйте его и вставьте в переменную ADMIN_ID в Railway."
    await update.message.reply_text(text, parse_mode='HTML')

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not ADMIN_ID or user_id != ADMIN_ID: 
        await update.message.reply_text("У вас нет прав администратора.")
        return
    
    keyboard = [
        [InlineKeyboardButton("Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("Добавить блюдо", callback_data="admin_add_dish"), InlineKeyboardButton("Удалить блюдо", callback_data="admin_del_dish")],
        [InlineKeyboardButton("Скачать отчет (Excel)", callback_data="admin_export_excel")],
        [InlineKeyboardButton("Открыть/Закрыть заказы", callback_data="admin_toggle")]
    ]
    await update.message.reply_text("<b>Панель администратора</b>\nУправление меню и отчетами.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def post_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not ADMIN_ID or user_id != ADMIN_ID:
        return

    weekday = datetime.now().weekday()
    posts_by_day = {
        0: ("<b>Понедельник — продуктивное начало!</b>\n\nСегодня в комплексе: <b>Салат витаминный</b>.\n\n<b>Горячее и напиток на выбор:</b>\n• Жаркое с картофелем (Айс-ти или Шербет) — <i>62 000 сум</i>\n• Курица в карри соусе с рисом и пюре (Айс-ти или Шербет) — <i>58 000 сум</i>", MONDAY_BANNER),
        1: ("<b>Вторник — время вкусного обеда!</b>\n\nСегодня в комплексе: <b>Салат Французский</b>.\n\n<b>Горячее и напиток на выбор:</b>\n• Говядина с овощами (Айс-ти или Шербет) — <i>62 000 сум</i>\n• Куриные котлеты (Айс-ти или Шербет) — <i>58 000 сум</i>", LUNCH_BANNER),
        2: ("<b>Среда — экватор недели!</b>\n\nСегодня в комплексе: <b>Овощной салат</b>.\n\n<b>Горячее и напиток на выбор:</b>\n• Бефстроганов (Айс-ти или Шербет) — <i>62 000 сум</i>\n• Куриная отбивная (Айс-ти или Шербет) — <i>58 000 сум</i>", LUNCH_BANNER),
        3: ("<b>Четверг — день Плова!</b>\n\nСегодня в комплексе: <b>Салат Ачик-чучук или соленья</b>.\n\n<b>Горячее и напиток на выбор:</b>\n• Плов из говядины (Айс-ти или Шербет) — <i>62 000 сум</i>\n• Куриный Ган-пан (Айс-ти или Шербет) — <i>58 000 сум</i>", LUNCH_BANNER),
        4: ("<b>Пятница — завершаем неделю вкусно!</b>\n\nСегодня в комплексе: <b>Салат Греческий</b>.\n\n<b>Горячее и напиток на выбор:</b>\n• Гуляш из говядины (Айс-ти или Шербет) — <i>62 000 сум</i>\n• Куриный казан-кебаб (Айс-ти или Шербет) — <i>58 000 сум</i>", LUNCH_BANNER)
    }

    if weekday not in posts_by_day:
        await update.message.reply_text("Сегодня выходной! Готовых текстов для выходных нет.")
        return

    text, photo = posts_by_day[weekday]
    bot_info = await context.bot.get_me()
    bot_url = f"https://t.me/{bot_info.username}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Заказать обед", url=bot_url)]])

    try:
        await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=text, reply_markup=keyboard, parse_mode='HTML')
        await update.message.reply_text(f"Пост успешно отправлен в канал {CHANNEL_ID}.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка отправки: {e}")

# ==================== ОБРАБОТКА ДЕЙСТВИЙ АДМИНА ====================
async def run_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_user_ids()
    count = 0
    msg = await update.message.reply_text("Рассылка начата...")
    for uid in users:
        try:
            await context.bot.copy_message(chat_id=uid, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
            count += 1
            await asyncio.sleep(0.05)
        except Exception: pass
    context.user_data['admin_state'] = None
    await msg.edit_text(f"Рассылка завершена. Успешно отправлено: {count} пользователям.")

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    state = context.user_data.get('admin_state')
    
    if text.lower() == 'отмена':
        context.user_data['admin_state'] = None
        await update.message.reply_text("Действие отменено.")
        return True
        
    if state == 'WAITING_BROADCAST':
        await run_broadcast(update, context)
        return True
    elif state == 'WAITING_DISH_NAME':
        context.user_data['new_dish']['name'] = text
        context.user_data['admin_state'] = 'WAITING_DISH_DESC'
        await update.message.reply_text("Введите описание блюда:")
        return True
    elif state == 'WAITING_DISH_DESC':
        context.user_data['new_dish']['desc'] = text
        context.user_data['admin_state'] = 'WAITING_DISH_PRICE'
        await update.message.reply_text("Введите цену (только цифры):")
        return True
    elif state == 'WAITING_DISH_PRICE':
        if not text.isdigit():
            await update.message.reply_text("Ошибка! Введите только цифры.")
            return True
        context.user_data['new_dish']['price'] = int(text)
        context.user_data['admin_state'] = 'WAITING_DISH_PHOTO'
        await update.message.reply_text("Отправьте ссылку на фото блюда или саму картинку:")
        return True
    elif state == 'WAITING_DISH_PHOTO':
        context.user_data['new_dish']['photo'] = text 
        save_new_dish(context.user_data['new_dish'])
        context.user_data['admin_state'] = None
        await update.message.reply_text("Блюдо добавлено в меню.")
        return True
    return False

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
            await update.message.reply_text("Блюдо добавлено в меню.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_ID and user_id == ADMIN_ID:
        if await handle_admin_text(update, context):
            return

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

    # ВЫБОР НАПИТКА ДЛЯ КОМПЛЕКСА (POP-UP)
    if data.startswith("drinksel_"):
        item_id = data.split("_")[1]
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT name, cat_id, banner FROM menu_items m JOIN menu_categories c ON m.cat_id = c.id WHERE m.id = ?", (item_id,))
        row = cursor.fetchone()
        conn.close()
        if not row: return
        item_name, cat_id, banner = row[0], row[1], row[2]

        cart = get_cart_db(user_id)
        count_ice = cart.get(f"{item_id}_icetea", {}).get('count', 0)
        count_sherbet = cart.get(f"{item_id}_sherbet", {}).get('count', 0)

        kb = [
            [InlineKeyboardButton("С напитком: Айс-ти", callback_data="ignore")],
            [
                InlineKeyboardButton("➖", callback_data=f"rmcombo_{item_id}_icetea"),
                InlineKeyboardButton(f"{count_ice} шт", callback_data="ignore"),
                InlineKeyboardButton("➕", callback_data=f"addcombo_{item_id}_icetea")
            ],
            [InlineKeyboardButton("С напитком: Шербет", callback_data="ignore")],
            [
                InlineKeyboardButton("➖", callback_data=f"rmcombo_{item_id}_sherbet"),
                InlineKeyboardButton(f"{count_sherbet} шт", callback_data="ignore"),
                InlineKeyboardButton("➕", callback_data=f"addcombo_{item_id}_sherbet")
            ],
            [InlineKeyboardButton("Готово (Назад)", callback_data=f"cat_{cat_id}")]
        ]
        caption = f"<b>{item_name}</b>\n\nПожалуйста, выберите количество порций с нужным напитком:"
        await edit_media_message(user_id, last_msg_id, banner, caption, InlineKeyboardMarkup(kb), context)
        await query.answer()
        return

    elif data.startswith("addcombo_") or data.startswith("rmcombo_"):
        parts = data.split("_")
        action = parts[0]
        item_id = parts[1]
        drink_type = parts[2]
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT name, price, cat_id, banner FROM menu_items m JOIN menu_categories c ON m.cat_id = c.id WHERE m.id = ?", (item_id,))
        row = cursor.fetchone()
        conn.close()
        if not row: return
        base_name, base_price, cat_id, banner = row[0], row[1], row[2], row[3]

        cart_item_id = f"{item_id}_{drink_type}"
        drink_display = "Айс-ти" if drink_type == "icetea" else "Шербет"
        clean_name = base_name.replace("▪️ ", "")
        cart_item_name = f"{clean_name} (+ {drink_display})"

        cart = get_cart_db(user_id)
        current_count = cart.get(cart_item_id, {}).get('count', 0)

        if action == "addcombo":
            new_count = current_count + 1
            update_cart_db(user_id, cart_item_id, cart_item_name, base_price, new_count)
        else:
            if current_count > 0:
                new_count = current_count - 1
                update_cart_db(user_id, cart_item_id, cart_item_name, base_price, new_count)

        cart = get_cart_db(user_id)
        count_ice = cart.get(f"{item_id}_icetea", {}).get('count', 0)
        count_sherbet = cart.get(f"{item_id}_sherbet", {}).get('count', 0)

        kb = [
            [InlineKeyboardButton("С напитком: Айс-ти", callback_data="ignore")],
            [
                InlineKeyboardButton("➖", callback_data=f"rmcombo_{item_id}_icetea"),
                InlineKeyboardButton(f"{count_ice} шт", callback_data="ignore"),
                InlineKeyboardButton("➕", callback_data=f"addcombo_{item_id}_icetea")
            ],
            [InlineKeyboardButton("С напитком: Шербет", callback_data="ignore")],
            [
                InlineKeyboardButton("➖", callback_data=f"rmcombo_{item_id}_sherbet"),
                InlineKeyboardButton(f"{count_sherbet} шт", callback_data="ignore"),
                InlineKeyboardButton("➕", callback_data=f"addcombo_{item_id}_sherbet")
            ],
            [InlineKeyboardButton("Готово (Назад)", callback_data=f"cat_{cat_id}")]
        ]
        
        try:
            await context.bot.edit_message_reply_markup(chat_id=user_id, message_id=last_msg_id, reply_markup=InlineKeyboardMarkup(kb))
        except Exception: pass
        await query.answer()
        return

    # ВЕТКА АДМИНА
    if data.startswith("admin_"):
        if not ADMIN_ID or user_id != ADMIN_ID: return
        
        if data == "admin_toggle":
            global menu_active
            menu_active = not menu_active
            status = "ОТКРЫТ" if menu_active else "ЗАКРЫТ"
            await query.answer(f"Прием заказов: {status}", show_alert=True)
            
        elif data == "admin_broadcast":
            context.user_data['admin_state'] = 'WAITING_BROADCAST'
            await query.message.reply_text("Отправьте сообщение для рассылки (текст или картинка). Для отмены напишите 'отмена'.")

        elif data == "admin_add_dish":
            cats = get_categories()
            kb = [[InlineKeyboardButton(c['name'], callback_data=f"admin_addcat_{c['id']}")] for c in cats]
            await query.message.reply_text("Выберите категорию:", reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("admin_addcat_"):
            cat_id = data.split("_")[2]
            context.user_data['admin_state'] = 'WAITING_DISH_NAME'
            context.user_data['new_dish'] = {'cat_id': cat_id}
            await query.message.reply_text("Введите название блюда:")

        elif data == "admin_del_dish":
            cats = get_categories()
            kb = [[InlineKeyboardButton(c['name'], callback_data=f"admin_delcat_{c['id']}")] for c in cats]
            await query.message.reply_text("Выберите категорию для удаления блюда:", reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("admin_delcat_"):
            cat_id = data.split("_")[2]
            items = get_items_by_cat(cat_id)
            if not items:
                await query.message.reply_text("Категория пуста.")
                return
            kb = [[InlineKeyboardButton(i['name'], callback_data=f"admin_delitem_{i['id']}")] for i in items]
            await query.message.reply_text("Выберите блюдо для удаления:", reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("admin_delitem_"):
            item_id = data.split("_")[2]
            delete_item(item_id)
            await query.message.reply_text("Блюдо удалено.")

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
                    order_id = row[0]
                    date_str = row[1]
                    raw_phone = str(row[2])
                    if not raw_phone.startswith('+'):
                        raw_phone = '+' + raw_phone
                    phone_excel = f'="{raw_phone}"' 
                    items_str = str(row[3]).replace("\n", "   |   ")
                    total = row[4]
                    writer.writerow([order_id, date_str, phone_excel, items_str, total])
                    
            with open(filename, 'rb') as doc:
                caption_text = (
                    "<b>Отчет готов.</b>\n"
                    "Для автовыравнивания в Excel нажмите Ctrl+A, затем дважды кликните по границе любой колонки сверху."
                )
                await context.bot.send_document(chat_id=user_id, document=doc, caption=caption_text, parse_mode='HTML')
            
            os.remove(filename)
            await query.answer("Отчет отправлен.")

        await query.answer()
        return

    # НАВИГАЦИЯ
    if data == "home":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "<b>Главное меню</b>\n\nВыберите нужный раздел для заказа.", get_main_keyboard(), context)

    elif data == "nav_drinks":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?q=80&w=1200&auto=format&fit=crop", "<b>Напитки</b>\nВыберите категорию:", get_drinks_keyboard(), context)

    elif data == "nav_week":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "<b>Недельное меню</b>\nВыберите день для предзаказа:", get_week_menu_keyboard(), context)

    elif data == "lunch_today":
        weekday = datetime.now().weekday()
        days_map = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri'}
        if weekday in days_map:
            cat_id = days_map[weekday]
            data = f"cat_{cat_id}" 
        else:
            await query.answer("Сегодня выходной. Выберите день через 'Недельное меню'.", show_alert=True)
            return

    # ПРОСМОТР КАТЕГОРИЙ 
    if data.startswith("cat_"):
        await query.answer()
        cat_id = data[4:] 
        
        items = get_items_by_cat(cat_id)
        cat_info = get_category_info(cat_id)
        if not items or not cat_info: return
        
        caption = f"<b>{cat_info['name']}</b>\n\n"
        for item in items:
            price_str = f" — {item['price']:,} сум".replace(",", " ") if item['price'] > 0 else ""
            caption += f"<b>{item['name']}</b>{price_str}\n<i>{item['description']}</i>\n\n"

        await edit_media_message(user_id, last_msg_id, cat_info['banner'], caption, get_category_list_keyboard(user_id, cat_id, items), context)

    # ДОБАВЛЕНИЕ И УДАЛЕНИЕ ИЗ СПИСКА (ОБЫЧНЫЕ ТОВАРЫ)
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
        items_text, total, _ = get_order_summary(user_id)
        if not items_text:
            await edit_media_message(user_id, last_msg_id, CART_BANNER, "<b>Корзина пуста.</b>", get_main_keyboard(), context)
            return
            
        caption = f"<b>Ваш заказ:</b>\n\n{items_text}\n\n<b>Итого:</b> {total:,} сум\n\nПерейти к оформлению?".replace(",", " ")
        kb = [[InlineKeyboardButton("Оформить заказ", callback_data="select_time")], [InlineKeyboardButton("Очистить корзину", callback_data="cancel_order"), InlineKeyboardButton("В меню", callback_data="home")]]
        await edit_media_message(user_id, last_msg_id, CART_BANNER, caption, InlineKeyboardMarkup(kb), context)

    elif data == "cancel_order":
        await query.answer("Корзина очищена")
        clear_cart_db(user_id)
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "Корзина очищена.", get_main_keyboard(), context)

    elif data == "select_time":
        await query.answer()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("12:00", callback_data="time_12:00"), InlineKeyboardButton("12:30", callback_data="time_12:30")],
            [InlineKeyboardButton("13:00", callback_data="time_13:00"), InlineKeyboardButton("13:30", callback_data="time_13:30")],
            [InlineKeyboardButton("Как будет готово", callback_data="time_ASAP")],
            [InlineKeyboardButton("Назад в корзину", callback_data="cart_list")]
        ])
        await edit_media_message(user_id, last_msg_id, CART_BANNER, "<b>Выберите время выдачи:</b>\nМы заранее соберем заказ в контейнеры.", kb, context)

    elif data.startswith("time_"):
        await query.answer()
        selected_time = data.split("_")[1]
        if selected_time == "ASAP":
            selected_time = "Как можно скорее"
        
        context.user_data['pickup_time'] = selected_time
        _, total, _ = get_order_summary(user_id)
        
        click_url = f"https://my.click.uz/services/pay/?service_id={CLICK_SERVICE_ID}&merchant_id={CLICK_MERCHANT_ID}&amount={total}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Оплатить через Click", url=click_url)], [InlineKeyboardButton("Оплата завершена", callback_data="paid_order")]])
        formatted_total = f"{total:,}".replace(",", " ")
        caption = f"<b>Счет сформирован</b>\nСумма: {formatted_total} сум\nВремя выдачи: {selected_time}\n\nПожалуйста, перейдите по ссылке для оплаты."
        
        try: await context.bot.delete_message(chat_id=user_id, message_id=last_msg_id)
        except: pass
        try:
            if os.path.exists(QR_FILE_NAME):
                with open(QR_FILE_NAME, "rb") as p: msg = await context.bot.send_photo(chat_id=user_id, photo=p, caption=caption, reply_markup=kb, parse_mode='HTML')
            else:
                msg = await context.bot.send_message(chat_id=user_id, text=caption, reply_markup=kb, parse_mode='HTML')
        except Exception:
            msg = await context.bot.send_message(chat_id=user_id, text=caption, reply_markup=kb, parse_mode='HTML')
        context.user_data['last_msg_id'] = msg.message_id

    elif data == "paid_order":
        await query.answer()
        items_text, total, items_str = get_order_summary(user_id)
        if not items_text: return
        
        save_order_history(user_id, items_str, total)
        clear_cart_db(user_id)
        
        pickup_time = context.user_data.get('pickup_time', 'В порядке очереди')
        customer_name = query.from_user.first_name
        if query.from_user.last_name: customer_name += f" {query.from_user.last_name}"
        username = f" (@{query.from_user.username})" if query.from_user.username else ""
        
        text = f"<b>Заказ принят в работу!</b>\n\n<b>Состав:</b>\n{items_text}\n\nМесто выдачи: 4 этаж\nВремя: {pickup_time}\n\nСпасибо за заказ."
        try: await context.bot.delete_message(chat_id=user_id, message_id=last_msg_id)
        except: pass
        await context.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
        
        if ADMIN_ID:
            user = get_user_db(user_id)
            formatted_total = f"{total:,}".replace(",", " ")
            admin_text = f"🚨 <b>Новый заказ!</b>\nИмя: {customer_name}{username}\nТел: {user[1]}\nВремя выдачи: {pickup_time}\nСумма: {formatted_total} сум\n\n<b>Состав:</b>\n{items_text}"
            try: await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode='HTML')
            except: pass

async def post_init(application: Application):
    await application.bot.delete_my_commands()
    commands = [
        BotCommand("start", "Главное меню"),
        BotCommand("admin", "Панель Администратора"),
        BotCommand("post", "Опубликовать меню в канал")
    ]
    await application.bot.set_my_commands(commands)

async def handle_health_check(request): return web.Response(text="Bot OK")

async def main():
    app_bot = Application.builder().token(TOKEN).post_init(post_init).build()
    
    # ВОТ ОНА! ФУНКЦИЯ КОТОРАЯ ТЕРЯЛАСЬ! ТЕПЕРЬ ОНА ТОЧНО ЗДЕСЬ!
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("post", post_to_channel))
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
