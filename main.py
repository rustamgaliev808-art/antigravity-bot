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

MAIN_BANNER = "https://picsum.photos/1200/800?random=10"
CART_BANNER = "https://picsum.photos/1200/800?random=11"
LUNCH_BANNER = "https://picsum.photos/1200/800?random=12"
SUBS_BANNER = "https://picsum.photos/1200/800?random=13"

try:
    ADMIN_ID = int(ADMIN_ID_STR) if ADMIN_ID_STR.isdigit() else None
except (ValueError, TypeError):
    ADMIN_ID = None

DB_NAME = 'delivery_bot_v9.db'
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
    ('breakfasts', 'Яичница с сосисками', 'Классический сытный завтрак.', 40000, ''),
    ('breakfasts', 'Омлет', 'Пышный свежеприготовленный омлет.', 35000, ''),
    ('breakfasts', 'Гренки 4 шт', 'Золотистые поджаренные гренки.', 20000, ''),
    ('breakfasts', 'Овсяная каша', 'Вкусная и полезная каша.', 25000, ''),
    
    ('hot_drinks', 'Американо', 'Классический черный кофе.', 18000, ''),
    ('hot_drinks', 'Капучино', 'Кофе с молочной пеной.', 20000, ''),
    ('hot_drinks', 'Латте', 'Кофейный напиток с молоком.', 22000, ''),
    
    ('cold_drinks', 'Кола 0.25 / Zero', 'Освежающая газировка.', 13000, ''),
    ('cold_drinks', 'Fanta 0.25', 'Апельсиновая газировка.', 12000, ''),
    ('cold_drinks', 'Мохито (Клас. / Клубничный)', 'Охлаждающий напиток.', 20000, ''),
    
    ('fresh_drinks', 'Яблочный фреш', 'Свежевыжатый сок (250 мл).', 30000, ''),
    ('fresh_drinks', 'Фреш Морковь-Яблоко', 'Витаминный заряд (250 мл).', 30000, ''),

    ('subs', 'Подписка: 1 нед (Курица)', 'Комплексные обеды на 5 рабочих дней.', 290000, ''),
    ('subs', 'Подписка: 1 нед (Говядина)', 'Комплексные обеды на 5 рабочих дней.', 310000, ''),

    ('mon', 'Пн. Комплекс (Говядина)', 'Тефтели с гречкой + Салат + Компот', 62000, ''),
    ('mon', 'Пн. Комплекс (Курица)', 'Курица в соусе с рисом + Салат + Компот', 58000, ''),
    
    ('tue', 'Вт. Комплекс (Говядина)', 'Тушеная говядина с картофелем + Салат + Компот', 62000, ''),
    ('tue', 'Вт. Комплекс (Курица)', 'Запеченная курица с пюре + Салат + Компот', 58000, ''),
    
    ('wed', 'Ср. Комплекс (Говядина)', 'Бефстроганов (с пюре/рисом) + Салат + Компот', 62000, ''),
    ('wed', 'Ср. Комплекс (Курица)', 'Куриный казан-кабоб + Салат + Компот', 58000, ''),
    
    ('thu', 'Чт. Комплекс (Говядина)', 'Плов из говядины + Салат + Компот', 62000, ''),
    ('thu', 'Чт. Комплекс (Курица)', 'Курица с овощами с пюре + Салат + Компот', 58000, ''),
    
    ('fri', 'Пт. Комплекс (Говядина)', 'Гуляш из говядины + Салат + Компот', 62000, ''),
    ('fri', 'Пт. Комплекс (Курица)', 'Запеченные куриные бедра + Салат + Компот', 58000, '')
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
    cursor.execute("INSERT OR REPLACE INTO users (user_id, phone, orders_count) VALUES (?, ?, COALESCE((SELECT orders_count FROM users WHERE user_id=?), 0))", (user_id, phone, user_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

def get_today_stats(date_str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(total) FROM order_history WHERE date = ?", (date_str,))
    row = cursor.fetchone()
    conn.close()
    return (row[0] or 0, row[1] or 0)

def save_order_history(user_id, items, total):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today = datetime.now().strftime("%d.%m.%Y")
    cursor.execute("INSERT INTO order_history (user_id, date, items, total) VALUES (?, ?, ?, ?)", (user_id, today, items, total))
    cursor.execute("UPDATE users SET orders_count = orders_count + 1 WHERE user_id = ?", (user_id,))
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
        [InlineKeyboardButton("🍱 Комплексный обед (Сегодня)", callback_data="lunch_today")],
        [InlineKeyboardButton("🍳 Завтраки", callback_data="cat_breakfasts"), InlineKeyboardButton("🥤 Напитки", callback_data="nav_drinks")],
        [InlineKeyboardButton("🗓 Меню на неделю", callback_data="nav_week"), InlineKeyboardButton("💳 Подписки", callback_data="cat_subs")],
        [InlineKeyboardButton("🛍 Корзина", callback_data="cart_list")]
    ])

def get_drinks_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Горячие напитки", callback_data="cat_hot_drinks")],
        [InlineKeyboardButton("🧊 Холодные напитки", callback_data="cat_cold_drinks")],
        [InlineKeyboardButton("🍹 Фреши", callback_data="cat_fresh_drinks")],
        [InlineKeyboardButton("⬅️ Вернуться в меню", callback_data="home")]
    ])

