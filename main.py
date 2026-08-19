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
POST_FILE_NAME = "post.jpg"

MAIN_BANNER = "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=1200"
CART_BANNER = "https://images.unsplash.com/photo-1581349485608-9469926a8e5e?w=1200"
LUNCH_BANNER = "https://images.unsplash.com/photo-1627308595229-7830f5c9244f?w=1200"
SUBS_BANNER = "https://images.unsplash.com/photo-1576867757603-05b1af5eb47b?w=1200"

try:
    ADMIN_ID = int(ADMIN_ID_STR) if ADMIN_ID_STR.isdigit() else None
except (ValueError, TypeError):
    ADMIN_ID = None

DB_NAME = 'delivery_bot_v3.db'
menu_active = True

# ==================== ДАННЫЕ МЕНЮ ПО УМОЛЧАНИЮ ====================
DEFAULT_CATEGORIES = [
    ('breakfasts', '🍳 Завтраки', 'https://images.unsplash.com/photo-1493770348161-369560ae357d?w=1200'),
    ('hot_drinks', '🔥 Горячие напитки', 'https://images.unsplash.com/photo-1541167760496-1628856ab772?w=1200'),
    ('cold_drinks', '🧊 Холодные напитки', 'https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=1200'),
    ('fresh_drinks', '🍹 Фреши', 'https://images.unsplash.com/photo-1613478223719-2ab802602423?w=1200'),
    ('subs', '💳 Подписки', SUBS_BANNER),
    # Для просмотра меню на неделю
    ('mon', 'Понедельник', MAIN_BANNER), ('tue', 'Вторник', MAIN_BANNER), ('wed', 'Среда', MAIN_BANNER),
    ('thu', 'Четверг', MAIN_BANNER), ('fri', 'Пятница', MAIN_BANNER)
]

DEFAULT_ITEMS = [
    ('breakfasts', 'Овсяная каша с ягодами', 'На молоке с добавлением свежих ягод и меда.', 20000, 'https://picsum.photos/400/300?random=201'),
    ('breakfasts', 'Сырники со сметаной', 'Домашние творожные сырники.', 25000, 'https://picsum.photos/400/300?random=202'),
    ('breakfasts', 'Блинчики с творогом', 'Тонкие блинчики с нежной творожной начинкой.', 22000, 'https://picsum.photos/400/300?random=203'),
    
    ('hot_drinks', 'Американо / Капучино', 'Свежесваренный кофе (200 / 250 мл).', 20000, 'https://picsum.photos/400/300?random=301'),
    ('hot_drinks', 'Авторский чай', 'Имбирь, лимон, мед.', 18000, 'https://picsum.photos/400/300?random=303'),
    
    ('cold_drinks', 'Домашний лимонад Цитрус-Мята', 'Освежающий лимонад (400 мл).', 25000, 'https://picsum.photos/400/300?random=304'),
    ('cold_drinks', 'Айс-Латте', 'Холодный кофе (350 мл).', 25000, 'https://picsum.photos/400/300?random=305'),
    
    ('fresh_drinks', 'Яблочный фреш', 'Свежевыжатый сок из зеленых яблок (250 мл).', 30000, 'https://picsum.photos/400/300?random=306'),
    ('fresh_drinks', 'Фреш Морковь-Яблоко', 'Витаминный заряд (250 мл).', 30000, 'https://picsum.photos/400/300?random=307'),
    ('fresh_drinks', 'Фреш Детокс', 'Свекла, яблоко, морковь (250 мл).', 32000, 'https://picsum.photos/400/300?random=308'),

    ('subs', 'Подписка: 1 неделя', 'Комплексные обеды на 5 рабочих дней.', 350000, SUBS_BANNER),
    ('subs', 'Подписка: 4 недели', 'Комплексные обеды на целый месяц (20 дней). Выгода 10%!', 1260000, SUBS_BANNER),

    # Информационное меню для просмотра
    ('mon', 'Меню Понедельника', 'Горячее: Курица/Мясо. Гарнир: Рис/Гречка. + Салат и Компот', 0, MAIN_BANNER),
    ('tue', 'Меню Вторника', 'Горячее: Курица/Мясо. Гарнир: Пюре/Макароны. + Салат и Компот', 0, MAIN_BANNER),
    ('wed', 'Меню Среды', 'Горячее: Курица/Мясо. Гарнир: Рис/Гречка. + Салат и Компот', 0, MAIN_BANNER),
    ('thu', 'Меню Четверга', 'Горячее: Курица/Мясо. Гарнир: Пюре/Макароны. + Салат и Компот', 0, MAIN_BANNER),
    ('fri', 'Меню Пятницы', 'Плов Ташкентский + Салат Ачик-Чучук + Компот', 0, MAIN_BANNER)
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
        [InlineKeyboardButton("🍳 Завтраки", callback_data="cat_breakfasts_0")],
        [InlineKeyboardButton("🍱 Комплексный обед дня", callback_data="lunch_build_start")],
        [InlineKeyboardButton("🥤 Напитки", callback_data="nav_drinks")],
        [InlineKeyboardButton("🗓 Недельное меню (просмотр)", callback_data="nav_week")],
        [InlineKeyboardButton("💳 Подписки на обеды", callback_data="cat_subs_0")],
        [InlineKeyboardButton("🛍 Корзина", callback_data="cart_list"), InlineKeyboardButton("📜 История", callback_data="history_list")]
    ])

