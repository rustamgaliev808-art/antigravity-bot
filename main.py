import os
import logging
import asyncio
from datetime import datetime
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

# Временная память 
users_db = {} 
active_orders = {}
menu_active = True

MENU_ITEMS = {
    "1": {"name": "Курица гриль + рис + салат", "price": 63000},
    "2": {"name": "Мясо + картофель + компот", "price": 75000},
    "3": {"name": "Сэндвич курица-сыр", "price": 25000},
    "4": {"name": "Свежевыжатый сок (апельсин)", "price": 18000}
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in users_db:
        users_db[user_id] = {'phone': None, 'orders_count': 0, 'history': []}

    if not users_db[user_id]['phone']:
        keyboard = [[KeyboardButton("📱 Поделиться номером", request_contact=True)], [KeyboardButton("Отмена")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            "👋 Привет! Это бот заказа обедов в офисе Click.\n\n"
            "Каждый день в 8:30 здесь появляется меню. Выбираете блюдо — "
            "бот выставляет счёт через Click — оплачиваете — забираете на "
            "4 этаже в указанное время.\n\n"
            "Чтобы выставлять счета, нужен ваш номер телефона (тот же, что привязан к Click).",
            reply_markup=reply_markup
        )
    else:
        await menu_command(update, context)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    contact = update.message.contact
    if contact:
        if user_id not in users_db:
            users_db[user_id] = {'phone': None, 'orders_count': 0, 'history': []}
        users_db[user_id]['phone'] = contact.phone_number
        await update.message.reply_text(
            f"Готово, {update.effective_user.first_name}! Номер сохранён.\nМеню на сегодня уже ниже 👇 (или нажмите /menu)",
            reply_markup=ReplyKeyboardRemove()
        )
        await menu_command(update, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Отмена":
        keyboard = [[KeyboardButton("📱 Поделиться номером", request_contact=True)], [KeyboardButton("Отмена")]]
        await update.message.reply_text(
            "Чтобы оформить заказ, нужен номер телефона для выставления счёта в Click. Поделиться сейчас?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not menu_active:
        await update.message.reply_text("⛔ Приём заказов на сегодня закрыт.\nСледующее меню — завтра в 8:30.")
        return

    text = (
        "🍽 **Меню на сегодня**\n\n"
        "1️⃣ Курица гриль + рис + салат — 63 000 сум\n"
        "2️⃣ Мясо + картофель + компот — 75 000 сум\n"
        "3️⃣ Сэндвич курица-сыр — 25 000 сум\n"
        "4️⃣ Свежевыжатый сок (апельсин) — 18 000 сум\n\n"
        "⏰ Приём заказов до 11:00\n📍 Выдача: 4 этаж, 12:30–14:00"
    )
    keyboard = [
        [InlineKeyboardButton("Заказать №1", callback_data="add_1"), InlineKeyboardButton("Заказать №2", callback_data="add_2")],
        [InlineKeyboardButton("Заказать №3", callback_data="add_3"), InlineKeyboardButton("Заказать №4", callback_data="add_4")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if user_id not in users_db or not users_db[user_id].get('phone'):
        await query.message.reply_text("Пожалуйста, поделитесь номером телефона (команда /start)")
        return

    if not menu_active and not data.startswith("paid") and data != "cancel":
        await query.message.reply_text("⛔ Приём заказов на сегодня закрыт.")
        return

    if user_id not in active_orders:
        active_orders[user_id] = {'items': [], 'floor': None, 'total': 0}
    order = active_orders[user_id]

    if data.startswith("add_"):
        item_id = data.split("_")[1]
        item = MENU_ITEMS[item_id]
        order['items'].append(item)
        order['total'] += item['price']
        
        keyboard = [
            [InlineKeyboardButton("1 этаж", callback_data="floor_1"), InlineKeyboardButton("2 этаж", callback_data="floor_2")],
            [InlineKeyboardButton("3 этаж", callback_data="floor_3"), InlineKeyboardButton("4 этаж (заберу сам)", callback_data="floor_4")]
        ]
        await query.message.reply_text(
            f"{item['name']} — {item['price']} сум\n\nЭтаж выдачи:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("floor_"):
        floor_num = data.split("_")[1]
        order['floor'] = floor_num + " этаж" if floor_num != "4" else "4 этаж (заберу сам)"
        
        items_text = "\n".join([f"{i['name']} — {i['price']} сум" for i in order['items']])
        text = f"Проверьте заказ:\n\n{items_text}\n\nИтого: {order['total']} сум\nВыдача: {order['floor']}, ~12:30–14:00\n\nПодтвердить и оплатить?"
        
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm")],
            [InlineKeyboardButton("➕ Добавить ещё", callback_data="add_more")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
        ]
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "add_more":
        keyboard = [
            [InlineKeyboardButton("Заказать №1", callback_data="add_1"), InlineKeyboardButton("Заказать №2", callback_data="add_2")],
            [InlineKeyboardButton("Заказать №3", callback_data="add_3"), InlineKeyboardButton("Заказать №4", callback_data="add_4")]
        ]
        await query.message.reply_text("Что еще добавить к заказу?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "cancel":
        active_orders.pop(user_id, None)
        await query.message.reply_text("Заказ отменён. Если передумаете — меню доступно до 11:00.")

    elif data == "confirm":
        await query.message.reply_text("⏳ Выставляю счёт в Click...")
        await asyncio.sleep(2) # Эмуляция задержки API
        
        keyboard = [[InlineKeyboardButton("💳 Я оплатил(а) (Тест)", callback_data="paid")]]
        await query.message.reply_text(
            f"💳 Счёт на {order['total']} сум выставлен.\n\n"
            "Откройте Click → уведомления → оплатите счёт.\n"
            "Как только оплата пройдёт, я подтвержу заказ здесь.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "paid":
        if not order.get('items'):
            await query.message.reply_text("Заказ уже обработан или отменен.")
            return

        users_db[user_id]['orders_count'] += 1
        count = users_db[user_id]['orders_count']
        today = datetime.now().strftime("%d.%m")
        items_str = " + ".join([i['name'].split(" + ")[0] for i in order['items']])
        
        users_db[user_id]['history'].append(f"{today} — {items_str} ({order['total']} сум) ✅")
        order_num = 2300 + count
        
        text = f"✅ Оплачено! Заказ №{order_num} принят.\n\n{items_str}\nВыдача: {order['floor']}, 12:30–14:00\n\nУвидимся на обеде 🙂"
        if count % 5 == 0:
            text += f"\n\n🎁 Это ваш {count}-й заказ — держите сок в подарок к следующему обеду. Просто скажите об этом на выдаче."
            
        await query.message.reply_text(text)
        
        if ADMIN_ID:
            admin_text = f"🚨 **Новый заказ №{order_num}**\n📞 Тел: {users_db[user_id]['phone']}\n🏢 Этаж: {order['floor']}\n💰 Сумма: {order['total']}\n🍽 Блюда: {items_str}"
            try:
                await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text)
            except Exception:
                pass
                
        active_orders.pop(user_id, None)

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in users_db or not users_db[user_id].get('history'):
        await update.message.reply_text("У вас пока нет заказов.")
        return
        
    hist = users_db[user_id]['history']
    count = users_db[user_id]['orders_count']
    rem = 5 - (count % 5)
    
    text = "Ваши заказы:\n" + "\n".join(hist) + f"\n\nВсего заказов: {count}. До следующего бонуса: {rem} заказа."
    await update.message.reply_text(text)

def main():
    if not TOKEN:
        return
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()

if __name__ == '__main__':
    main()
