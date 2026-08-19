import asyncio
import logging
import os
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Получение токена из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

# ==================== БАЗА ДАННЫХ МЕНЮ ====================
MENU_DATA = {
    "days": {
        "mon": {
            "title": "📅 Понедельник",
            "items": [
                {"name": "Суп-харчо с говядиной", "description": "Пряный суп с рисом и специями.", "price": "35 000 сум", "image": "https://picsum.photos/400/300?random=101"},
                {"name": "Ташкентский плов", "description": "Традиционный плов с говядиной и нутом.", "price": "45 000 сум", "image": "https://picsum.photos/400/300?random=102"}
            ]
        },
        "tue": {
            "title": "📅 Вторник",
            "items": [
                {"name": "Грибной крем-суп", "description": "Нежный суп с шампиньонами и сухариками.", "price": "32 000 сум", "image": "https://picsum.photos/400/300?random=103"},
                {"name": "Куриный шницель с пюре", "description": "Шницель с картофельным пюре.", "price": "40 000 сум", "image": "https://picsum.photos/400/300?random=104"}
            ]
        },
        "wed": {
            "title": "📅 Среда",
            "items": [
                {"name": "Борщ сибирский", "description": "Классический сытный борщ со сметаной.", "price": "35 000 сум", "image": "https://picsum.photos/400/300?random=105"},
                {"name": "Мясо по-французски", "description": "Запеченная говядина под сыром.", "price": "48 000 сум", "image": "https://picsum.photos/400/300?random=106"}
            ]
        },
        "thu": {
            "title": "📅 Четверг",
            "items": [
                {"name": "Уха из лосося", "description": "Ароматная уха с рыбой и зеленью.", "price": "38 000 сум", "image": "https://picsum.photos/400/300?random=107"},
                {"name": "Рыбное филе с рисом", "description": "Запеченная рыба с овощами и рисом.", "price": "42 000 сум", "image": "https://picsum.photos/400/300?random=108"}
            ]
        },
        "fri": {
            "title": "📅 Пятница",
            "items": [
                {"name": "Лагман уйгурский", "description": "Лапша с сочным мясом и овощным соусом.", "price": "42 000 сум", "image": "https://picsum.photos/400/300?random=109"},
                {"name": "Люля-кебаб с гарниром", "description": "Сочный кебаб из рубленой говядины.", "price": "44 000 сум", "image": "https://picsum.photos/400/300?random=110"}
            ]
        },
        "sat": {
            "title": "📅 Суббота",
            "items": [
                {"name": "Солянка мясная сборная", "description": "Густой суп с мясными деликатесами.", "price": "39 000 сум", "image": "https://picsum.photos/400/300?random=111"},
                {"name": "Бефстроганов с гречкой", "description": "Говядина в сливочном соусе.", "price": "46 000 сум", "image": "https://picsum.photos/400/300?random=112"}
            ]
        },
        "sun": {
            "title": "📅 Воскресенье",
            "items": [
                {"name": "Сырный суп с курицей", "description": "Бархатистый суп с филе.", "price": "34 000 сум", "image": "https://picsum.photos/400/300?random=113"},
                {"name": "Куриные рулетики с сыром", "description": "Запеченные рулетики с сыром.", "price": "42 000 сум", "image": "https://picsum.photos/400/300?random=114"}
            ]
        }
    },
    "breakfast_snacks": [
        {"name": "Овсяная каша с ягодами", "description": "Каша на молоке с ягодами и медом.", "price": "20 000 сум", "image": "https://picsum.photos/400/300?random=201"},
        {"name": "Сырники со сметаной", "description": "Творожные сырники со сметаной или джемом.", "price": "25 000 сум", "image": "https://picsum.photos/400/300?random=202"},
        {"name": "Классический клаб-сэндвич", "description": "Тосты с курицей, сыром и томатами.", "price": "30 000 сум", "image": "https://picsum.photos/400/300?random=203"}
    ],
    "drinks": {
        "hot": [
            {"name": "Американо / Капучино", "description": "Ароматный свежесваренный кофе.", "price": "20 000 сум", "image": "https://picsum.photos/400/300?random=301"},
            {"name": "Латте Макиато", "description": "Кофейный напиток с пышной пеной.", "price": "24 000 сум", "image": "https://picsum.photos/400/300?random=302"}
        ],
        "cold": [
            {"name": "Домашний лимонад Цитрус-Мята", "description": "Освежающий лимонад (400 мл).", "price": "25 000 сум", "image": "https://picsum.photos/400/300?random=304"},
            {"name": "Айс-Латте", "description": "Холодный кофе с молоком и льдом.", "price": "25 000 сум", "image": "https://picsum.photos/400/300?random=305"}
        ]
    }
}