def get_drinks_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Горячие напитки", callback_data="cat_hot_drinks_0")],
        [InlineKeyboardButton("🧊 Холодные напитки", callback_data="cat_cold_drinks_0")],
        [InlineKeyboardButton("🍹 Фреши", callback_data="cat_fresh_drinks_0")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="home")]
    ])

def get_week_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Пн", callback_data="cat_mon_0"), InlineKeyboardButton("Вт", callback_data="cat_tue_0"), InlineKeyboardButton("Ср", callback_data="cat_wed_0")],
        [InlineKeyboardButton("Чт", callback_data="cat_thu_0"), InlineKeyboardButton("Пт", callback_data="cat_fri_0")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="home")]
    ])

def get_item_pagination_keyboard(cat_id, item_index, item_id, total_items, cart_count=0, is_info=False):
    keyboard = []
    
    # Если это не информационное меню недели, показываем кнопку добавить
    if not is_info:
        add_text = f"➕ Добавить ({cart_count})" if cart_count > 0 else "➕ Добавить"
        keyboard.append([
            InlineKeyboardButton("➖ Удалить", callback_data=f"remove_item_{cat_id}_{item_index}_{item_id}"),
            InlineKeyboardButton(add_text, callback_data=f"add_item_{cat_id}_{item_index}_{item_id}")
        ])

    pagination_row = []
    if item_index > 0: pagination_row.append(InlineKeyboardButton("⬅️ Пред.", callback_data=f"view_item_{cat_id}_{item_index - 1}_{item_id}"))
    if item_index < total_items - 1: pagination_row.append(InlineKeyboardButton("След. ➡️", callback_data=f"view_item_{cat_id}_{item_index + 1}_{item_id}"))
    if pagination_row: keyboard.append(pagination_row)
    
    back_data = "home"
    if cat_id in ['hot_drinks', 'cold_drinks', 'fresh_drinks']: back_data = "nav_drinks"
    elif cat_id in ['mon', 'tue', 'wed', 'thu', 'fri']: back_data = "nav_week"
        
    keyboard.append([InlineKeyboardButton("🛍 В корзину", callback_data="cart_list"), InlineKeyboardButton("🔙 Назад", callback_data=back_data)])
    return InlineKeyboardMarkup(keyboard)

