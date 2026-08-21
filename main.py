import os
import logging
import asyncio
import sqlite3
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
ADMIN_ID_STR = os.getenv("ADMIN_ID", "ВАШ_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel")

CLICK_PASS_ID = "052528"
QR_FILE_NAME = "qr.jpg"

# Надежные ссылки на картинки
MAIN_BANNER = "https://picsum.photos/1200/800?random=10"
CART_BANNER = "https://picsum.photos/1200/800?random=11"
LUNCH_BANNER = "https://picsum.photos/1200/800?random=12"
SUBS_BANNER = "https://picsum.photos/1200/800?random=13"

try:
    ADMIN_ID = int(ADMIN_ID_STR) if ADMIN_ID_STR.isdigit() else None
except (ValueError, TypeError):
    ADMIN_ID = None

DB_NAME = 'delivery_bot_v8.db'
menu_active = True

# ==================== ДАННЫЕ МЕНЮ ====================
DEFAULT_CATEGORIES = [
    ('breakfasts', '🍳 Завтраки', 'https://picsum.photos/1200/800?random=20'),
    ('hot_drinks', '🔥 Горячие напитки', 'https://picsum.photos/1200/800?random=21'),
    ('cold_drinks', '🧊 Холодные напитки', 'https://picsum.photos/1200/800?random=22'),
    ('fresh_drinks', '🍹 Фреши', 'https://picsum.photos/1200/800?random=23'),
    ('subs', '💳 Подписки', SUBS_BANNER),
    ('mon', 'Понедельник', MAIN_BANNER), 
    ('tue', 'Вторник', MAIN_BANNER), 
    ('wed', 'Среда', MAIN_BANNER),
    ('thu', 'Четверг', MAIN_BANNER), 
    ('fri', 'Пятница', MAIN_BANNER)
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
    ('cold_drinks', 'Мохито (Клас. / Клубничный)', 'Охлаждающий напиток.', 20000, ''),
    ('cold_drinks', 'Chortoq 0.25 (с газом)', 'Минеральная газированная вода.', 12000, ''),
    
    ('fresh_drinks', 'Яблочный фреш', 'Свежевыжатый сок из зеленых яблок (250 мл).', 30000, ''),
    ('fresh_drinks', 'Фреш Морковь-Яблоко', 'Витаминный заряд (250 мл).', 30000, ''),
    ('fresh_drinks', 'Фреш Детокс', 'Свекла, яблоко, морковь (250 мл).', 32000, ''),

    ('subs', 'Подписка: 1 нед (Курица)', 'Комплексные обеды с курицей на 5 рабочих дней.', 290000, ''),
    ('subs', 'Подписка: 1 нед (Говядина)', 'Комплексные обеды с говядиной на 5 рабочих дней.', 310000, ''),
    ('subs', 'Подписка: 4 нед (Курица)', 'Обеды с курицей на месяц (20 дней). Выгода 10%!', 1044000, ''),
    ('subs', 'Подписка: 4 нед (Говядина)', 'Обеды с говядиной на месяц (20 дней). Выгода 10%!', 1116000, ''),

    ('mon', 'Пн. Комплекс (Говядина)', 'Тефтели с гречкой + Салат Винегрет + Компот', 62000, ''),
    ('mon', 'Пн. Комплекс (Курица)', 'Курица в сливочном соусе с рисом + Салат Винегрет + Компот', 58000, ''),
    
    ('tue', 'Вт. Комплекс (Говядина)', 'Тушеная говядина с картофелем + Овощной салат + Компот', 62000, ''),
    ('tue', 'Вт. Комплекс (Курица)', 'Запеченная курица с сыром и помидорами с пюре + Овощной салат + Компот', 58000, ''),
    
    ('wed', 'Ср. Комплекс (Говядина)', 'Бефстроганов (с пюре/рисом) + Салат Греческий + Компот', 62000, ''),
    ('wed', 'Ср. Комплекс (Курица)', 'Куриный казан-кабоб + Салат Греческий + Компот', 58000, ''),
    
    ('thu', 'Чт. Комплекс (Говядина)', 'Плов из говядины + Салат Ачик-чучук + Компот', 62000, ''),
    ('thu', 'Чт. Комплекс (Курица)', 'Курица с овощами с пюре + Салат Ачик-чучук + Компот', 58000, ''),
    
    ('fri', 'Пт. Комплекс (Говядина)', 'Гуляш из говядины (с рисом/гречкой) + Салат Цезарь + Компот', 62000, ''),
    ('fri', 'Пт. Комплекс (Курица)', 'Запеченные куриные бедра (с рисом/гречкой) + Салат Цезарь + Компот', 58000, '')
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
        [InlineKeyboardButton("🍳 Завтраки", callback_data="cat_breakfasts")],
        [InlineKeyboardButton("🍱 Комплексный обед дня", callback_data="lunch_today")],
        [InlineKeyboardButton("🥤 Напитки", callback_data="nav_drinks")],
        [InlineKeyboardButton("🗓 Недельное меню (предзаказ)", callback_data="nav_week")],
        [InlineKeyboardButton("💳 Подписки на обеды", callback_data="cat_subs")],
        [InlineKeyboardButton("🛍 Корзина", callback_data="cart_list"), InlineKeyboardButton("📜 История", callback_data="history_list")]
    ])

