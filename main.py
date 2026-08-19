import os
import logging
import asyncio
from datetime import datetime
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") and os.getenv("ADMIN_ID").isdigit() else os.getenv("ADMIN_ID")

# Хранение данных в памяти
users_db = {} 
active_orders = {}
menu_active = True

# Меню по дням недели
WEEKLY_MENU = {
    "mon": {
        "name": "Понедельник",
        "items": {
            "mon_1": {"name": "Курица гриль + рис + салат", "price": 63000},
            "mon_2": {"name": "Мясо + картофель + компот", "price": 75000},
            "mon_3": {"name": "Сэндвич курица-сыр", "price": 25000},
            "mon_4": {"name": "Свежевыжатый сок (апельсин)", "price": 18000}
        }
    },
    "tue": {
        "name": "Вторник",
        "items": {
            "tue_1": {"name": "Плов чайханский + салат Ачик-чучук", "price": 65000},
            "tue_2": {"name": "Бефстроганов + пюре + морс", "price": 72000},
            "tue_3": {"name": "Клаб-сэндвич с индейкой", "price": 28000},
            "tue_4": {"name": "Компот из сухофруктов", "price": 12000}
        }
    },
    "wed": {
        "name": "Среда",
        "items": {
            "wed_1": {"name": "Стейк из лосося + овощи гриль", "price": 85000},
            "wed_2": {"name": "Паста Карбонара + салат", "price": 68000},
            "wed_3": {"name": "Цезарь с креветками", "price": 35000},
            "wed_4": {"name": "Лимонад домашний", "price": 15000}
        }
    },
    "thu": {
        "name": "Четверг",
        "items": {
            "thu_1": {"name": "Шницель куриный + картофель фри", "price": 60000},
            "thu_2": {"name": "Гуляш из говядины + гречка", "price": 70000},
            "thu_3": {"name": "Ролл с курицей и овощами", "price": 27000},
            "thu_4": {"name": "Морс ягодный", "price": 14000}
        }
    },
    "fri": {
        "name": "Пятница",
        "items": {
            "fri_1": {"name": "Бургер сет + фри + напиток", "price": 75000},
            "fri_2": {"name": "Казан-кабоб из баранины", "price": 80000},
            "fri_3": {"name": "Салат Греческий", "price": 26000},
            "fri_4": {"name": "Свежевыжатый яблочный сок", "price": 18000}
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

async def render_day_menu(query, day_code, user_id):
    """Отображает меню конкретного дня и текущую корзину без перехода на другой экран"""
    order = active_orders[user_id]
    order['day'] = day_code
    day_info = WEEKLY_MENU.get(day_code)
    if not day_info:
        return

    text = f"<b>🍽 Меню на {day_info['name']}</b>\n\n"
    for idx, (item_id, item) in enumerate(day_info['items'].items(), 1):
        text += f"{idx}️⃣ {item['name']} — {item['price']:,} сум\n".replace(",", " ")

    text += "\n⏰ Приём заказов до 11:00\n📍 Выдача: 4 этаж, 12:30–14:00\n"

    # Выводим текущую корзину прямо под меню дня
    if order['items']:
        items_text, _ = get_order_summary(order['items'])
        text += f"\n🛒 <b>Ваш выбор:</b>\n{items_text}\n\n💰 <b>Итого:</b> {order['total']:,} сум".replace(",", " ")

    keyboard = []
    row = []
    for idx, (item_id, item) in enumerate(day_info['items'].items(), 1):
        row.append(InlineKeyboardButton(f"+ Заказать №{idx}", callback_data=f"add_{item_id}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    if order['items']:
        keyboard.append([InlineKeyboardButton(f"🛒 Перейти к оформлению ({order['total']:,} сум)".replace(",", " "), callback_data="checkout")])

    keyboard.append([InlineKeyboardButton("⬅️ Назад к дням", callback_data="days_list")])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def post_init(application: Application):
    commands = [
        BotCommand("start", "🔄 Перезапустить бота"),
        BotCommand("menu", "🍽 Посмотреть меню"),
        BotCommand("history", "📜 История заказов")
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
        await query.message.edit_text("<b>📅 Выберите день недели:</b>", reply_markup=get_days_keyboard(), parse_mode='HTML')

    elif data.startswith("day_"):
        await query.answer()
        day_code = data.split("_")[1]
        await render_day_menu(query, day_code, user_id)

    elif data.startswith("add_"):
        item_id = data.split("add_")[1]
        item = get_item_by_id(item_id)
        if item:
            order['items'].append(item)
            order['total'] += item['price']
            
            # Подсчет добавленного товара для всплывающего уведомления
            cnt = sum(1 for i in order['items'] if i['name'] == item['name'])
            await query.answer(f"Добавлено: {item['name']} (x{cnt})")
            
            # Обновляем это же сообщение с новым выбором
            await render_day_menu(query, order.get('day', 'mon'), user_id)

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
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data == "cancel":
        await query.answer()
        active_orders.pop(user_id, None)
        await query.message.reply_text("Заказ отменён.")

    elif data == "confirm":
        await query.answer()
        await query.message.reply_text("⏳ Выставляю счёт...")
        await asyncio.sleep(1.5)
        
        keyboard = [[InlineKeyboardButton("💳 Я оплатил(а) (Тест)", callback_data="paid")]]
        await query.message.reply_text(
            f"💳 Счёт на {order['total']:,} сум выставлен.\n\n".replace(",", " ") +
            "Откройте приложение для оплаты → уведомления → оплатите счёт.\n"
            "Как только оплата пройдёт, нажмите кнопку ниже.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

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
        
        if ADMIN_ID:
            admin_text = (
                f"🚨 <b>Новый заказ №{order_num}</b>\n"
                f"📞 Тел: {users_db[user_id]['phone']}\n"
                f"💰 Сумма: {order['total']:,} сум\n\n".replace(",", " ") +
                f"🍽 <b>Состав заказа:</b>\n{items_text}"
            )
            try:
                await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode='HTML')
            except Exception as e:
                logging.error(f"Не удалось отправить сообщение админу: {e}")
                
        active_orders.pop(user_id, None)

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
    if not TOKEN:
        logging.error("BOT_TOKEN не найден в переменных окружения!")
        return
        
    app = Application.builder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("toggle", toggle_menu))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()

if __name__ == '__main__':
    main()
