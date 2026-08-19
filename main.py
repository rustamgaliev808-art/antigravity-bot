import os
import logging
import asyncio
from datetime import datetime
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
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

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = os.getenv("ADMIN_ID", "YOUR_TELEGRAM_ID_HERE")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel_username") # Юзернейм или ID канала

CLICK_PASS_ID = "052528"
QR_FILE_NAME = "qr.jpg"
POST_FILE_NAME = "post.jpg"

# База данных в памяти
users_db = {} 
active_orders = {}
menu_active = True

# Меню на неделю с фото и описанием блюд
WEEKLY_MENU = {
    "mon": {
        "name": "Понедельник",
        "banner": "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=800",
        "items": {
            "mon_1": {
                "name": "Курица гриль + рис + салат",
                "price": 63000,
                "desc": "Сочное филе курицы на гриле, рассыпчатый басмати и свежий овощной салат.",
                "image": "https://images.unsplash.com/photo-1598515214211-89d3c73ae83b?w=800"
            },
            "mon_2": {
                "name": "Мясо + картофель + компот",
                "price": 75000,
                "desc": "Нежная тушеная говядина с запеченным картофелем по-домашнему.",
                "image": "https://images.unsplash.com/photo-1544025162-d76694265947?w=800"
            },
            "mon_3": {
                "name": "Сэндвич курица-сыр",
                "price": 25000,
                "desc": "Хрустящий тост с филе курицы, сыром Чеддер и фирменным соусом.",
                "image": "https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=800"
            },
            "mon_4": {
                "name": "Свежевыжатый апельсиновый сок",
                "price": 18000,
                "desc": "100% натуральный свежевыжатый сок из спелых апельсинов.",
                "image": "https://images.unsplash.com/photo-1613478223719-2ab802602423?w=800"
            }
        }
    },
    "tue": {
        "name": "Вторник",
        "banner": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=800",
        "items": {
            "tue_1": {
                "name": "Плов чайханский + Ачик-чучук",
                "price": 65000,
                "desc": "Традиционный узбекский плов с говядиной и салатом из спелых томатов.",
                "image": "https://images.unsplash.com/photo-1633964913295-ceb43826e7c9?w=800"
            },
            "tue_2": {
                "name": "Бефстроганов + пюре + морс",
                "price": 72000,
                "desc": "Классический бефстроганов из говядины со сливочным пюре.",
                "image": "https://images.unsplash.com/photo-1588168333986-5078d3ae3976?w=800"
            },
            "tue_3": {
                "name": "Клаб-сэндвич с индейкой",
                "price": 28000,
                "desc": "Трехслойный сэндвич с индейкой, беконом, томатами и салатом.",
                "image": "https://images.unsplash.com/photo-1567234669003-dce7a7a88821?w=800"
            },
            "tue_4": {
                "name": "Компот из сухофруктов",
                "price": 12000,
                "desc": "Домашний освежающий компот из кураги, изюма и чернослива.",
                "image": "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=800"
            }
        }
    },
    "wed": {
        "name": "Среда",
        "banner": "https://images.unsplash.com/photo-1498837167922-ddd27525d352?w=800",
        "items": {
            "wed_1": {
                "name": "Стейк из лосося + овощи гриль",
                "price": 85000,
                "desc": "Стейк лосося на гриле со свежими кабачками, перцем и баклажанами.",
                "image": "https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?w=800"
            },
            "wed_2": {
                "name": "Паста Карбонара + салат",
                "price": 68000,
                "desc": "Итальянская спагетти с беконом, пармезаном и сливочным соусом.",
                "image": "https://images.unsplash.com/photo-1612874742237-6526221588e3?w=800"
            },
            "wed_3": {
                "name": "Цезарь с креветками",
                "price": 35000,
                "desc": "Салат Романо, тигровые креветки, пармезан и соус Цезарь.",
                "image": "https://images.unsplash.com/photo-1550304943-4f24f54ddde9?w=800"
            },
            "wed_4": {
                "name": "Лимонад домашний",
                "price": 15000,
                "desc": "Натуральный освежающий лимонад с мятой и лимоном.",
                "image": "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=800"
            }
        }
    },
    "thu": {
        "name": "Четверг",
        "banner": "https://images.unsplash.com/photo-1543353071-10c8ba85a904?w=800",
        "items": {
            "thu_1": {
                "name": "Шницель куриный + картофель фри",
                "price": 60000,
                "desc": "Хрустящий куриный шницель в панировке с золотистой картошкой фри.",
                "image": "https://images.unsplash.com/photo-1532550907401-a500c9a57435?w=800"
            },
            "thu_2": {
                "name": "Гуляш из говядины + гречка",
                "price": 70000,
                "desc": "Ароматный гуляш в густом соусе с рассыпчатой гречкой.",
                "image": "https://images.unsplash.com/photo-1544025162-d76694265947?w=800"
            },
            "thu_3": {
                "name": "Ролл с курицей и овощами",
                "price": 27000,
                "desc": "Сочная курица, свежие огурцы, томаты и соус в тортилье.",
                "image": "https://images.unsplash.com/photo-1626700051175-6818013e1d4f?w=800"
            },
            "thu_4": {
                "name": "Морс ягодный",
                "price": 14000,
                "desc": "Натуральный морс из спелых лесных ягод.",
                "image": "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=800"
            }
        }
    },
    "fri": {
        "name": "Пятница",
        "banner": "https://images.unsplash.com/photo-1466978913421-dad2ebd01d17?w=800",
        "items": {
            "fri_1": {
                "name": "Бургер сет + фри + напиток",
                "price": 75000,
                "desc": "Сочный бургер из говядины, картофель фри и прохладительный напиток.",
                "image": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=800"
            },
            "fri_2": {
                "name": "Казан-кабоб из баранины",
                "price": 80000,
                "desc": "Нежная баранина с обжаренным румяным картофелем и луком.",
                "image": "https://images.unsplash.com/photo-1544025162-d76694265947?w=800"
            },
            "fri_3": {
                "name": "Салат Греческий",
                "price": 26000,
                "desc": "Свежие овощи, сыр Фета, маслины и оливковое масло.",
                "image": "https://images.unsplash.com/photo-1540420773420-3366772f4999?w=800"
            },
            "fri_4": {
                "name": "Свежевыжатый яблочный сок",
                "price": 18000,
                "desc": "100% свежевыжатый сок из зеленых яблок.",
                "image": "https://images.unsplash.com/photo-1613478223719-2ab802602423?w=800"
            }
        }
    }
}