def get_week_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Пн", callback_data="cat_mon"), InlineKeyboardButton("Вт", callback_data="cat_tue"), InlineKeyboardButton("Ср", callback_data="cat_wed")],
        [InlineKeyboardButton("Чт", callback_data="cat_thu"), InlineKeyboardButton("Пт", callback_data="cat_fri")],
        [InlineKeyboardButton("⬅️ Вернуться в меню", callback_data="home")]
    ])

def get_category_list_keyboard(user_id, cat_id, items):
    keyboard = []
    cart = get_cart_db(user_id)
    
    for item in items:
        item_id = item['id']
        count = cart.get(item_id, {}).get('count', 0)
        display_name = item['name'][:16] + ".." if len(item['name']) > 16 else item['name']
        middle_text = f"{display_name} : {count} шт"
        
        keyboard.append([
            InlineKeyboardButton("➖", callback_data=f"list_rm_{cat_id}_{item_id}"),
            InlineKeyboardButton(middle_text, callback_data="ignore"),
            InlineKeyboardButton("➕", callback_data=f"list_add_{cat_id}_{item_id}")
        ])

    back_data = "nav_drinks" if cat_id in ['hot_drinks', 'cold_drinks', 'fresh_drinks'] else ("nav_week" if cat_id in ['mon', 'tue', 'wed', 'thu', 'fri'] else "home")
    keyboard.append([InlineKeyboardButton("🛍 В корзину", callback_data="cart_list"), InlineKeyboardButton("🔙 Назад", callback_data=back_data)])
    return InlineKeyboardMarkup(keyboard)

# ==================== ОБЩИЕ ФУНКЦИИ ====================
async def edit_media_message(chat_id, message_id, photo_source, caption, reply_markup, context):
    try:
        media = InputMediaPhoto(media=photo_source, caption=caption, parse_mode='HTML')
        await context.bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=reply_markup)
    except Exception:
        try: await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except: pass
        msg = await context.bot.send_photo(chat_id=chat_id, photo=photo_source, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
        context.user_data['last_msg_id'] = msg.message_id

async def render_start(chat_id, context):
    caption = "🏠 <b>Главное меню</b>\n\n🍽 Выберите нужный раздел для заказа. Вкусные обеды уже ждут!"
    try: await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data.get('last_msg_id'))
    except: pass
    msg = await context.bot.send_photo(chat_id=chat_id, photo=MAIN_BANNER, caption=caption, reply_markup=get_main_keyboard(), parse_mode='HTML')
    context.user_data['last_msg_id'] = msg.message_id