# ==================== ОТПРАВКА СООБЩЕНИЙ ====================
async def edit_media_message(chat_id, message_id, photo_source, caption, reply_markup, context):
    try:
        media = InputMediaPhoto(media=photo_source, caption=caption, parse_mode='HTML')
        await context.bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=reply_markup)
    except Exception:
        try: await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception: pass
        msg = await context.bot.send_photo(chat_id=chat_id, photo=photo_source, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
        context.user_data['last_msg_id'] = msg.message_id

async def render_start(chat_id, context):
    caption = "🏠 <b>Главное меню 👇</b>\n\n🍽 Выберите нужный раздел для заказа."
    try: await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data.get('last_msg_id'))
    except Exception: pass
    msg = await context.bot.send_photo(chat_id=chat_id, photo=MAIN_BANNER, caption=caption, reply_markup=get_main_keyboard(), parse_mode='HTML')
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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    init_db()
    last_msg_id = context.user_data.get('last_msg_id')

    # НАВИГАЦИЯ
    if data == "home":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "🏠 <b>Главное меню 👇</b>", get_main_keyboard(), context)

    elif data == "nav_drinks":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, "https://images.unsplash.com/photo-1541167760496-1628856ab772?w=1200", "<b>🥤 Выберите категорию напитков:</b>", get_drinks_keyboard(), context)

    elif data == "nav_week":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "<b>🗓 Информационное меню по дням недели:</b>", get_week_menu_keyboard(), context)

    # КОНСТРУКТОР ОБЕДА
    elif data == "lunch_build_start":
        await query.answer()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍗 Курица", callback_data="lunch_meat_chicken"), InlineKeyboardButton("🥩 Мясо", callback_data="lunch_meat_beef")],
            [InlineKeyboardButton("🔙 Отмена", callback_data="home")]
        ])
        await edit_media_message(user_id, last_msg_id, LUNCH_BANNER, "🍱 <b>Сборка обеда (Шаг 1/2)</b>\n\nВыберите горячее блюдо:", kb, context)

    elif data.startswith("lunch_meat_"):
        await query.answer()
        meat_type = "Курица" if data.split("_")[2] == "chicken" else "Мясо"
        context.user_data['temp_lunch_meat'] = meat_type
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍚 Рис", callback_data="lunch_garnish_rice"), InlineKeyboardButton("🥔 Пюре", callback_data="lunch_garnish_potato")],
            [InlineKeyboardButton("🍲 Гречка", callback_data="lunch_garnish_buckwheat")],
            [InlineKeyboardButton("🔙 Отмена", callback_data="home")]
        ])
        await edit_media_message(user_id, last_msg_id, LUNCH_BANNER, f"🍱 <b>Сборка обеда (Шаг 2/2)</b>\nГорячее: {meat_type}\n\nВыберите гарнир:", kb, context)

    elif data.startswith("lunch_garnish_"):
        await query.answer()
        garnish_map = {"rice": "Рис", "potato": "Пюре", "buckwheat": "Гречка"}
        garnish = garnish_map[data.split("_")[2]]
        meat = context.user_data.get('temp_lunch_meat', 'Не выбрано')
        
        lunch_name = f"Комплекс: {meat} + {garnish} + Салат + Компот"
        lunch_price = 75000
        
        item_id = f"lunch_{meat}_{garnish}"
        new_count = get_cart_db(user_id).get(item_id, {}).get('count', 0) + 1
        update_cart_db(user_id, item_id, lunch_name, lunch_price, new_count)
        
        await query.answer("✅ Обед собран и добавлен в корзину!", show_alert=True)
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "🏠 <b>Главное меню 👇</b>", get_main_keyboard(), context)

    # ПРОСМОТР КАТЕГОРИЙ И ДОБАВЛЕНИЕ
    elif data.startswith("cat_") or data.startswith("view_item_"):
        await query.answer()
        parts = data.split("_")
        cat_id = parts[1] if data.startswith("cat_") else parts[2]
        item_index = int(parts[2]) if data.startswith("cat_") else int(parts[3])
        
        items = get_items_by_cat(cat_id)
        if not items: return
            
        item = items[item_index]
        cart_count = get_cart_db(user_id).get(item['id'], {}).get('count', 0)
        is_info = cat_id in ['mon', 'tue', 'wed', 'thu', 'fri']
        
        caption = f"🖼 <b>{item['name']}</b>\n\n📝 <i>{item['description']}</i>\n\n💰 <b>Цена:</b> {item['price']:,} сум\n".replace(",", " ")
        if is_info: caption = f"ℹ️ <b>ИНФОРМАЦИЯ О МЕНЮ</b>\n\n🖼 <b>{item['name']}</b>\n\n📝 <i>{item['description']}</i>"
        if cart_count > 0 and not is_info: caption += f"🛒 <b>В вашем заказе:</b> {cart_count} шт.\n"

        await edit_media_message(user_id, last_msg_id, item['image'], caption, get_item_pagination_keyboard(cat_id, item_index, item['id'], len(items), cart_count, is_info), context)

    elif data.startswith("add_item_"):
        parts = data.split("_")
        cat_id, item_index, item_id = parts[2], int(parts[3]), parts[4]
        items = get_items_by_cat(cat_id)
        item = items[item_index]
        new_count = get_cart_db(user_id).get(item_id, {}).get('count', 0) + 1
        
        update_cart_db(user_id, item_id, item['name'], item['price'], new_count)
        await query.answer(f"Добавлено")
        caption = f"🖼 <b>{item['name']}</b>\n\n📝 <i>{item['description']}</i>\n\n💰 <b>Цена:</b> {item['price']:,} сум\n🛒 <b>В корзине:</b> {new_count} шт.\n".replace(",", " ")
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
            if new_count > 0: caption += f"🛒 <b>В корзине:</b> {new_count} шт.\n"
            await edit_media_message(user_id, last_msg_id, item['image'], caption, get_item_pagination_keyboard(cat_id, item_index, item['id'], len(items), new_count), context)
        else:
            await query.answer("Этого нет в корзине")

    # КОРЗИНА И ОФОРМЛЕНИЕ
    elif data == "cart_list":
        await query.answer()
        items_text, total, _ = get_order_summary(user_id)
        if not items_text:
            await edit_media_message(user_id, last_msg_id, CART_BANNER, "🛍 <b>Ваша корзина пуста!</b>", get_main_keyboard(), context)
            return
            
        caption = f"<b>Ваш заказ:</b>\n\n{items_text}\n\n<b>Итого:</b> {total:,} сум\n\nПодтвердить и оплатить?".replace(",", " ")
        kb = [[InlineKeyboardButton("✅ Подтвердить", callback_data="checkout_order")], [InlineKeyboardButton("❌ Очистить", callback_data="cancel_order"), InlineKeyboardButton("🔙 Меню", callback_data="home")]]
        await edit_media_message(user_id, last_msg_id, CART_BANNER, caption, InlineKeyboardMarkup(kb), context)

    elif data == "cancel_order":
        await query.answer("Корзина очищена")
        clear_cart_db(user_id)
        await edit_media_message(user_id, last_msg_id, MAIN_BANNER, "❌ Корзина очищена.", get_main_keyboard(), context)

    elif data == "checkout_order":
        await query.answer()
        _, total, _ = get_order_summary(user_id)
        click_url = f"https://my.click.uz/clickpass/{CLICK_PASS_ID}?amount={total}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💳 Оплатить", url=click_url)], [InlineKeyboardButton("✅ Я оплатил(а)", callback_data="paid_order")]])
        caption = f"💳 <b>Счёт на {total:,} сум!</b>\n\nОтсканируйте <b>QR-код</b> или нажмите кнопку.".replace(",", " ")
        
        try: await context.bot.delete_message(chat_id=user_id, message_id=last_msg_id)
        except: pass
        if os.path.exists(QR_FILE_NAME):
            with open(QR_FILE_NAME, "rb") as p: msg = await context.bot.send_photo(chat_id=user_id, photo=p, caption=caption, reply_markup=kb, parse_mode='HTML')
        else:
            msg = await context.bot.send_message(chat_id=user_id, text=caption, reply_markup=kb, parse_mode='HTML')
        context.user_data['last_msg_id'] = msg.message_id

    elif data == "paid_order":
        await query.answer()
        items_text, total, items_str = get_order_summary(user_id)
        if not items_text: return
        clear_cart_db(user_id)
        
        # Симуляция сохранения заказа
        text = f"✅ <b>Оплачено!</b>\n\n<b>Состав:</b>\n{items_text}\n\nВыдача: 4 этаж.\nСпасибо за заказ!"
        try: await context.bot.delete_message(chat_id=user_id, message_id=last_msg_id)
        except: pass
        await context.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
        
        # Уведомление админу
        if ADMIN_ID:
            user = get_user_db(user_id)
            admin_text = f"🚨 <b>Новый заказ!</b>\n📞 Тел: {user[1]}\n💰 Сумма: {total:,} сум\n\n🍽 <b>Состав:</b>\n{items_text}".replace(",", " ")
            try: await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode='HTML')
            except: pass

# ==================== ВЕБ-СЕРВЕР ====================
async def handle_health_check(request): return web.Response(text="Bot OK")

async def main():
    app_bot = Application.builder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
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
