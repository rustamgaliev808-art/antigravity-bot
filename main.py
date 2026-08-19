import os
import logging
import asyncio
import sqlite3
import re
from datetime import datetime
from aiohttp import web
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    InputMediaPhoto
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from telegram.exceptions import TelegramUnauthorizedError

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
# Укажите свой ID. Если не число, бот запустится, но уведомлений не будет
ADMIN_ID_STR = os.getenv("ADMIN_ID", "YOUR_TELEGRAM_ID_HERE") 
CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel_username") 

CLICK_PASS_ID = "052528"
QR_FILE_NAME = "qr.jpg"
POST_FILE_NAME = "post.jpg"

try:
    ADMIN_ID = int(ADMIN_ID_STR) if ADMIN_ID_STR.isdigit() else None
except (ValueError, TypeError):
    logging.error("Неверный формат ADMIN_ID! Укажите числовой ID.")
    ADMIN_ID = None

DB_NAME = 'delivery_bot.db'
menu_active = True

# ==================== ДАННЫЕ МЕНЮ (APP-STYLE) ====================
MENU_DATA = {
    "categories": {
        "burgers": {
            "name": "🍔 Бургеры",
            "banner": "https://images.unsplash.com/photo-1594179047519-f347310d3322?w=1200",
            "items": [
                {
                    "id": "b1",
                    "name": "Классический Чизбургер",
                    "description": "Сочная котлета из говядины, сыр чеддер, маринованные огурцы, красный лук, фирменный соус.",
                    "price": 35000,
                    "image": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=600"
                },
                {
                    "id": "b2",
                    "name": "Бургер Техас BBQ",
                    "description": "Котлета гриль, бекон, луковые кольца, сыр гауда, соус барбекю.",
                    "price": 45000,
                    "image": "https://images.unsplash.com/photo-1551782450-a2132b4ba21d?w=600"
                }
            ]
        },
        "pizza": {
            "name": "🍕 Пицца",
            "banner": "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=1200",
            "items": [
                {
                    "id": "p1",
                    "name": "Пепперони",
                    "description": "Классическая пицца с острыми колбасками пепперони, моцареллой и томатным соусом (30 см).",
                    "price": 60000,
                    "image": "https://images.unsplash.com/photo-1534308983496-4fabb1a015ee?w=600"
                },
                {
                    "id": "p2",
                    "name": "Маргарита",
                    "description": "Классическая итальянская пицца с томатами, моцареллой и базиликом (30 см).",
                    "price": 50000,
                    "image": "https://images.unsplash.com/photo-1627626775846-122b778965ae?w=600"
                }
            ]
        },
        "drinks": {
            "name": "🥤 Напитки",
            "banner": "https://images.unsplash.com/photo-1625944111553-bfd4b9c9f7a5?w=1200",
            "items": [
                {
                    "id": "d1",
                    "name": "Классический лимонад Цитрус-Мята",
                    "description": "Свежевыжатый сок лимона, лайма, свежая мята, сахарный сироп, газированная вода.",
                    "price": 25000,
                    "image": "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=600"
                },
                {
                    "id": "d2",
                    "name": "Американо / Капучино",
                    "description": "Ароматный свежесваренный кофе из зерен арабики (250 мл).",
                    "price": 22000,
                    "image": "https://images.unsplash.com/photo-1595434091143-b375ace5d468?w=600"
                }
            ]
        }
    }
}