def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🍽 Меню"), KeyboardButton("📜 История")],
        [KeyboardButton("🔄 Перезапустить")]
    ], resize_keyboard=True)

def get_item_by_id(item_id):
    for day_data in WEEKLY_MENU.values():
        if item_id in day_data['items']:
            return day_data['items'][item_id]
    return None

def get_days_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Понедельник", callback_data="day_mon"), InlineKeyboardButton("📅 Вторник", callback_data="day_tue")],
        [InlineKeyboardButton("📅 Среда", callback_data="day_wed"), InlineKeyboardButton("📅 Четверг", callback_data="day_thu")],
        [InlineKeyboardButton("📅 Пятница", callback_data="day_fri")]
    ])

def get_order_summary(items_list):
    counts = {}
    for item in items_list:
        name = item['name']
        if name not in counts:
            counts[name] = {'count': 0, 'unit_price': item['price']}
        counts[name]['count'] += 1
    
    formatted_lines = []
    short_lines = []
    for name, data in counts.items():
        cnt = data['count']
        total_price = f"{data['unit_price'] * cnt:,}".replace(",", " ")
        count_str = f" x{cnt}" if cnt > 1 else ""
        formatted_lines.append(f"• {name}{count_str} — {total_price} сум")
        short_lines.append(f"{name}{count_str}")
        
    items_text = "\n".join(formatted_lines)
    items_str = ", ".join(short_lines)
    return items_text, items_str

async def send_photo_message(chat_id, photo_source, caption, reply_markup, context):
    """Вспомогательная функция для отправки фото (URL или локальный файл)"""
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
    else:
        return await context.bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

async def update_photo_or_text(query, photo_source, caption, reply_markup, context):
    """Обновляет текущее сообщение картинкой и текстом"""
    try:
        if photo_source and (photo_source.startswith("http://") or photo_source.startswith("https://")):
            media = InputMediaPhoto(media=photo_source, caption=caption, parse_mode='HTML')
            await query.message.edit_media(media=media, reply_markup=reply_markup)
            return
        elif photo_source and os.path.exists(photo_source):
            with open(photo_source, "rb") as photo:
                media = InputMediaPhoto(media=photo, caption=caption, parse_mode='HTML')
                await query.message.edit_media(media=media, reply_markup=reply_markup)
                return
    except Exception:
        pass

    try:
        await query.message.delete()
    except Exception:
        pass
    await send_photo_message(query.from_user.id, photo_source, caption, reply_markup, context)

