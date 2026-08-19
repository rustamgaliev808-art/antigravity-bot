import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Включаем логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Получаем настройки
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Состояния для записи
NAME, PHONE, WORKOUT = range(3)

def get_main_keyboard():
    keyboard = [
        ["📅 Расписание и Прайс", "🤸‍♀️ Направления"],
        ["🧘‍♀️ Новичкам", "📝 Записаться"],
        ["📢 Сделать анонс в канал"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот студии фитнеса и йоги в гамаках «Антигравити». Выберите нужный раздел в меню ниже 👇",
        reply_markup=get_main_keyboard()
    )

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id
    
    if text == "📅 Расписание и Прайс":
        await update.message.reply_text(
            "📅 **Актуальное расписание:**\n"
            "ПН, СР, ПТ:\n"
            "18:00 - Аэройога (Новички)\n"
            "19:30 - Аэростретчинг\n\n"
            "ВТ, ЧТ:\n"
            "18:30 - Силовая в гамаках\n\n"
            "💰 **Прайс-лист:**\n"
            "Разовое занятие - 800 руб.\n"
            "Абонемент 4 занятия - 2800 руб.",
            parse_mode='Markdown'
        )
    elif text == "🤸‍♀️ Направления":
        await update.message.reply_text(
            "🧘‍♀️ **Аэройога** - классическая йога в гамаке.\n"
            "🤸‍♀️ **Аэростретчинг** - глубокая растяжка в воздухе.\n"
            "💪 **Силовая в гамаках** - интенсивная тренировка."
        )
    elif text == "🧘‍♀️ Новичкам":
        await update.message.reply_text(
            "👕 **Что надеть?** Удобную облегающую форму без молний (чтобы не повредить гамак). Занимаемся в носочках.\n"
            "⚠️ **Противопоказания:** Беременность, гипертония, недавние травмы.\n"
            "🔒 **Безопасность:** Гамаки выдерживают до 200 кг, тренеры всегда рядом!"
        )
    elif text == "📝 Записаться":
        await update.message.reply_text("Отлично! Как к вам обращаться? (Напишите ваше имя)")
        return NAME
    elif text == "📢 Сделать анонс в канал":
        if str(user_id) == str(ADMIN_ID):
            await update.message.reply_text("Напишите текст анонса. Я сразу перешлю его в наш канал.")
            return "ANNOUNCE"
        else:
            await update.message.reply_text("У вас нет прав администратора для этой команды.")
    else:
        await update.message.reply_text("Пожалуйста, используйте кнопки меню.")
    return ConversationHandler.END

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Напишите ваш номер телефона для связи:")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    await update.message.reply_text("На какую тренировку и в какое время вы хотите записаться?")
    return WORKOUT

async def get_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    workout = update.message.text
    name = context.user_data.get('name')
    phone = context.user_data.get('phone')
    username = update.message.from_user.username
    user_link = f"@{username}" if username else "Скрыт"
    
    admin_text = f"🚨 **Новая заявка!**\n👤 Имя: {name}\n📞 Тел: {phone}\n🏋️ Занятие: {workout}\n💬 Telegram: {user_link}"
    
    if ADMIN_ID:
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text)
        except Exception:
            pass
            
    await update.message.reply_text("✅ Заявка отправлена! Администратор скоро свяжется с вами.", reply_markup=get_main_keyboard())
    return ConversationHandler.END

async def get_announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if CHANNEL_ID:
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=text)
            await update.message.reply_text("✅ Анонс опубликован в канале!", reply_markup=get_main_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка публикации: {e}", reply_markup=get_main_keyboard())
    return ConversationHandler.END

def main():
    if not TOKEN:
        return
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 Записаться$"), handle_menu)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            WORKOUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_workout)],
        },
        fallbacks=[]
    )

    announce_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 Сделать анонс"), handle_menu)],
        states={"ANNOUNCE": [MessageHandler(filters.TEXT & ~filters.COMMAND, get_announce)]},
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(announce_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))

    app.run_polling()

if __name__ == '__main__':
    main()
