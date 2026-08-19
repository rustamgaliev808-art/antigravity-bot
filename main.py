import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ==================== НАСТРОЙКИ ====================
# Вставьте сюда ваш токен от @BotFather
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== БАЗА ДАННЫХ МЕНЮ ====================
# Вы можете менять названия, описания, цены и ссылки на фото
MENU_DATA = {
    "days": {
        "mon": {
            "title": "📅 Понедельник",
            "items": [
                {
                    "name": "Суп-харчо с говядиной",
                    "description": "Пряный суп с рисом, томатами, зеленью и восточными специями.",
                    "price": "35 000 сум",
                    "image": "https://picsum.photos/400/300?random=101"
                },
                {
                    "name": "Ташкентский плов",
                    "description": "Традиционный плов с говядиной, нутом, казы и желтой морковью.",
                    "price": "45 000 сум",
                    "image": "https://picsum.photos/400/300?random=102"
                }
            ]
        },
        "tue": {
            "title": "📅 Вторник",
            "items": [
                {
                    "name": "Грибной крем-суп",
                    "description": "Нежный суп из свежих шампиньонов со сливками и хрустящими сухариками.",
                    "price": "32 000 сум",
                    "image": "https://picsum.photos/400/300?random=103"
                },
                {
                    "name": "Куриный шницель с пюре",
                    "description": "Сочный куриный шницель в золотистой панировке с картофельным пюре.",
                    "price": "40 000 сум",
                    "image": "https://picsum.photos/400/300?random=104"
                }
            ]
        },
        "wed": {
            "title": "📅 Среда",
            "items": [
                {
                    "name": "Борщ сибирский",
                    "description": "Классический сытный борщ с мясом, подается со сметаной.",
                    "price": "35 000 сум",
                    "image": "https://picsum.photos/400/300?random=105"
                },
                {
                    "name": "Мясо по-французски",
                    "description": "Запеченная говядина под грибами, луком и сырной корочкой.",
                    "price": "48 000 сум",
                    "image": "https://picsum.photos/400/300?random=106"
                }
            ]
        },
        "thu": {
            "title": "📅 Четверг",
            "items": [
                {
                    "name": "Уха из лосося",
                    "description": "Ароматная уха с кусочками лосося, картофелем и зеленью.",
                    "price": "38 000 сум",
                    "image": "https://picsum.photos/400/300?random=107"
                },
                {
                    "name": "Рыбное филе с рисом",
                    "description": "Нежная запеченная рыба с овощами и рассыпчатым рисом.",
                    "price": "42 000 сум",
                    "image": "https://picsum.photos/400/300?random=108"
                }
            ]
        },
        "fri": {
            "title": "📅 Пятница",
            "items": [
                {
                    "name": "Лагман уйгурский",
                    "description": "Тянутая вручную лапша с сочным мясом и овощным соусом сай.",
                    "price": "42 000 сум",
                    "image": "https://picsum.photos/400/300?random=109"
                },
                {
                    "name": "Люля-кебаб с гарниром",
                    "description": "Сочный кебаб из рубленой говядины с маринованным луком.",
                    "price": "44 000 сум",
                    "image": "https://picsum.photos/400/300?random=110"
                }
            ]
        },
        "sat": {
            "title": "📅 Суббота",
            "items": [
                {
                    "name": "Солянка мясная сборная",
                    "description": "Густой наваристый суп с несколькими видами мясных деликатесов.",
                    "price": "39 000 сум",
                    "image": "https://picsum.photos/400/300?random=111"
                },
                {
                    "name": "Бефстроганов с гречкой",
                    "description": "Нежные полоски говядины в сливочно-томатном соусе.",
                    "price": "46 000 сум",
                    "image": "https://picsum.photos/400/300?random=112"
                }
            ]
        },
        "sun": {
            "title": "📅 Воскресенье",
            "items": [
                {
                    "name": "Сырный суп с курицей",
                    "description": "Бархатистый сырный суп с кусочками нежного куриного филе.",
                    "price": "34 000 сум",
                    "image": "https://picsum.photos/400/300?random=113"
                },
                {
                    "name": "Куриные рулетики с сыром",
                    "description": "Запеченное рулетики из филе с начинкой из сыра и зелени.",
                    "price": "42 000 сум",
                    "image": "https://picsum.photos/400/300?random=114"
                }
            ]
        }
    },
    "breakfast_snacks": [
        {
            "name": "Овсяная каша с ягодами",
            "description": "Нежная овсяная каша на молоке с добавлением свежих ягод и меда.",
            "price": "20 000 сум",
            "image": "https://picsum.photos/400/300?random=201"
        },
        {
            "name": "Сырники со сметаной",
            "description": "Домашние творожные сырники, подаются со сметаной или джемом.",
            "price": "25 000 сум",
            "image": "https://picsum.photos/400/300?random=202"
        },
        {
            "name": "Классический клаб-сэндвич",
            "description": "Хрустящие тосты с курицей, сыром, ветчиной, свежими томатами и соусом.",
            "price": "30 000 сум",
            "image": "https://picsum.photos/400/300?random=203"
        }
    ],
    "drinks": {
        "hot": [
            {
                "name": "Американо / Капучино",
                "description": "Ароматный свежесваренный кофе (200 / 250 мл).",
                "price": "20 000 сум",
                "image": "https://picsum.photos/400/300?random=301"
            },
            {
                "name": "Латте Макиато",
                "description": "Мягкий кофейный напиток с пышной молочной пеной (300 мл).",
                "price": "24 000 сум",
                "image": "https://picsum.photos/400/300?random=302"
            },
            {
                "name": "Авторский чай (Имбирь-Лимон)",
                "description": "Согревающий сортовой чай с добавлением лимона, имбиря и меда.",
                "price": "18 000 сум",
                "image": "https://picsum.photos/400/300?random=303"
            }
        ],
        "cold": [
            {
                "name": "Домашний лимонад Цитрус-Мята",
                "description": "Освежающий лимонад собственного приготовления (400 мл).",
                "price": "25 000 сум",
                "image": "https://picsum.photos/400/300?random=304"
            },
            {
                "name": "Айс-Латте",
                "description": "Холодный кофе с добавлением молока и льда (350 мл).",
                "price": "25 000 сум",
                "image": "https://picsum.photos/400/300?random=305"
            },
            {
                "name": "Свежевыжатый сок (Апельсин)",
                "description": "100% натуральный фреш из спелых апельсинов (250 мл).",
                "price": "30 000 сум",
                "image": "https://picsum.photos/400/300?random=306"
            }
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

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def send_menu_cards(message: types.Message, items: list, title: str):
    """Функция для отправки блюд в виде карточек с фото, описанием и ценой."""
    await message.answer(f"<b>=== {title} ===</b>", parse_mode="HTML")
    
    for item in items:
        caption = (
            f"<b>{item['name']}</b>\n\n"
            f"📝 <i>{item['description']}</i>\n\n"
            f"💰 <b>Цена:</b> {item['price']}"
        )
        try:
            await message.answer_photo(
                photo=item['image'],
                caption=caption,
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Ошибка при отправке фото: {e}")
            await message.answer(caption, parse_mode="HTML")

# ==================== ОБРАБОТЧИКИ (ХЕНДЛЕРЫ) ====================

@dp.message(CommandStart())
@dp.message(F.text == "⬅️ Главное меню")
async def start_handler(message: types.Message):
    await message.answer(
        "Добро пожаловать в наше меню! Выберите интересующий вас раздел:",
        reply_markup=main_kb
    )

@dp.message(F.text == "📅 Меню по дням")
async def show_days_keyboard(message: types.Message):
    await message.answer("Выберите день недели:", reply_markup=days_kb)

@dp.message(F.text == "☕ Напитки")
async def show_drinks_keyboard(message: types.Message):
    await message.answer("Выберите категории напитков:", reply_markup=drinks_kb)

# Обработка выбора дня недели
DAY_MAP = {
    "Понедельник": "mon",
    "Вторник": "tue",
    "Среда": "wed",
    "Четверг": "thu",
    "Пятница": "fri",
    "Суббота": "sat",
    "Воскресенье": "sun"
}

@dp.message(F.text.in_(DAY_MAP.keys()))
async def handle_days(message: types.Message):
    day_key = DAY_MAP[message.text]
    day_info = MENU_DATA["days"][day_key]
    await send_menu_cards(message, day_info["items"], f"Меню на {message.text}")

# Обработка завтраков и снеков
@dp.message(F.text == "🍳 Завтраки и снеки")
async def handle_breakfasts(message: types.Message):
    items = MENU_DATA["breakfast_snacks"]
    await send_menu_cards(message, items, "Завтраки и снеки")

# Обработка напитков (Горячие / Холодные)
@dp.message(F.text == "🔥 Горячие напитки")
async def handle_hot_drinks(message: types.Message):
    items = MENU_DATA["drinks"]["hot"]
    await send_menu_cards(message, items, "Горячие напитки")

@dp.message(F.text == "🧊 Холодные напитки")
async def handle_cold_drinks(message: types.Message):
    items = MENU_DATA["drinks"]["cold"]
    await send_menu_cards(message, items, "Холодные напитки")

# ==================== ЗАПУСК БОТА ====================

async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    print(">>> Бот успешно запущен и готов к работе! <<<")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