# ==================== ХЕНДЛЕРЫ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_db()
    if not get_user_db(user_id):
        keyboard = [[KeyboardButton("📱 Поделиться номером", request_contact=True)]]
        await context.bot.send_message(chat_id=user_id, text="👋 <b>Добро пожаловать в Click Обеды!</b>\n\nЧтобы начать, пожалуйста, поделитесь номером телефона 👇", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True), parse_mode='HTML')
    else:
        await render_start(user_id, context)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    contact = update.message.contact
    if contact:
        add_user_db(user_id, contact.phone_number)
        await update.message.reply_text("✅ Номер успешно сохранён!", reply_markup=ReplyKeyboardRemove())
        await render_start(user_id, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # Обработка состояния рассылки для админа
    if ADMIN_ID and user_id == ADMIN_ID and context.user_data.get('admin_state') == 'broadcasting':
        if text.lower() == 'отмена':
            context.user_data['admin_state'] = None
            await update.message.reply_text("❌ Рассылка отменена.")
            return
        
        users = get_all_users()
        success = 0
        await update.message.reply_text("⏳ Рассылка началась, подождите...")
        for u in users:
            try:
                await context.bot.send_message(chat_id=u[0], text=f"📢 <b>Уведомление:</b>\n\n{text}", parse_mode='HTML')
                success += 1
                await asyncio.sleep(0.1) # Защита от спам-блока Telegram
            except: pass
        context.user_data['admin_state'] = None
        await update.message.reply_text(f"✅ Рассылка успешно завершена!\nДоставлено: <b>{success}</b> пользователям.", parse_mode='HTML')
        return

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not ADMIN_ID or user_id != ADMIN_ID: return
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика за сегодня", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Сделать рассылку", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⛔ Открыть/Закрыть прием заказов", callback_data="admin_toggle")]
    ]
    await update.message.reply_text("👑 <b>Панель администратора</b>\nВыберите действие:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def post_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not ADMIN_ID or user_id != ADMIN_ID: return
    weekday = datetime.now().weekday()
    
    posts_by_day = {
        0: ("<b>Начинаем неделю вкусно! ☀️</b>\n\nСегодня на обед домашние комплексы (салат и компот включены). Успейте заказать до 11:00!", LUNCH_BANNER),
        1: ("<b>Время сытного обеда! 😋</b>\n\nНаши комплексные обеды уже ждут вас. Зарядитесь энергией!", LUNCH_BANNER),
        2: ("<b>Экватор недели! 🍽</b>\n\nПорадуйте себя вкусным обедом. Салат и компот уже включены в стоимость.", LUNCH_BANNER),
        3: ("<b>Четверг — день Плова! 🍚🔥</b>\n\nКакая же неделя без традиционного плова? Порции разлетаются быстро!", LUNCH_BANNER),
        4: ("<b>Пятница! Вкусно завершаем неделю 🎉</b>\n\nСпасибо, что обедали с нами всю неделю!", LUNCH_BANNER)
    }

    if weekday not in posts_by_day:
        await update.message.reply_text("Сегодня выходной! Готовых текстов нет.")
        return

    text, photo = posts_by_day[weekday]
    bot_info = await context.bot.get_me()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🥗 Заказать обед в 2 клика", url=f"https://t.me/{bot_info.username}")]])

    try:
        await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=text, reply_markup=keyboard, parse_mode='HTML')
        await update.message.reply_text(f"✅ Пост отправлен в канал {CHANNEL_ID}.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка отправки: {e}")