async def render_day_menu(query, day_code, user_id):
    order = active_orders[user_id]
    order['day'] = day_code
    day_info = WEEKLY_MENU.get(day_code)
    if not day_info:
        return

    text = f"<b>🍽 Меню на {day_info['name']}</b>\n\n"
    for idx, (item_id, item) in enumerate(day_info['items'].items(), 1):
        text += f"{idx}️⃣ <b>{item['name']}</b>\n💰 {item['price']:,} сум\n".replace(",", " ")

    text += "\n⏰ Приём заказов до 11:00\n📍 Выдача: 4 этаж, 12:30–14:00\n"

    if order['items']:
        items_text, _ = get_order_summary(order['items'])
        text += f"\n🛒 <b>Ваш выбор:</b>\n{items_text}\n\n💰 <b>Итого:</b> {order['total']:,} сум".replace(",", " ")

    keyboard = []
    for idx, (item_id, item) in enumerate(day_info['items'].items(), 1):
        keyboard.append([
            InlineKeyboardButton(f"🖼 №{idx} Фото и описание", callback_data=f"view_{item_id}"),
            InlineKeyboardButton(f"➕ Заказать №{idx}", callback_data=f"add_{item_id}")
        ])

    if order['items']:
        total_count = len(order['items'])
        keyboard.append([InlineKeyboardButton(f"✅ ОФОРМИТЬ ЗАКАЗ ({total_count} шт. — {order['total']:,} сум) ➡️".replace(",", " "), callback_data="checkout")])

    keyboard.append([InlineKeyboardButton("⬅️ Назад к дням", callback_data="days_list")])

    banner = day_info.get("banner")
    await update_photo_or_text(query, banner, text, InlineKeyboardMarkup(keyboard), context)

async def render_item_card(query, item_id, user_id):
    """Показ отдельного блюда с его фото и описанием"""
    item = get_item_by_id(item_id)
    if not item:
        return

    order = active_orders[user_id]
    cnt = sum(1 for i in order['items'] if i['name'] == item['name'])

    caption = (
        f"🖼 <b>{item['name']}</b>\n\n"
        f"<i>{item['desc']}</i>\n\n"
        f"💰 <b>Цена:</b> {item['price']:,} сум\n".replace(",", " ")
    )
    if cnt > 0:
        caption += f"🛒 <b>В вашем заказе:</b> {cnt} шт.\n"

    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить", callback_data=f"add_{item_id}"),
            InlineKeyboardButton("➖ Удалить", callback_data=f"remove_{item_id}")
        ],
        [InlineKeyboardButton("⬅️ Назад к меню дня", callback_data=f"day_{order.get('day', 'mon')}")]
    ]

    await update_photo_or_text(query, item['image'], caption, InlineKeyboardMarkup(keyboard), context)