# ==================== КЛАВИАТУРЫ ====================

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Меню по дням")],
        [KeyboardButton(text="🍳 Завтраки и снеки"), KeyboardButton(text="☕ Напитки")]
    ],
    resize_keyboard=True
)

days_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Понедельник"), KeyboardButton(text="Вторник")],
        [KeyboardButton(text="Среда"), KeyboardButton(text="Четверг")],
        [KeyboardButton(text="Пятница"), KeyboardButton(text="Суббота")],
        [KeyboardButton(text="Воскресенье")],
        [KeyboardButton(text="⬅️ Главное меню")]
    ],
    resize_keyboard=True
)

drinks_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔥 Горячие напитки"), KeyboardButton(text="🧊 Холодные напитки")],
        [KeyboardButton(text="⬅️ Главное меню")]
    ],
    resize_keyboard=True
)

# ==================== ИНИЦИАЛИЗАЦИЯ ====================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def send_menu_cards(message: types.Message, items: list, title: str):
    await message.answer(f"<b>=== {title} ===</b>", parse_mode="HTML")
    for item in items:
        caption = f"<b>{item['name']}</b>\n\n📝 <i>{item['description']}</i>\n\n💰 <b>Цена:</b> {item['price']}"
        try:
            await message.answer_photo(photo=item['image'], caption=caption, parse_mode="HTML")
        except Exception:
            await message.answer(caption, parse_mode="HTML")

@dp.message(CommandStart())
@dp.message(F.text == "⬅️ Главное меню")
async def start_handler(message: types.Message):
    await message.answer("Добро пожаловать в наше меню! Выберите раздел:", reply_markup=main_kb)

@dp.message(F.text == "📅 Меню по дням")
async def show_days_keyboard(message: types.Message):
    await message.answer("Выберите день недели:", reply_markup=days_kb)

@dp.message(F.text == "☕ Напитки")
async def show_drinks_keyboard(message: types.Message):
    await message.answer("Выберите категорию напитков:", reply_markup=drinks_kb)

DAY_MAP = {"Понедельник": "mon", "Вторник": "tue", "Среда": "wed", "Четверг": "thu", "Пятница": "fri", "Суббота": "sat", "Воскресенье": "sun"}

@dp.message(F.text.in_(DAY_MAP.keys()))
async def handle_days(message: types.Message):
    day_key = DAY_MAP[message.text]
    await send_menu_cards(message, MENU_DATA["days"][day_key]["items"], f"Меню на {message.text}")

@dp.message(F.text == "🍳 Завтраки и снеки")
async def handle_breakfasts(message: types.Message):
    await send_menu_cards(message, MENU_DATA["breakfast_snacks"], "Завтраки и снеки")

@dp.message(F.text == "🔥 Горячие напитки")
async def handle_hot_drinks(message: types.Message):
    await send_menu_cards(message, MENU_DATA["drinks"]["hot"], "Горячие напитки")

@dp.message(F.text == "🧊 Холодные напитки")
async def handle_cold_drinks(message: types.Message):
    await send_menu_cards(message, MENU_DATA["drinks"]["cold"], "Холодные напитки")

# ==================== ЗАГЛУШКА ДЛЯ ВЕБ-ПОРТА (HEALTH CHECK) ====================

async def handle_health_check(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# ==================== ЗАПУСК ====================

async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN" or not BOT_TOKEN:
        print("❌ ОШИБКА: Задайте переменную BOT_TOKEN в настройках хостинга!")
        return

    # Запускаем фоновый веб-сервер для проходимости health-check на хостинге
    await start_web_server()
    print(">>> Бот запущен! <<<")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