# ==================== ОБРАБОТЧИК КНОПОК ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    init_db()
    last_msg_id = context.user_data.get('last_msg_id', query.message.message_id)

    if data == "ignore":
        await query.answer()
        return

    # --- АДМИН ПАНЕЛЬ ---
    if data == "admin_toggle":
        if not ADMIN_ID or user_id != ADMIN_ID: return
        global menu_active
        menu_active = not menu_active
        status = "ОТКРЫТ ✅" if menu_active else "ЗАКРЫТ ⛔"
        await query.answer(f"Прием заказов: {status}", show_alert=True)
        return

    elif data == "admin_stats":
        if not ADMIN_ID or user_id != ADMIN_ID: return
        users_count = len(get_all_users())
        today = datetime.now().strftime("%d.%m.%Y")
        orders_today, revenue_today = get_today_stats(today)
        
        stats_text = (
            f"📊 <b>Статистика бота:</b>\n\n"
            f"👥 Всего пользователей: <b>{users_count}</b>\n"
            f"🛒 Заказов за сегодня: <b>{orders_today}</b>\n"
            f"💰 Выручка за сегодня: <b>{revenue_today:,} сум</b>".replace(",", " ")
        )
        await query.answer()
        await query.message.edit_text(stats_text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]]))
        return
        
    elif data == "admin_broadcast":
        if not ADMIN_ID or user_id != ADMIN_ID: return
        context.user_data['admin_state'] = 'broadcasting'
        await query.answer()
        await query.message.reply_text("✍️ Напишите текст, который нужно отправить всем пользователям бота.\n\n<i>Для отмены напишите слово 'Отмена'</i>", parse_mode='HTML')
        return
        
    elif data == "admin_back":
        if not ADMIN_ID or user_id != ADMIN_ID: return
        keyboard = [
            [InlineKeyboardButton("📊 Статистика за сегодня", callback_data="admin_stats")],
            [InlineKeyboardButton("📢 Сделать рассылку", callback_data="admin_broadcast")],
            [InlineKeyboardButton("⛔ Открыть/Закрыть прием заказов", callback_data="admin_toggle")]
        ]
        await query.message.edit_text("👑 <b>Панель администратора</b>\nВыберите действие:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return

    # --- НАВИГАЦИЯ ---
    if data == "home":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "🏠 <b>Главное меню</b>\n\n🍽 Выберите нужный раздел для заказа.", get_main_keyboard(), context)

    elif data == "nav_drinks":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, "https://picsum.photos/1200/800?random=30", "<b>🥤 Выберите категорию напитков:</b>", get_drinks_keyboard(), context)

    elif data == "nav_week":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "<b>🗓 Выберите день для предзаказа обеда:</b>", get_week_menu_keyboard(), context)

    elif data == "lunch_today":
        if not menu_active:
            await query.answer("⛔ Приём заказов на сегодня закрыт.", show_alert=True)
            return
        weekday = datetime.now().weekday()
        days_map = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri'}
        if weekday in days_map:
            data = f"cat_{days_map[weekday]}" 
        else:
            await query.answer("Сегодня выходной! 😴\nСделайте предзаказ через 'Меню на неделю'.", show_alert=True)
            return

    # --- КАТЕГОРИИ И ТОВАРЫ ---
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

    elif data.startswith("list_add_"):
        parts = data.split("_")
        item_id, cat_id = parts[-1], "_".join(parts[2:-1])
        if not menu_active and cat_id in ['mon', 'tue', 'wed', 'thu', 'fri']:
            await query.answer("⛔ Приём заказов закрыт.", show_alert=True)
            return
            
        items = get_items_by_cat(cat_id)
        item = next((i for i in items if i['id'] == item_id), None)
        if not item: return
        
        new_count = get_cart_db(user_id).get(item_id, {}).get('count', 0) + 1
        update_cart_db(user_id, item_id, item['name'], item['price'], new_count)
        await query.answer(f"➕ Добавлено: {item['name']}")
        await context.bot.edit_message_reply_markup(chat_id=user_id, message_id=last_msg_id, reply_markup=get_category_list_keyboard(user_id, cat_id, items))

    elif data.startswith("list_rm_"):
        parts = data.split("_")
        item_id, cat_id = parts[-1], "_".join(parts[2:-1])
        items = get_items_by_cat(cat_id)
        item = next((i for i in items if i['id'] == item_id), None)
        if not item: return
        
        current_count = get_cart_db(user_id).get(item_id, {}).get('count', 0)
        if current_count > 0:
            update_cart_db(user_id, item_id, item['name'], item['price'], current_count - 1)
            await query.answer("➖ Удалено")
            await context.bot.edit_message_reply_markup(chat_id=user_id, message_id=last_msg_id, reply_markup=get_category_list_keyboard(user_id, cat_id, items))
        else:
            await query.answer("Этого нет в корзине")

    # --- КОРЗИНА И ОПЛАТА ---
    elif data == "cart_list":
        await query.answer()
        items_text, total, _ = get_order_summary(user_id)
        if not items_text:
            await edit_media_message(user_id, last_msg_id, CART_BANNER, "🛍 <b>Ваша корзина пуста!</b>", get_main_keyboard(), context)
            return
            
        caption = f"🛒 <b>Ваш заказ:</b>\n\n{items_text}\n\n<b>Итого:</b> {total:,} сум\n\nПодтвердить и оплатить?".replace(",", " ")
        kb = [[InlineKeyboardButton("✅ Оплатить", callback_data="checkout_order")], [InlineKeyboardButton("❌ Очистить корзину", callback_data="cancel_order"), InlineKeyboardButton("🔙 Назад", callback_data="home")]]
        await edit_media_message(user_id, last_msg_id, CART_BANNER, caption, InlineKeyboardMarkup(kb), context)

    elif data == "cancel_order":
        await query.answer("Корзина очищена")
        clear_cart_db(user_id)
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "❌ <b>Корзина очищена.</b>", get_main_keyboard(), context)

    elif data == "checkout_order":
        if not menu_active:
            await query.answer("⛔ Приём заказов закрыт. Оплата недоступна.", show_alert=True)
            return
        await query.answer()
        _, total, _ = get_order_summary(user_id)
        click_url = f"https://my.click.uz/clickpass/{CLICK_PASS_ID}?amount={total}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💳 Оплатить в Click", url=click_url)], [InlineKeyboardButton("✅ Я оплатил(а)", callback_data="paid_order")], [InlineKeyboardButton("🔙 В корзину", callback_data="cart_list")]])
        
        caption = f"💳 <b>Счёт на {total:,} сум выставлен!</b>\n\nНажмите кнопку для оплаты в приложении.".replace(",", " ")
        await edit_media_message(user_id, last_msg_id, CART_BANNER, caption, kb, context)

    elif data == "paid_order":
        await query.answer()
        items_text, total, items_str = get_order_summary(user_id)
        if not items_text: return
        clear_cart_db(user_id)
        
        save_order_history(user_id, items_str, total)
        
        name = query.from_user.first_name + (f" {query.from_user.last_name}" if query.from_user.last_name else "")
        username = f" (@{query.from_user.username})" if query.from_user.username else ""
        
        text = f"✅ <b>Оплачено успешно!</b>\n\n<b>Состав:</b>\n{items_text}\n\n📍 Выдача: на Вашем этаже.\nПриятного аппетита!"
        await edit_media_message(user_id, last_msg_id, CART_BANNER, text, InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В главное меню", callback_data="home")]]), context)
        
        if ADMIN_ID:
            user = get_user_db(user_id)
            admin_text = (
                f"🚨 <b>НОВЫЙ ОПЛАЧЕННЫЙ ЗАКАЗ!</b>\n"
                f"👤 Имя: {name}{username}\n"
                f"📞 Тел: {user[1]}\n"
                f"💰 Сумма: {total:,} сум\n\n"
                f"🍽 <b>Состав:</b>\n{items_text}".replace(",", " ")
            )
            try: await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode='HTML')
            except: pass

# ==================== ВЕБ-СЕРВЕР (ДЛЯ ХОСТИНГА) ====================
async def handle_health_check(request): return web.Response(text="Bot OK")

async def main():
    app_bot = Application.builder().token(TOKEN).build()
    
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("post", post_to_channel))
    app_bot.add_handler(CommandHandler("admin", admin_command))
    app_bot.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
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