def get_drinks_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Горячие напитки", callback_data="cat_hot_drinks")],
        [InlineKeyboardButton("🧊 Холодные напитки", callback_data="cat_cold_drinks")],
        [InlineKeyboardButton("🍹 Фреши", callback_data="cat_fresh_drinks")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="home")]
    ])

def get_week_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Пн", callback_data="cat_mon"), InlineKeyboardButton("Вт", callback_data="cat_tue"), InlineKeyboardButton("Ср", callback_data="cat_wed")],
        [InlineKeyboardButton("Чт", callback_data="cat_thu"), InlineKeyboardButton("Пт", callback_data="cat_fri")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="home")]
    ])

def get_category_list_keyboard(user_id, cat_id, items):
    keyboard = []
    cart = get_cart_db(user_id)
    
    for item in items:
        item_id = item['id']
        count = cart.get(item_id, {}).get('count', 0)
        
        display_name = item['name']
        if len(display_name) > 16:
            display_name = display_name[:14] + ".."
            
        middle_text = f"{display_name} : {count} шт"
        
        keyboard.append([
            InlineKeyboardButton("➖", callback_data=f"list_rm_{cat_id}_{item_id}"),
            InlineKeyboardButton(middle_text, callback_data="ignore"),
            InlineKeyboardButton("➕", callback_data=f"list_add_{cat_id}_{item_id}")
        ])

    back_data = "home"
    if cat_id in ['hot_drinks', 'cold_drinks', 'fresh_drinks']: back_data = "nav_drinks"
    elif cat_id in ['mon', 'tue', 'wed', 'thu', 'fri']: back_data = "nav_week"
        
    keyboard.append([InlineKeyboardButton("🛍 В корзину", callback_data="cart_list"), InlineKeyboardButton("🔙 Назад", callback_data=back_data)])
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
    caption = "🏠 <b>Главное меню 👇</b>\n\n🍽 Выберите нужный раздел для заказа."
    try: await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data.get('last_msg_id'))
    except Exception: pass
    
    try:
        msg = await context.bot.send_photo(chat_id=chat_id, photo=MAIN_BANNER, caption=caption, reply_markup=get_main_keyboard(), parse_mode='HTML')
    except Exception:
        msg = await context.bot.send_message(chat_id=chat_id, text=caption, reply_markup=get_main_keyboard(), parse_mode='HTML')
    context.user_data['last_msg_id'] = msg.message_id

# ==================== ХЕНДЛЕРЫ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_db()
    if not get_user_db(user_id):
        keyboard = [[KeyboardButton("📱 Поделиться номером", request_contact=True)]]
        await context.bot.send_message(chat_id=user_id, text="🏠 Чтобы начать, поделитесь номером телефона 👇", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True))
    else:
        await render_start(user_id, context)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    contact = update.message.contact
    if contact:
        add_user_db(user_id, contact.phone_number)
        await update.message.reply_text("✅ Номер сохранён.", reply_markup=ReplyKeyboardRemove())
        await render_start(user_id, context)

