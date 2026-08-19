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

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН")
ADMIN_ID_STR = os.getenv("ADMIN_ID", "ВАШ_ID") 
CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel") 

CLICK_PASS_ID = "052528"
QR_FILE_NAME = "qr.jpg"
POST_FILE_NAME = "post.jpg"

# Баннеры по умолчанию
MAIN_BANNER = "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=1200"
CART_BANNER = "https://images.unsplash.com/photo-1581349485608-9469926a8e5e?w=1200"

try:
    ADMIN_ID = int(ADMIN_ID_STR) if ADMIN_ID_STR.isdigit() else None
except (ValueError, TypeError):
    ADMIN_ID = None

DB_NAME = 'delivery_bot.db'
menu_active = True

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
        # Базовые категории
        cursor.executemany("INSERT INTO menu_categories VALUES (?, ?, ?)", [
            ('burgers', '🍔 Бургеры', 'https://images.unsplash.com/photo-1594179047519-f347310d3322?w=1200'),
            ('pizza', '🍕 Пицца', 'https://images.unsplash.com/photo-1513104890138-7c749659a591?w=1200'),
            ('drinks', '🥤 Напитки', 'https://images.unsplash.com/photo-1625944111553-bfd4b9c9f7a5?w=1200')
        ])
        # Базовые блюда
        cursor.executemany("INSERT INTO menu_items (cat_id, name, description, price, image) VALUES (?, ?, ?, ?, ?)", [
            ('burgers', 'Классический Чизбургер', 'Сочная котлета из говядины, сыр чеддер...', 35000, 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=600'),
            ('burgers', 'Бургер Техас BBQ', 'Котлета гриль, бекон, луковые кольца...', 45000, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d?w=600'),
            ('pizza', 'Пепперони', 'Острые колбаски пепперони, моцарелла...', 60000, 'https://images.unsplash.com/photo-1534308983496-4fabb1a015ee?w=600'),
            ('pizza', 'Маргарита', 'Итальянская пицца с томатами, моцареллой...', 50000, 'https://images.unsplash.com/photo-1627626775846-122b778965ae?w=600'),
            ('drinks', 'Домашний лимонад', 'Свежевыжатый сок лимона, лайма, мята...', 25000, 'https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=600')
        ])
    conn.commit()
    conn.close()

# --- Функции меню ---
def get_categories():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, banner FROM menu_categories")
    cats = [{"id": r[0], "name": r[1], "banner": r[2]} for r in cursor.fetchall()]
    conn.close()
    return cats

def get_category(cat_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, banner FROM menu_categories WHERE id = ?", (cat_id,))
    r = cursor.fetchone()
    conn.close()
    return {"id": r[0], "name": r[1], "banner": r[2]} if r else None

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
    cursor.execute("DELETE FROM active_orders WHERE item_id = ?", (item_id,)) # Убираем из корзин
    conn.commit()
    conn.close()

# --- Функции пользователей и статистики ---
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

def get_stats():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    u = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*), SUM(total) FROM order_history")
    row = cursor.fetchone()
    o, r = row[0] or 0, row[1] or 0
    conn.close()
    return u, o, r

# --- Корзина и Заказы ---
def get_cart_db(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT item_id, item_name, price, count FROM active_orders WHERE user_id = ?", (user_id,))
    cart_items = cursor.fetchall()
    conn.close()
    cart = {}
    for item in cart_items:
        cart[item[0]] = {"name": item[1], "price": item[2], "count": item[3]}
    return cart

def update_cart_db(user_id, item_id, item_name, price, count):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if count == 0:
        cursor.execute("DELETE FROM active_orders WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    else:
        cursor.execute("INSERT OR REPLACE INTO active_orders (user_id, item_id, item_name, price, count) VALUES (?, ?, ?, ?, ?)", (user_id, item_id, item_name, price, count))
    conn.commit()
    conn.close()

def clear_cart_db(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM active_orders WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def add_order_to_history(user_id, items_text, total):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today = datetime.now().strftime("%d.%m")
    cursor.execute("INSERT INTO order_history (user_id, date, items, total) VALUES (?, ?, ?, ?)", (user_id, today, items_text, total))
    cursor.execute("UPDATE users SET orders_count = orders_count + 1 WHERE user_id = ?", (user_id,))
    cursor.execute("SELECT orders_count FROM users WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return count

def get_order_history(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT date, items, total FROM order_history WHERE user_id = ? ORDER BY id DESC", (user_id,))
    history = cursor.fetchall()
    conn.close()
    return history

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
        [InlineKeyboardButton("🍽 Меню категорий", callback_data="cat_list")],
        [InlineKeyboardButton("🛍 Корзина", callback_data="cart_list"), InlineKeyboardButton("📜 История", callback_data="history_list")]
    ])

def get_categories_keyboard():
    keyboard = []
    row = []
    for cat in get_categories():
        row.append(InlineKeyboardButton(cat['name'], callback_data=f"cat_{cat['id']}_0"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Назад в главное меню", callback_data="days_list")])
    return InlineKeyboardMarkup(keyboard)

def get_item_pagination_keyboard(cat_id, item_index, item_id, total_items, cart_count=0):
    add_remove_text = f"➕ Добавить ({cart_count})" if cart_count > 0 else "➕ Добавить"
    keyboard = [[
        InlineKeyboardButton("➖ Удалить", callback_data=f"remove_item_{cat_id}_{item_index}_{item_id}"),
        InlineKeyboardButton(add_remove_text, callback_data=f"add_item_{cat_id}_{item_index}_{item_id}")
    ]]
    pagination_row = []
    if item_index > 0:
        pagination_row.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"view_item_{cat_id}_{item_index - 1}_{item_id}"))
    if item_index < total_items - 1:
        pagination_row.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"view_item_{cat_id}_{item_index + 1}_{item_id}"))
    if pagination_row: keyboard.append(pagination_row)
    keyboard.append([InlineKeyboardButton("🛍 Оформить", callback_data="cart_list"), InlineKeyboardButton("🔙 Категории", callback_data="cat_list")])
    return InlineKeyboardMarkup(keyboard)

# ==================== ОТПРАВКА И ИЗМЕНЕНИЕ СООБЩЕНИЙ ====================
async def send_photo_message(chat_id, photo_source, caption, reply_markup, context):
    try:
        if photo_source and (photo_source.startswith("http://") or photo_source.startswith("https://")):
            return await context.bot.send_photo(chat_id=chat_id, photo=photo_source, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
        elif photo_source and os.path.exists(photo_source):
            with open(photo_source, "rb") as photo:
                return await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
    except Exception:
        pass
    return await context.bot.send_message(chat_id=chat_id, text=caption, reply_markup=reply_markup, parse_mode='HTML')

async def edit_media_message(chat_id, message_id, photo_source, caption, reply_markup, context):
    try:
        if photo_source and (photo_source.startswith("http://") or photo_source.startswith("https://")):
            media = InputMediaPhoto(media=photo_source, caption=caption, parse_mode='HTML')
            await context.bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=reply_markup)
            return
        elif photo_source and os.path.exists(photo_source):
            with open(photo_source, "rb") as photo:
                media = InputMediaPhoto(media=photo, caption=caption, parse_mode='HTML')
                await context.bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=reply_markup)
                return
    except Exception:
        pass
    try: await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception: pass
    msg = await send_photo_message(chat_id, photo_source, caption, reply_markup, context)
    context.user_data['last_msg_id'] = msg.message_id

async def render_start(chat_id, context, from_restart=False):
    caption = "🏠 <b>Главное меню открыто 👇</b>\n\n🍽 Кликните по кнопке ниже, чтобы посмотреть категории и блюда."
    if from_restart:
        try: await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data.get('last_msg_id'))
        except Exception: pass
    msg = await send_photo_message(chat_id, MAIN_BANNER, caption, get_main_keyboard(), context)
    context.user_data['last_msg_id'] = msg.message_id

# ==================== ХЕНДЛЕРЫ И ЛОГИКА ====================
async def post_init(application: Application):
    commands = [
        BotCommand("start", "🏠 Главное меню"),
        BotCommand("menu", "🍽 Посмотреть категории"),
        BotCommand("history", "📜 История заказов")
    ]
    if ADMIN_ID:
        commands.append(BotCommand("admin", "👑 Панель Администратора"))
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_db()
    if not get_user_db(user_id):
        keyboard = [[KeyboardButton("📱 Поделиться номером", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await context.bot.send_message(chat_id=user_id, text="🏠 Добро пожаловать! Чтобы оформить заказ, пожалуйста, поделитесь номером телефона 👇", reply_markup=reply_markup)
    else:
        await render_start(user_id, context)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    contact = update.message.contact
    if contact:
        add_user_db(user_id, contact.phone_number)
        await update.message.reply_text("✅ Номер сохранён. Приятного аппетита!", reply_markup=ReplyKeyboardRemove())
        await render_start(user_id, context)

async def run_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_user_ids()
    count = 0
    msg = await update.message.reply_text("⏳ Рассылка начата...")
    for uid in users:
        try:
            await context.bot.copy_message(chat_id=uid, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
            count += 1
            await asyncio.sleep(0.05)
        except Exception: pass
    context.user_data['admin_state'] = None
    await msg.edit_text(f"✅ Рассылка завершена!\nУспешно отправлено: {count} пользователям.")

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    state = context.user_data.get('admin_state')
    
    if text.lower() == 'отмена':
        context.user_data['admin_state'] = None
        await update.message.reply_text("❌ Действие отменено.")
        return True
        
    if state == 'WAITING_BROADCAST':
        await run_broadcast(update, context)
        return True
    elif state == 'WAITING_DISH_NAME':
        context.user_data['new_dish']['name'] = text
        context.user_data['admin_state'] = 'WAITING_DISH_DESC'
        await update.message.reply_text("✏️ Введите описание блюда (ингредиенты):")
        return True
    elif state == 'WAITING_DISH_DESC':
        context.user_data['new_dish']['desc'] = text
        context.user_data['admin_state'] = 'WAITING_DISH_PRICE'
        await update.message.reply_text("💰 Введите цену (только цифры, например 45000):")
        return True
    elif state == 'WAITING_DISH_PRICE':
        if not text.isdigit():
            await update.message.reply_text("⚠️ Ошибка! Введите только цифры.")
            return True
        context.user_data['new_dish']['price'] = int(text)
        context.user_data['admin_state'] = 'WAITING_DISH_PHOTO'
        await update.message.reply_text("🖼 Отправьте фото блюда (как картинку) или ссылку (http...):")
        return True
    elif state == 'WAITING_DISH_PHOTO':
        context.user_data['new_dish']['photo'] = text 
        save_new_dish(context.user_data['new_dish'])
        context.user_data['admin_state'] = None
        await update.message.reply_text("✅ Блюдо успешно добавлено в меню!")
        return True
    return False

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_ID and user_id == ADMIN_ID:
        if await handle_admin_text(update, context):
            return
    if update.message.text == "🔄 Перезапустить":
        await start(update, context)

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
            await update.message.reply_text("✅ Блюдо успешно добавлено в меню!")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not ADMIN_ID or user_id != ADMIN_ID: return
    
    keyboard = [
        [InlineKeyboardButton("📢 Рассылка всем", callback_data="admin_broadcast")],
        [InlineKeyboardButton("➕ Добавить блюдо", callback_data="admin_add_dish"), InlineKeyboardButton("🗑 Удалить", callback_data="admin_del_dish")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"), InlineKeyboardButton("⛔ Открыть/Закрыть", callback_data="admin_toggle")]
    ]
    await update.message.reply_text("👑 <b>Панель администратора</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    init_db()

    # --- ЛОГИКА АДМИНА ---
    if data.startswith("admin_"):
        if not ADMIN_ID or user_id != ADMIN_ID: return
        
        if data == "admin_broadcast":
            context.user_data['admin_state'] = 'WAITING_BROADCAST'
            await query.message.edit_text("📢 Отправьте сообщение (текст или фото) для рассылки всем пользователям.\nДля отмены напишите 'отмена'.")
            
        elif data == "admin_stats":
            u, o, r = get_stats()
            await query.message.edit_text(f"📊 <b>Статистика:</b>\n\nПользователей: {u}\nВсего заказов: {o}\nВыручка: {r:,} сум".replace(",", " "), parse_mode='HTML')
            
        elif data == "admin_toggle":
            global menu_active
            menu_active = not menu_active
            status = "ОТКРЫТ ✅" if menu_active else "ЗАКРЫТ ⛔"
            await query.message.edit_text(f"Статус приема заказов изменён: {status}")

        elif data == "admin_add_dish":
            cats = get_categories()
            kb = [[InlineKeyboardButton(c['name'], callback_data=f"admin_addcat_{c['id']}")] for c in cats]
            await query.message.edit_text("В какую категорию добавить блюдо?", reply_markup=InlineKeyboardMarkup(kb))
            
        elif data.startswith("admin_addcat_"):
            cat_id = data.split("_")[2]
            context.user_data['admin_state'] = 'WAITING_DISH_NAME'
            context.user_data['new_dish'] = {'cat_id': cat_id}
            await query.message.edit_text("✏️ Введите название нового блюда.\nДля отмены напишите 'отмена'.")
            
        elif data == "admin_del_dish":
            cats = get_categories()
            kb = [[InlineKeyboardButton(c['name'], callback_data=f"admin_delcat_{c['id']}")] for c in cats]
            await query.message.edit_text("Из какой категории удалить?", reply_markup=InlineKeyboardMarkup(kb))
            
        elif data.startswith("admin_delcat_"):
            cat_id = data.split("_")[2]
            items = get_items_by_cat(cat_id)
            if not items:
                await query.message.edit_text("В этой категории нет блюд.")
                return
            kb = [[InlineKeyboardButton(i['name'], callback_data=f"admin_delitem_{i['id']}")] for i in items]
            await query.message.edit_text("🗑 Выберите блюдо для удаления:", reply_markup=InlineKeyboardMarkup(kb))
            
        elif data.startswith("admin_delitem_"):
            item_id = data.split("_")[2]
            delete_item(item_id)
            await query.message.edit_text("✅ Блюдо успешно удалено из меню.")
        await query.answer()
        return

    # --- ЛОГИКА ПОЛЬЗОВАТЕЛЯ ---
    user = get_user_db(user_id)
    if not user or not user[1]:
        await query.answer("Сначала поделитесь номером телефона (/start)", show_alert=True)
        return

    if not menu_active and not data.startswith("paid") and data != "cancel_order":
        await query.answer("⛔ Приём заказов временно закрыт.", show_alert=True)
        return

    last_msg_id = context.user_data.get('last_msg_id')

    if data == "restart" or data == "days_list":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "🏠 <b>Главное меню открыто 👇</b>\n\n🍽 Кликните по кнопке ниже, чтобы посмотреть категории.", get_main_keyboard(), context)

    elif data == "cat_list":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "<b>📅 Выберите категорию для просмотра блюд:</b>", get_categories_keyboard(), context)

    elif data.startswith("cat_") or data.startswith("view_item_"):
        await query.answer()
        parts = data.split("_")
        cat_id = parts[1] if data.startswith("cat_") else parts[2]
        item_index = int(parts[2]) if data.startswith("cat_") else int(parts[3])
        
        items = get_items_by_cat(cat_id)
        if not items:
            await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "В этой категории пока нет блюд 😔", get_categories_keyboard(), context)
            return
            
        item = items[item_index]
        cart_count = get_cart_db(user_id).get(item['id'], {}).get('count', 0)
        
        caption = f"🖼 <b>{item['name']}</b>\n\n📝 <i>{item['description']}</i>\n\n💰 <b>Цена:</b> {item['price']:,} сум\n".replace(",", " ")
        if cart_count > 0: caption += f"🛒 <b>В вашем заказе:</b> {cart_count} шт.\n"

        await edit_media_message(user_id, last_msg_id, item['image'], caption, get_item_pagination_keyboard(cat_id, item_index, item['id'], len(items), cart_count), context)

    elif data.startswith("add_item_"):
        parts = data.split("_")
        cat_id, item_index, item_id = parts[2], int(parts[3]), parts[4]
        items = get_items_by_cat(cat_id)
        item = items[item_index]
        new_count = get_cart_db(user_id).get(item_id, {}).get('count', 0) + 1
        
        update_cart_db(user_id, item_id, item['name'], item['price'], new_count)
        await query.answer(f"Добавлено: {item['name']}")
        
        caption = f"🖼 <b>{item['name']}</b>\n\n📝 <i>{item['description']}</i>\n\n💰 <b>Цена:</b> {item['price']:,} сум\n🛒 <b>В вашем заказе:</b> {new_count} шт.\n".replace(",", " ")
        await edit_media_message(user_id, last_msg_id, item['image'], caption, get_item_pagination_keyboard(cat_id, item_index, item['id'], len(items), new_count), context)

    elif data.startswith("remove_item_"):
        parts = data.split("_")
        cat_id, item_index, item_id = parts[2], int(parts[3]), parts[4]
        items = get_items_by_cat(cat_id)
        item = items[item_index]
        current_count = get_cart_db(user_id).get(item_id, {}).get('count', 0)
        
        if current_count > 0:
            new_count = current_count - 1
            update_cart_db(user_id, item_id, item['name'], item['price'], new_count)
            await query.answer("Удалено")
            caption = f"🖼 <b>{item['name']}</b>\n\n📝 <i>{item['description']}</i>\n\n💰 <b>Цена:</b> {item['price']:,} сум\n".replace(",", " ")
            if new_count > 0: caption += f"🛒 <b>В вашем заказе:</b> {new_count} шт.\n"
            await edit_media_message(user_id, last_msg_id, item['image'], caption, get_item_pagination_keyboard(cat_id, item_index, item['id'], len(items), new_count), context)
        else:
            await query.answer("Этого блюда нет в корзине")

    elif data == "cart_list":
        await query.answer()
        items_text, total, _ = get_order_summary(user_id)
        if not items_text:
            await edit_media_message(user_id, last_msg_id, CART_BANNER, "🛍 <b>Ваша корзина пуста!</b>\n\n🍽 Выберите категории и добавьте блюда.", get_categories_keyboard(), context)
            return
            
        caption = f"<b>Проверьте Ваш заказ:</b>\n\n{items_text}\n\n<b>Итого:</b> {total:,} сум\nВыдача: 4 этаж (12:30–14:00)\n\nПодтвердить и оплатить?".replace(",", " ")
        keyboard = [[InlineKeyboardButton("✅ Подтвердить и оплатить", callback_data="checkout_order")], [InlineKeyboardButton("❌ Очистить", callback_data="cancel_order"), InlineKeyboardButton("🔙 Меню", callback_data="cat_list")]]
        await edit_media_message(user_id, last_msg_id, CART_BANNER, caption, InlineKeyboardMarkup(keyboard), context)

    elif data == "cancel_order":
        await query.answer("Корзина очищена")
        clear_cart_db(user_id)
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "❌ Заказ отменён. Корзина очищена.", get_main_keyboard(), context)

    elif data == "checkout_order":
        await query.answer()
        _, total, _ = get_order_summary(user_id)
        click_url = f"https://my.click.uz/clickpass/{CLICK_PASS_ID}?amount={total}"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💳 Оплатить в Click", url=click_url)], [InlineKeyboardButton("✅ Я оплатил(а)", callback_data="paid_order")]])
        caption = f"💳 <b>Счёт на {total:,} сум сформирован!</b>\n\nОтсканируйте <b>QR-код</b> выше через Click или нажмите кнопку <b>Оплатить</b>.".replace(",", " ")
        await send_photo_message(user_id, QR_FILE_NAME, caption, keyboard, context)

    elif data == "paid_order":
        await query.answer()
        items_text, total, items_str = get_order_summary(user_id)
        if not items_text: return
        
        clear_cart_db(user_id)
        count = add_order_to_history(user_id, items_str, total)
        order_num = 2300 + count
        
        text = f"✅ <b>Оплачено! Заказ №{order_num} принят.</b>\n\n<b>Состав:</b>\n{items_text}\n\nВыдача: 4 этаж, 12:30–14:00\nУвидимся на обеде 🙂"
        await query.message.reply_text(text, parse_mode='HTML')
        
        if ADMIN_ID:
            admin_text = f"🚨 <b>Новый заказ №{order_num}</b>\n📞 Тел: {user[1]}\n💰 Сумма: {total:,} сум\n\n🍽 <b>Состав:</b>\n{items_text}".replace(",", " ")
            try: await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode='HTML')
            except Exception: pass

    elif data == "history_list":
        await query.answer()
        history = get_order_history(user_id)
        if not history:
             await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "📜 У вас пока нет истории заказов.", get_main_keyboard(), context)
             return
        hist_text = "<b>Ваша история заказов:</b>\n\n"
        for h in history: hist_text += f"{h[0]} — {h[1][:40]}... ({h[2]:,} сум) ✅\n".replace(",", " ")
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, hist_text, InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="restart")]]), context)

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await render_start(update.effective_user.id, context, from_restart=True)

# ==================== ВЕБ-СЕРВЕР И ЗАПУСК ====================
async def handle_health_check(request):
    return web.Response(text="Bot is running OK")

async def main():
    if TOKEN == "ВАШ_ТОКЕН" or not TOKEN:
        logging.error("❌ Укажите BOT_TOKEN в переменных среды!")
        return

    app_bot = Application.builder().token(TOKEN).post_init(post_init).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("menu", start))
    app_bot.add_handler(CommandHandler("history", history_command))
    app_bot.add_handler(CommandHandler("admin", admin_command))
    app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
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

    logging.info(f">>> Бот запущен! Веб-сервер слушает порт {port} <<<")
    while True: await asyncio.sleep(3600)

if __name__ == '__main__':
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