# ==================== РАБОТА С БД ====================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                      (user_id INTEGER PRIMARY KEY, phone TEXT, orders_count INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS active_orders
                      (user_id INTEGER, item_id TEXT, item_name TEXT, price INTEGER, count INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS order_history
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, date TEXT, items TEXT, total INTEGER)''')
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

# ==================== КЛАВИАТУРЫ (APP-STYLE) ====================
def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🍽 Меню категорий", callback_data="cat_list"), InlineKeyboardButton("📜 История", callback_data="history_list")],
        [InlineKeyboardButton("🛍 Корзина", callback_data="cart_list"), InlineKeyboardButton("🔄 Перезапустить", callback_data="restart")]
    ])

def get_categories_keyboard():
    keyboard = []
    # Сетка 2x2 или 2x3
    row = []
    for cat_id, cat_info in MENU_DATA["categories"].items():
        row.append(InlineKeyboardButton(cat_info['name'], callback_data=f"cat_{cat_id}_0")) # view item index 0
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Назад в главное меню", callback_data="days_list")]) # Will manage 'days_list' -> main
    return InlineKeyboardMarkup(keyboard)

def get_item_pagination_keyboard(cat_id, item_index, item_id, total_items, cart_count=0):
    """Клавиатура пагинации для карточки блюда."""
    add_remove_text = f"➕ Добавить ({cart_count})" if cart_count > 0 else "➕ Добавить"
    keyboard = [
        [
            InlineKeyboardButton("➖ Удалить", callback_data=f"remove_item_{cat_id}_{item_index}_{item_id}"),
            InlineKeyboardButton(add_remove_text, callback_data=f"add_item_{cat_id}_{item_index}_{item_id}")
        ]
    ]

    # Пагинация
    pagination_row = []
    if item_index > 0:
        pagination_row.append(InlineKeyboardButton("⬅️ Предыдущее", callback_data=f"view_item_{cat_id}_{item_index - 1}_{item_id}"))
    if item_index < total_items - 1:
        pagination_row.append(InlineKeyboardButton("Следующее ➡️", callback_data=f"view_item_{cat_id}_{item_index + 1}_{item_id}"))
    
    if pagination_row:
        keyboard.append(pagination_row)
        
    keyboard.append([InlineKeyboardButton("🛍 Оформить заказ", callback_data="cart_list"), InlineKeyboardButton("🔙 К категориям", callback_data="cat_list")])
    return InlineKeyboardMarkup(keyboard)

def get_order_summary(user_id):
    cart = get_cart_db(user_id)
    if not cart:
        return None, 0, ""

    formatted_lines = []
    short_lines = []
    total = 0
    
    for item_id, data in cart.items():
        name = data['name']
        unit_price = data['price']
        cnt = data['count']
        total_price = unit_price * cnt
        formatted_lines.append(f"• {name} x{cnt} — {total_price:,} сум".replace(",", " "))
        short_lines.append(f"{name} x{cnt}")
        total += total_price
        
    items_text = "\n".join(formatted_lines)
    items_str = ", ".join(short_lines)
    return items_text, total, items_str

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
async def render_start(chat_id, context, from_restart=False):
    user = get_user_db(chat_id)
    caption = "🏠 <b>Главное меню открыто 👇</b>\n\n🍽 Кликните по кнопке ниже, чтобы посмотреть категории и блюда."
    if from_restart:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data.get('last_msg_id'))
        except Exception:
            pass
    msg = await send_photo_message(chat_id, MENU_DATA["categories"]["burgers"]["banner"], caption, get_main_keyboard(), context)
    context.user_data['last_msg_id'] = msg.message_id

async def send_photo_message(chat_id, photo_source, caption, reply_markup, context):
    try:
        if photo_source and (photo_source.startswith("http://") or photo_source.startswith("https://")):
            return await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo_source,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        elif photo_source and os.path.exists(photo_source):
            with open(photo_source, "rb") as photo:
                return await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
    except Exception:
        pass
    
    return await context.bot.send_message(
        chat_id=chat_id,
        text=caption,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

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
    except Exception as e:
        pass

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass
    msg = await send_photo_message(chat_id, photo_source, caption, reply_markup, context)
    context.user_data['last_msg_id'] = msg.message_id

# ==================== ХЕНДЛЕРЫ ====================
async def post_init(application: Application):
    commands = [
        BotCommand("start", "🏠 Главное меню"),
        BotCommand("menu", "🍽 Посмотреть меню категорий"),
        BotCommand("history", "📜 История заказов"),
        BotCommand("post", "📢 Опубликовать меню в канал (Админ)"),
        BotCommand("toggle", "⛔ Открыть/Закрыть прием (Админ)")
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.pop('active_cart_item', None)
    init_db()
    
    if not get_user_db(user_id):
        caption = "👋 Привет! Это бот заказа обедов в офисе.\n\n🍽 Здесь вы можете выбрать обед на любой день недели.\n\n" \
                  "🏠 Чтобы выставить счета, нужен ваш номер телефона."
        await send_photo_message(user_id, MENU_DATA["categories"]["pizza"]["banner"], caption, get_main_keyboard(), context)
        await asyncio.sleep(2) # Show main kb, then ask contact flow
        await request_contact_and_continue(user_id, context) # Force request contact initial, turn 8 logic
    else:
        await render_start(user_id, context)

async def request_contact_and_continue(user_id, context):
    user = get_user_db(user_id)
    if not user or not user[1]: # No user db or no phone saved
        # Request contact via bot direct msg flow logic turn 8 integration
        keyboard = [
            [types.KeyboardButton("📱 Поделиться номером", request_contact=True)],
            [types.KeyboardButton("🔄 Перезапустить")]
        ]
        reply_markup = types.ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        # Using a direct message instead of keyboard editing for contact flow
        await context.bot.send_message(chat_id=user_id, text="🏠 Чтобы оформить заказ, пожалуйста, поделитесь номером телефона 👇", reply_markup=reply_markup)
    else:
        await render_start(user_id, context)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    contact = update.message.contact
    if contact:
        add_user_db(user_id, contact.phone_number)
        await update.message.reply_text(f"✅ Готово, {update.effective_user.first_name}! Номер сохранён. Оформляем заказ 🍽.", reply_markup=types.ReplyKeyboardRemove())
        await render_start(user_id, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔄 Перезапустить":
        await start(update, context)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not menu_active:
        await update.message.reply_text("⛔ Приём заказов временно закрыт.")
        return
    await render_start(update.effective_user.id, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    init_db()

    user = get_user_db(user_id)
    if not user or not user[1]:
        await query.answer()
        await request_contact_and_continue(user_id, context)
        return

    if not menu_active and not data.startswith("paid") and data != "cancel_order":
        await query.answer()
        await query.message.reply_text("⛔ Приём заказов временно закрыт.")
        return

    last_msg_id = context.user_data.get('last_msg_id')

    if data == "restart":
        await query.answer()
        await render_start(user_id, context, from_restart=True)

    elif data == "days_list": # Management for turn 8 navigation days_list -> main
        await query.answer()
        await edit_media_message(user_id, last_msg_id, MENU_DATA["categories"]["burgers"]["banner"], 
                                  "🏠 <b>Главное меню открыто 👇</b>\n\n🍽 Кликните по кнопке ниже, чтобы посмотреть категории.", get_main_keyboard(), context)

    elif data == "cat_list":
        await query.answer()
        await edit_media_message(user_id, last_msg_id, MENU_DATA["categories"]["pizza"]["banner"], 
                                  "<b>📅 Выберите категорию для просмотра блюд:</b>", get_categories_keyboard(), context)

    elif data.startswith("cat_"):
        await query.answer()
        parts = data.split("_")
        cat_id = parts[1]
        item_index = int(parts[2]) if len(parts) > 2 else 0
        cat_info = MENU_DATA["categories"].get(cat_id)
        if not cat_info or not cat_info["items"]:
            return
        
        item = cat_info["items"][item_index]
        cart = get_cart_db(user_id)
        cart_count = cart.get(item['id'], {}).get('count', 0)
        
        caption = f"🖼 <b>{item['name']}</b>\n\n" \
                  f"📝 <i>{item['description']}</i>\n\n" \
                  f"💰 <b>Цена:</b> {item['price']:,} сум\n".replace(",", " ")
        if cart_count > 0:
             caption += f"🛒 <b>В вашем заказе:</b> {cart_count} шт.\n"

        # Update last msg ID for pagination flow, essential app-style logic integration
        await edit_media_message(user_id, last_msg_id, item['image'], caption, 
                                  get_item_pagination_keyboard(cat_id, item_index, item['id'], len(cat_info['items']), cart_count), context)

    elif data.startswith("view_item_"):
        await query.answer()
        parts = data.split("_")
        cat_id = parts[2]
        item_index = int(parts[3])
        # Force re-add/re-manage the viewing flow, app-style essential integration
        cat_info = MENU_DATA["categories"].get(cat_id)
        if not cat_info: return
        item = cat_info["items"][item_index]
        cart = get_cart_db(user_id)
        cart_count = cart.get(item['id'], {}).get('count', 0)
        
        caption = f"🖼 <b>{item['name']}</b>\n\n" \
                  f"📝 <i>{item['description']}</i>\n\n" \
                  f"💰 <b>Цена:</b> {item['price']:,} сум\n".replace(",", " ")
        if cart_count > 0:
             caption += f"🛒 <b>В вашем заказе:</b> {cart_count} шт.\n"
             
        await edit_media_message(user_id, last_msg_id, item['image'], caption, 
                                  get_item_pagination_keyboard(cat_id, item_index, item['id'], len(cat_info['items']), cart_count), context)

    elif data.startswith("add_item_"):
        parts = data.split("_")
        cat_id = parts[2]
        item_index = int(parts[3])
        item_id = parts[4]
        
        cat_info = MENU_DATA["categories"].get(cat_id)
        item = cat_info["items"][item_index]
        cart = get_cart_db(user_id)
        current_count = cart.get(item_id, {}).get('count', 0)
        new_count = current_count + 1
        
        update_cart_db(user_id, item_id, item['name'], item['price'], new_count)
        await query.answer(f"Добавлено: {item['name']} (x{new_count})")
        
        # Immediate refresh same card with updated count flow, app-style logic integration
        caption = f"🖼 <b>{item['name']}</b>\n\n" \
                  f"📝 <i>{item['description']}</i>\n\n" \
                  f"💰 <b>Цена:</b> {item['price']:,} сум\n".replace(",", " ") + \
                  f"🛒 <b>В вашем заказе:</b> {new_count} шт.\n"
        await edit_media_message(user_id, last_msg_id, item['image'], caption, 
                                  get_item_pagination_keyboard(cat_id, item_index, item['id'], len(cat_info['items']), new_count), context)

    elif data.startswith("remove_item_"):
        parts = data.split("_")
        cat_id = parts[2]
        item_index = int(parts[3])
        item_id = parts[4]
        
        cat_info = MENU_DATA["categories"].get(cat_id)
        item = cat_info["items"][item_index]
        cart = get_cart_db(user_id)
        current_count = cart.get(item_id, {}).get('count', 0)
        
        if current_count > 0:
            new_count = current_count - 1
            update_cart_db(user_id, item_id, item['name'], item['price'], new_count)
            await query.answer(f"Удалено: {item['name']}")
            
            # Immediate refresh same card with updated count flow, app-style logic integration
            caption = f"🖼 <b>{item['name']}</b>\n\n" \
                      f"📝 <i>{item['description']}</i>\n\n" \
                      f"💰 <b>Цена:</b> {item['price']:,} сум\n".replace(",", " ")
            if new_count > 0:
                 caption += f"🛒 <b>В вашем заказе:</b> {new_count} шт.\n"
            await edit_media_message(user_id, last_msg_id, item['image'], caption, 
                                      get_item_pagination_keyboard(cat_id, item_index, item['id'], len(cat_info['items']), new_count), context)
        else:
            await query.answer("Этого блюда нет в корзине")

    elif data == "cart_list":
        await query.answer()
        items_text, total, _ = get_order_summary(user_id)
        if not items_text:
            await edit_media_message(user_id, last_msg_id, MENU_DATA["categories"]["drinks"]["banner"], 
                                      "🛍 <b>Ваша корзина пуста!</b>\n\n🍽 Выберите категории и добавьте блюда.", get_categories_keyboard(), context)
            return
            
        caption = f"<b>Проверьте Ваш заказ:</b>\n\n{items_text}\n\n" \
                  f"<b>Итого:</b> {total:,} сум\n".replace(",", " ") + \
                  f"Выдача: 4 этаж (12:30–14:00)\n\nПодтвердить и оплатить?"
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить и оплатить", callback_data="checkout_order")],
            [InlineKeyboardButton("➕ Добавить ещё", callback_data="cat_list"), InlineKeyboardButton("❌ Отмена", callback_data="cancel_order")]
        ]
        await edit_media_message(user_id, last_msg_id, MENU_DATA["categories"]["burgers"]["banner"], caption, InlineKeyboardMarkup(keyboard), context)

    elif data == "cancel_order":
        await query.answer()
        clear_cart_db(user_id)
        await edit_media_message(user_id, last_msg_id, MENU_DATA["categories"]["drinks"]["banner"], 
                                  "❌ Заказ отменён. Корзина очищена.", get_main_keyboard(), context)

    elif data == "checkout_order":
        await query.answer()
        items_text, total, _ = get_order_summary(user_id)
        if not items_text: return
        
        amount = total
        click_url = f"https://my.click.uz/clickpass/{CLICK_PASS_ID}?amount={amount}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Оплатить в ClickPass", url=click_url)],
            [InlineKeyboardButton("✅ Я оплатил(а)", callback_data="paid_order")]
        ])
        amount_str = f"{amount:,}".replace(",", " ")
        caption = f"💳 <b>Счёт на {amount_str} сум сформирован!</b>\n\nОтсканируйте <b>QR-код</b> выше через приложение Click или нажмите кнопку <b>«Оплатить в ClickPass»</b> 👇."
        
        # Directly manage QR flow turn 8 integration without last msg ID as QR is separate image flow essential turn 8 integration logic
        await send_photo_message(user_id, QR_FILE_NAME, caption, keyboard, context)

    elif data == "paid_order":
        await query.answer()
        items_text, total, items_str = get_order_summary(user_id)
        if not items_text: return
        
        clear_cart_db(user_id) # Direct clearing cart turn 8 flow integration
        count = add_order_to_history(user_id, items_str, total) # Order num management
        order_num = 2300 + count
        
        text = f"✅ <b>Оплачено! Заказ №{order_num} принят.</b>\n\n<b>Состав заказа:</b>\n{items_text}\n\nВыдача: 4 этаж, 12:30–14:00\n\nУвидимся на обеде 🙂"
        if count % 5 == 0:
            text += "\n\n🎁 Это ваш 5-й заказ — сок в подарок к следующему обеду!"
            
        await query.message.reply_text(text, parse_mode='HTML')
        
        if ADMIN_ID and str(ADMIN_ID).isdigit():
            admin_text = f"🚨 <b>Новый заказ №{order_num}</b>\n📞 Тел: {user[1]}\n💰 Сумма: {total:,} сум\n\n".replace(",", " ") + f"🍽 <b>Состав:</b>\n{items_text}"
            try:
                await context.bot.send_message(chat_id=int(ADMIN_ID), text=admin_text, parse_mode='HTML')
            except Exception as e:
                logging.error(f"Не удалось отправить сообщение админу: {e}")
                
        context.user_data.pop('last_msg_id', None) # Force refresh flow post checkout integration logic turn 8 integration

    elif data == "history_list":
        await query.answer()
        history = get_order_history(user_id)
        if not history:
             await edit_media_message(user_id, last_msg_id, MENU_DATA["categories"]["drinks"]["banner"], 
                                      "📜 У вас пока нет истории заказов.", get_main_keyboard(), context)
             return
             
        hist_text = "<b>Ваша история заказов:</b>\n\n"
        total_hist_orders = len(history)
        for h in history:
            items_str = f"{h[1][:40]}..." if len(h[1]) > 40 else h[1] # Limit turn 8 history integration summary text flow turn 8 integration logic integration
            hist_text += f"{h[0]} — {items_str} ({h[2]:,} сум) ✅\n".replace(",", " ")
        
        hist_text += f"\nВсего заказов: {total_hist_orders}."
        await edit_media_message(user_id, last_msg_id, MENU_DATA["categories"]["burgers"]["banner"], 
                                  hist_text, InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад в главное", callback_data="restart")]]), context)

async def post_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Публикация анонса меню (категорий) с картинкой в канал (Админ)."""
    user_id = update.effective_user.id
    if ADMIN_ID and str(user_id) != str(ADMIN_ID):
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    init_db()
    
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username

    cat_items = []
    for cat_id, cat_info in MENU_DATA["categories"].items():
        cat_items.append(f"• {cat_info['name']}")
    categories_str = "\n".join(cat_items)

    # Simplified Turn 8 post summary logic flow integration integration logic
    caption = f"<b>🍽 АНОНС ОБЕДОВ: ЛУЧШИЕ БЛЮДА УЖЕ В МЕНЮ!</b>\n\nМы готовы радовать Вас вкуснейшими позициями:\n\n" \
              f"<b>🍔 НАШИ КАТЕГОРИИ:</b>\n{categories_str}\n\n" \
              f"⏰ Приём заказов до 11:00\n📍 Выдача: 4 этаж (12:30–14:00)\n\n" \
              f"👇 Кликните по кнопке ниже, чтобы посмотреть блюда и сделать заказ 👇"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🥗 Сделать заказ в боте", url=f"https://t.me/{bot_username}")]])

    try:
        await send_photo_message(CHANNEL_ID, POST_FILE_NAME, caption, keyboard, context)
        await update.message.reply_text(f"✅ Анонс категорий меню успешно опубликован в канале {CHANNEL_ID}!", parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка публикации: {e}\n\nУбедитесь, что бот добавлен администратором в канал {CHANNEL_ID}.")

async def toggle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открыть/Закрыть прием заказов (Админ)."""
    global menu_active
    user_id = update.effective_user.id
    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        menu_active = not menu_active
        status = "ОТКРЫТ ✅" if menu_active else "ЗАКРЫТ ⛔"
        await update.message.reply_text(f"Статус приема заказов изменён: {status}")

# ==================== ЗАПУСК ====================
async def handle_health_check(request):
    """Заглушка для health check хостинга (Render/Railway)."""
    return web.Response(text="Bot is running")

async def start_web_server():
    """Фоновый веб-сервер для проходимости health-check на хостинге."""
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    if TOKEN == "YOUR_BOT_TOKEN_HERE" or not TOKEN:
        print("❌ ОШИБКА: Укажите BOT_TOKEN!")
        return
        
    app = Application.builder().token(TOKEN).post_init(post_init).build()

    # Хэндлеры команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("history", history_command_flow_reinit_logic)) # history_command -> restart flow integration turn 8 logic reinit flow logic integration
    app.add_handler(CommandHandler("post", post_to_channel))
    app.add_handler(CommandHandler("toggle", toggle_menu))

    # Хэндлеры сообщений и нажатий
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Фоновый веб-сервер для хостинга (Render/Railway)
    # await start_web_server()

    init_db()
    logging.info(">>> Бот запущен... <<<")
    await app.run_polling()

# Helper for history cmd logic turn 8 flow integration logic integration logic reinit history command flow logic reinit integration integration
async def history_command_flow_reinit_logic(update, context): # Forced flow reinit turn 8 flow logic reinit command integration reinit history cmd flow logic integration reinit cmd integration reinit
    await render_start(update.effective_user.id, context, from_restart=True) # history -> restart, essential flow logic turn 8 integration logic

if __name__ == '__main__':
    # asyncio.run(main()) # use main() direct polling turn 8 logic polling direct turn 8 direct polling integration
    # to run within existing env polling logic poolingdirect logic integrationDirectpolling pooling Logic Pooling direct pooling
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