async def post_init(application: Application):
    commands = [
        BotCommand("start", "🔄 Перезапустить бота"),
        BotCommand("menu", "🍽 Посмотреть меню"),
        BotCommand("history", "📜 История заказов"),
        BotCommand("post", "📢 Опубликовать меню в канал (Админ)")
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in users_db:
        users_db[user_id] = {'phone': None, 'orders_count': 0, 'history': []}

    if not users_db[user_id]['phone']:
        keyboard = [
            [KeyboardButton("📱 Поделиться номером", request_contact=True)],
            [KeyboardButton("Отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            "👋 Привет! Это бот заказа обедов в офисе.\n\n"
            "Здесь вы можете выбрать обед на любой день недели.\n\n"
            "Чтобы выставлять счета, нужен ваш номер телефона.",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("Главное меню открыто 👇", reply_markup=get_main_keyboard())
        await menu_command(update, context)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    contact = update.message.contact
    if contact:
        if user_id not in users_db:
            users_db[user_id] = {'phone': None, 'orders_count': 0, 'history': []}
        users_db[user_id]['phone'] = contact.phone_number
        await update.message.reply_text(
            f"Готово, {update.effective_user.first_name}! Номер сохранён.",
            reply_markup=get_main_keyboard()
        )
        await menu_command(update, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🍽 Меню":
        await menu_command(update, context)
    elif text == "📜 История":
        await history(update, context)
    elif text in ["🔄 Перезапустить", "/start"]:
        await start(update, context)
    elif text == "Отмена":
        keyboard = [[KeyboardButton("📱 Поделиться номером", request_contact=True)]]
        await update.message.reply_text(
            "Чтобы оформить заказ, нужен номер телефона для выставления счёта. Поделиться сейчас?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not menu_active:
        await update.message.reply_text("⛔ Приём заказов временно закрыт.")
        return

    text = "<b>📅 Выберите день недели для просмотра меню и заказа:</b>"
    await update.message.reply_text(text, reply_markup=get_days_keyboard(), parse_mode='HTML')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if user_id not in users_db or not users_db[user_id].get('phone'):
        await query.answer()
        await query.message.reply_text("Пожалуйста, поделитесь номером телефона (команда /start)")
        return

    if not menu_active and not data.startswith("paid") and data != "cancel":
        await query.answer()
        await query.message.reply_text("⛔ Приём заказов временно закрыт.")
        return

    if user_id not in active_orders:
        active_orders[user_id] = {'items': [], 'total': 0, 'day': 'mon'}
    order = active_orders[user_id]

    if data == "days_list":
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=user_id,
            text="<b>📅 Выберите день недели:</b>",
            reply_markup=get_days_keyboard(),
            parse_mode='HTML'
        )

    elif data.startswith("day_"):
        await query.answer()
        day_code = data.split("_")[1]
        await render_day_menu(query, day_code, user_id)

    elif data.startswith("view_"):
        await query.answer()
        item_id = data.split("view_")[1]
        await render_item_card(query, item_id, user_id)

    elif data.startswith("add_"):
        item_id = data.split("add_")[1]
        item = get_item_by_id(item_id)
        if item:
            order['items'].append(item)
            order['total'] += item['price']
            
            cnt = sum(1 for i in order['items'] if i['name'] == item['name'])
            await query.answer(f"Добавлено: {item['name']} (x{cnt})")
            
            # Обновляем либо карточку блюда, либо общее меню дня
            if query.message.caption and "Итого" not in query.message.caption and item['name'] in query.message.caption:
                await render_item_card(query, item_id, user_id)
            else:
                await render_day_menu(query, order.get('day', 'mon'), user_id)

    elif data.startswith("remove_"):
        item_id = data.split("remove_")[1]
        item = get_item_by_id(item_id)
        if item:
            for idx, i in enumerate(order['items']):
                if i['name'] == item['name']:
                    order['items'].pop(idx)
                    order['total'] -= item['price']
                    await query.answer(f"Удалено: {item['name']}")
                    break
            else:
                await query.answer("Этого блюда нет в корзине")
            await render_item_card(query, item_id, user_id)

    elif data == "checkout":
        await query.answer()
        items_text, _ = get_order_summary(order['items'])
        text = (
            f"<b>Проверьте Ваш заказ:</b>\n\n{items_text}\n\n"
            f"<b>Итого:</b> {order['total']:,} сум\n".replace(",", " ") +
            f"<b>Выдача:</b> 4 этаж (12:30–14:00)\n\nПодтвердить и оплатить?"
        )
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm")],
            [InlineKeyboardButton("➕ Добавить ещё", callback_data=f"day_{order.get('day', 'mon')}")],
            [InlineKeyboardButton("❌ Отмена заказа", callback_data="cancel")]
        ]
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data == "cancel":
        await query.answer()
        active_orders.pop(user_id, None)
        await query.message.reply_text("Заказ отменён.")

    elif data == "confirm":
        await query.answer()
        amount = order['total']
        ussd_code = f"*880*{CLICK_PASS_ID}*{amount}#"
        click_url = f"https://my.click.uz/clickpass/{CLICK_PASS_ID}?amount={amount}"

        keyboard = [
            [InlineKeyboardButton("💳 Оплатить в Click", url=click_url)],
            [InlineKeyboardButton("✅ Я оплатил(а)", callback_data="paid")]
        ]
        
        amount_str = f"{amount:,}".replace(",", " ")
        caption = (
            f"💳 <b>Счёт на {amount_str} сум сформирован!</b>\n\n"
            "<b>Способы оплаты:</b>\n\n"
            "1️⃣ Отсканируйте <b>QR-код</b> выше через приложение Click.\n\n"
            "2️⃣ Или нажмите кнопку <b>«Оплатить в Click»</b> ниже.\n\n"
            "3️⃣ Или скопируйте USSD-код:\n"
            f"<code>{ussd_code}</code>\n\n"
            "После оплаты нажмите кнопку <b>«Я оплатил(а)»</b>."
        )

        try:
            await query.message.delete()
        except Exception:
            pass

        await send_photo_message(user_id, QR_FILE_NAME, caption, InlineKeyboardMarkup(keyboard), context)

    elif data == "paid":
        await query.answer()
        if not order.get('items'):
            await query.message.reply_text("Заказ уже обработан или отменен.")
            return

        users_db[user_id]['orders_count'] += 1
        count = users_db[user_id]['orders_count']
        today = datetime.now().strftime("%d.%m")
        
        items_text, items_str = get_order_summary(order['items'])
        
        users_db[user_id]['history'].append(f"{today} — {items_str} ({order['total']:,} сум) ✅".replace(",", " "))
        order_num = 2300 + count
        
        text = (
            f"✅ <b>Оплачено! Заказ №{order_num} принят.</b>\n\n"
            f"<b>Состав заказа:</b>\n{items_text}\n\n"
            f"Выдача: 4 этаж, 12:30–14:00\n\nУвидимся на обеде 🙂"
        )
        if count % 5 == 0:
            text += f"\n\n🎁 Это ваш {count}-й заказ — сок в подарок к следующему обеду!"
            
        await query.message.reply_text(text, parse_mode='HTML')
        
        if ADMIN_ID and str(ADMIN_ID).isdigit():
            admin_text = (
                f"🚨 <b>Новый заказ №{order_num}</b>\n"
                f"📞 Тел: {users_db[user_id]['phone']}\n"
                f"💰 Сумма: {order['total']:,} сум\n\n".replace(",", " ") +
                f"🍽 <b>Состав заказа:</b>\n{items_text}"
            )
            try:
                await context.bot.send_message(chat_id=int(ADMIN_ID), text=admin_text, parse_mode='HTML')
            except Exception as e:
                logging.error(f"Не удалось отправить сообщение админу: {e}")
                
        active_orders.pop(user_id, None)

async def post_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Публикация красивого анонса меню с картинкой в канал"""
    user_id = update.effective_user.id
    if str(user_id) != str(ADMIN_ID):
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    # Определяем текущий день недели по дате (пн = mon, вт = tue и т.д.)
    days_map = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri"}
    current_day = days_map.get(datetime.now().weekday(), "mon")
    
    # Если передан аргумент (например /post tue), используем его
    if context.args:
        arg_day = context.args[0].lower()
        if arg_day in WEEKLY_MENU:
            current_day = arg_day

    day_info = WEEKLY_MENU[current_day]
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username

    caption = f"<b>🍽 АНОНС ОБЕДОВ: {day_info['name'].upper()}!</b>\n\n"
    for idx, (item_id, item) in enumerate(day_info['items'].items(), 1):
        caption += f"{idx}️⃣ <b>{item['name']}</b> — {item['price']:,} сум\n<i>{item['desc']}</i>\n\n".replace(",", " ")

    caption += (
        "⏰ <b>Приём заказов до 11:00</b>\n"
        "📍 <b>Выдача:</b> 4 этаж (12:30–14:00)\n\n"
        "👇 <i>Нажмите кнопку ниже, чтобы оформить заказ:</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥗 Сделать заказ в боте", url=f"https://t.me/{bot_username}")]
    ])

    # Испольуем баннер дня или локальный post.jpg
    photo_to_send = POST_FILE_NAME if os.path.exists(POST_FILE_NAME) else day_info['banner']

    try:
        await send_photo_message(CHANNEL_ID, photo_to_send, caption, keyboard, context)
        await update.message.reply_text(f"✅ Пост с картинкой на <b>{day_info['name']}</b> успешно опубликован в канале!", parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка публикации: {e}\n\nУбедитесь, что бот добавлен администратором в {CHANNEL_ID}.")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in users_db or not users_db[user_id].get('history'):
        await update.message.reply_text("У вас пока нет заказов.")
        return
        
    hist = users_db[user_id]['history']
    count = users_db[user_id]['orders_count']
    rem = 5 - (count % 5)
    
    text = "<b>Ваши заказы:</b>\n\n" + "\n".join(hist) + f"\n\nВсего заказов: {count}.\nДо следующего бонуса: {rem} заказов."
    await update.message.reply_text(text, parse_mode='HTML')

async def toggle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global menu_active
    user_id = update.effective_user.id
    if str(user_id) == str(ADMIN_ID):
        menu_active = not menu_active
        status = "ОТКРЫТ ✅" if menu_active else "ЗАКРЫТ ⛔"
        await update.message.reply_text(f"Статус приёма заказов изменён: {status}")

def main():
    if TOKEN == "YOUR_BOT_TOKEN_HERE" or not TOKEN:
        logging.error("Укажите BOT_TOKEN!")
        return
        
    app = Application.builder().token(TOKEN).post_init(post_init).build()

    # Хэндлеры команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("toggle", toggle_menu))
    app.add_handler(CommandHandler("post", post_to_channel))

    # Хэндлеры сообщений и нажатий
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))

    logging.info("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()