async def post_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not ADMIN_ID or user_id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет прав администратора.")
        return

    weekday = datetime.now().weekday()
    
    posts_by_day = {
        0: ("<b>Начинаем неделю вкусно и продуктивно! ☀️</b>\n\nСегодня на обед мы приготовили для вас домашние комплексы. В каждый сет по умолчанию входит салат <b>Винегрет</b> и освежающий компот! 🍹\n\n<b>На выбор:</b>\n🥩 Сочные тефтели из говядины с рассыпчатой гречкой — <i>62 000 сум</i>\n🍗 Нежная курица в сливочном соусе с рисом — <i>58 000 сум</i>\n\nУспейте сделать заказ до 11:00!", LUNCH_BANNER),
        1: ("<b>Время сытного обеда! Что у нас сегодня? 😋</b>\n\nНаши комплексные обеды уже ждут вас. Напоминаем: компот и свежий овощной салат уже включены в стоимость! 🥗🥤\n\n<b>На выбор:</b>\n🥩 Тушеная говядина с тающим во рту картофелем — <i>62 000 сум</i>\n🍗 Куриное филе под сырно-томатной корочкой с воздушным пюре — <i>58 000 сум</i>\n\nЗарядитесь энергией на вторую половину дня!", LUNCH_BANNER),
        2: ("<b>Экватор рабочей недели! Порадуйте себя вкусным обедом 🍽</b>\n\nСегодня в нашем меню настоящие хиты! В качестве легкого старта в каждом комплексе вас ждет <b>Греческий салат</b> и прохладный компот. 🍅🥒\n\n<b>Горячее на выбор:</b>\n🥩 Классический Бефстроганов (пюре/рис) — <i>62 000 сум</i>\n🍗 Ароматный куриный казан-кабоб — <i>58 000 сум</i>\n\nВыбирайте то, что нравится больше!", LUNCH_BANNER),
        3: ("<b>Четверг — день Плова! 🍚🔥</b>\n\nКакая же неделя без традиционного плова? Сегодня мы подаем его с классическим салатом <b>Ачик-чучук</b> (или соленьями) и компотом.\n\n<b>Наши комплексы на сегодня:</b>\n🥩 Традиционный плов из говядины — <i>62 000 сум</i>\n🍗 Сочная курица с овощами и домашним пюре — <i>58 000 сум</i>\n\nПорции разлетаются быстро!", LUNCH_BANNER),
        4: ("<b>Пятница! Вкусно завершаем рабочую неделю 🎉</b>\n\nСегодня к горячему мы подаем всеми любимый салат <b>Цезарь</b> и наш фирменный компот! 🥬🍹\n\n<b>Выбирайте свой комплекс:</b>\n🥩 Сытный гуляш из говядины (рис/гречка) — <i>62 000 сум</i>\n🍗 Румяные запеченные куриные бедра (рис/гречка) — <i>58 000 сум</i>\n\nСпасибо, что обедали с нами всю неделю!", LUNCH_BANNER)
    }

    if weekday not in posts_by_day:
        await update.message.reply_text("Сегодня выходной! Готовых текстов для выходных нет.")
        return

    text, photo = posts_by_day[weekday]
    bot_info = await context.bot.get_me()
    bot_url = f"https://t.me/{bot_info.username}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🥗 Заказать обед в 2 клика", url=bot_url)]])

    try:
        await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=text, reply_markup=keyboard, parse_mode='HTML')
        await update.message.reply_text(f"✅ Успешно! Пост на сегодняшний день отправлен в канал {CHANNEL_ID}.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка отправки: {e}\nУбедитесь, что бот является Администратором в канале {CHANNEL_ID}!")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not ADMIN_ID or user_id != ADMIN_ID: return
    
    keyboard = [
        [InlineKeyboardButton("⛔ Открыть/Закрыть прием заказов", callback_data="admin_toggle")]
    ]
    await update.message.reply_text("👑 <b>Панель администратора</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# ----------------------------------------------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    init_db()
    last_msg_id = context.user_data.get('last_msg_id')

    if data == "ignore":
        await query.answer()
        return

    if data == "admin_toggle":
        if not ADMIN_ID or user_id != ADMIN_ID: return
        global menu_active
        menu_active = not menu_active
        status = "ОТКРЫТ ✅" if menu_active else "ЗАКРЫТ ⛔"
        await query.answer(f"Прием заказов: {status}", show_alert=True)
        return

    # НАВИГАЦИЯ
    if data == "home":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "🏠 <b>Главное меню 👇</b>", get_main_keyboard(), context)

    elif data == "nav_drinks":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, "https://picsum.photos/1200/800?random=30", "<b>🥤 Выберите категорию напитков:</b>", get_drinks_keyboard(), context)

    elif data == "nav_week":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "<b>🗓 Выберите день для предзаказа обеда:</b>", get_week_menu_keyboard(), context)

    # УМНЫЙ ОБЕД ДНЯ
    elif data == "lunch_today":
        weekday = datetime.now().weekday()
        days_map = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri'}
        
        if weekday in days_map:
            cat_id = days_map[weekday]
            data = f"cat_{cat_id}" 
        else:
            await query.answer("Сегодня выходной! 😴\nВы можете сделать предзаказ через 'Недельное меню'.", show_alert=True)
            return

    # ПРОСМОТР КАТЕГОРИЙ 
    if data.startswith("cat_"):
        await query.answer()
        cat_id = data[4:] 
        
        items = get_items_by_cat(cat_id)
        cat_info = get_category_info(cat_id)
        if not items or not cat_info: return
        
        caption = f"📋 <b>{cat_info['name']}</b>\n\n"
        for item in items:
            price_str = f" — {item['price']:,} сум".replace(",", " ") if item['price'] > 0 else ""
            caption += f"▪️ <b>{item['name']}</b>{price_str}\n<i>{item['description']}</i>\n\n"

        await edit_media_message(user_id, last_msg_id, cat_info['banner'], caption, get_category_list_keyboard(user_id, cat_id, items), context)

    # ДОБАВЛЕНИЕ И УДАЛЕНИЕ ИЗ СПИСКА
    elif data.startswith("list_add_"):
        parts = data.split("_")
        item_id = parts[-1]
        cat_id = "_".join(parts[2:-1])
        
        items = get_items_by_cat(cat_id)
        item = next((i for i in items if i['id'] == item_id), None)
        if not item: return
        
        new_count = get_cart_db(user_id).get(item_id, {}).get('count', 0) + 1
        update_cart_db(user_id, item_id, item['name'], item['price'], new_count)
        await query.answer(f"Добавлено: {item['name']}")
        
        await context.bot.edit_message_reply_markup(chat_id=user_id, message_id=last_msg_id, reply_markup=get_category_list_keyboard(user_id, cat_id, items))

    elif data.startswith("list_rm_"):
        parts = data.split("_")
        item_id = parts[-1]
        cat_id = "_".join(parts[2:-1])
        
        items = get_items_by_cat(cat_id)
        item = next((i for i in items if i['id'] == item_id), None)
        if not item: return
        
        current_count = get_cart_db(user_id).get(item_id, {}).get('count', 0)
        
        if current_count > 0:
            new_count = current_count - 1
            update_cart_db(user_id, item_id, item['name'], item['price'], new_count)
            await query.answer("Удалено")
            await context.bot.edit_message_reply_markup(chat_id=user_id, message_id=last_msg_id, reply_markup=get_category_list_keyboard(user_id, cat_id, items))
        else:
            await query.answer("Этого нет в корзине")

    # КОРЗИНА И ВЫБОР ВРЕМЕНИ (НОВЫЙ ШАГ)
    elif data == "cart_list":
        await query.answer()
        items_text, total, _ = get_order_summary(user_id)
        if not items_text:
            await edit_media_message(user_id, last_msg_id, CART_BANNER, "🛍 <b>Ваша корзина пуста!</b>", get_main_keyboard(), context)
            return
            
        caption = f"<b>Ваш заказ:</b>\n\n{items_text}\n\n<b>Итого:</b> {total:,} сум\n\nПерейти к выбору времени и оплате?".replace(",", " ")
        kb = [[InlineKeyboardButton("✅ Выбрать время и Оплатить", callback_data="select_time")], [InlineKeyboardButton("❌ Очистить", callback_data="cancel_order"), InlineKeyboardButton("🔙 Меню", callback_data="home")]]
        await edit_media_message(user_id, last_msg_id, CART_BANNER, caption, InlineKeyboardMarkup(kb), context)

    elif data == "cancel_order":
        await query.answer("Корзина очищена")
        clear_cart_db(user_id)
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "❌ Корзина очищена.", get_main_keyboard(), context)

    # --- ВЫБОР ВРЕМЕНИ ДЛЯ САМОВЫВОЗА ---
    elif data == "select_time":
        await query.answer()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("12:00", callback_data="time_12:00"), InlineKeyboardButton("12:30", callback_data="time_12:30")],
            [InlineKeyboardButton("13:00", callback_data="time_13:00"), InlineKeyboardButton("13:30", callback_data="time_13:30")],
            [InlineKeyboardButton("🔜 Как будет готово", callback_data="time_ASAP")],
            [InlineKeyboardButton("🔙 Назад", callback_data="cart_list")]
        ])
        await edit_media_message(user_id, last_msg_id, CART_BANNER, "🕒 <b>Выберите время, когда вы подниметесь за обедом:</b>\nМы заранее соберем его в контейнеры и отложим для вас!", kb, context)

    # --- ГЕНЕРАЦИЯ ОПЛАТЫ ПОСЛЕ ВЫБОРА ВРЕМЕНИ ---
    elif data.startswith("time_"):
        await query.answer()
        selected_time = data.split("_")[1]
        if selected_time == "ASAP":
            selected_time = "Как можно скорее"
        
        # Сохраняем время выдачи для этого пользователя
        context.user_data['pickup_time'] = selected_time

        _, total, _ = get_order_summary(user_id)
        click_url = f"https://my.click.uz/clickpass/{CLICK_PASS_ID}?amount={total}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💳 Оплатить в Click", url=click_url)], [InlineKeyboardButton("✅ Я оплатил(а)", callback_data="paid_order")]])
        
        formatted_total = f"{total:,}".replace(",", " ")
        caption = f"🕒 <b>Время выдачи: {selected_time}</b>\n💳 <b>Счёт на {formatted_total} сум!</b>\n\nОбед будет собран и отложен к вашему приходу.\nОтсканируйте <b>QR-код</b> или нажмите кнопку для оплаты."
        
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

    # ФИНАЛЬНЫЙ ШАГ И ОТПРАВКА АДМИНУ
    elif data == "paid_order":
        await query.answer()
        items_text, total, items_str = get_order_summary(user_id)
        if not items_text: return
        clear_cart_db(user_id)
        
        pickup_time = context.user_data.get('pickup_time', 'В порядке очереди')
        
        customer_name = query.from_user.first_name
        if query.from_user.last_name:
            customer_name += f" {query.from_user.last_name}"
        username = f" (@{query.from_user.username})" if query.from_user.username else ""
        
        text = f"✅ <b>Оплачено!</b>\n\n<b>Состав:</b>\n{items_text}\n\n📍 Выдача: 4 этаж\n🕒 Время: <b>{pickup_time}</b>\n\nВаш обед будет собран и отложен к этому времени. Спасибо за заказ!"
        try: await context.bot.delete_message(chat_id=user_id, message_id=last_msg_id)
        except: pass
        await context.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
        
        if ADMIN_ID:
            user = get_user_db(user_id)
            formatted_total = f"{total:,}".replace(",", " ")
            
            admin_text = (
                f"🚨 <b>Новый заказ (Предзаказ ко времени)!</b>\n"
                f"👤 Имя: {customer_name}{username}\n"
                f"📞 Тел: {user[1]}\n"
                f"🕒 <b>Собрать и отложить к: {pickup_time}</b>\n"
                f"💰 Сумма: {formatted_total} сум\n\n"
                f"🍽 <b>Состав:</b>\n{items_text}"
            )
            try: await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode='HTML')
            except: pass

# ==================== ВЕБ-СЕРВЕР ====================
async def handle_health_check(request): return web.Response(text="Bot OK")

async def main():
    app_bot = Application.builder().token(TOKEN).build()
    
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("post", post_to_channel))
    app_bot.add_handler(CommandHandler("admin", admin_command))
    
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
