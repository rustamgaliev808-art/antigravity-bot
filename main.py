import os
import logging
import asyncio
import sys
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    BotCommand
)

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_ОТ_BOTFATHER")
ADMIN_ID = os.getenv("ADMIN_ID", "ВАШ_TELEGRAM_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel")

CLICK_PASS_ID = "052528"

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище корзин и истории в памяти: {user_id: {"cart": {item_id: count}, "history": []}}
users_data = {}

# ==================== БАЗА ДАННЫХ МЕНЮ ====================
MENU = {
    # 1. ДНИ НЕДЕЛИ
    "mon": {
        "title": "Понедельник",
        "items": {
            "mon_1": {"name": "Суп-харчо с говядиной", "desc": "Пряный суп с рисом, томатами и кавказскими специями.", "price": 35000, "image": "https://images.unsplash.com/photo-1547592166-23ac45744acd?w=600"},
            "mon_2": {"name": "Ташкентский плов", "desc": "Традиционный плов с отборной говядиной, нутом и изюмом.", "price": 45000, "image": "https://images.unsplash.com/photo-1633964913295-ceb43826e7c9?w=600"}
        }
    },
    "tue": {
        "title": "Вторник",
        "items": {
            "tue_1": {"name": "Грибной крем-суп", "desc": "Нежный суп из шампиньонов со сливками и сухариками.", "price": 32000, "image": "https://images.unsplash.com/photo-1547592166-23ac45744acd?w=600"},
            "tue_2": {"name": "Куриный шницель с пюре", "desc": "Хрустящее куриное филе со сливочным пюре.", "price": 40000, "image": "https://images.unsplash.com/photo-1532550907401-a500c9a57435?w=600"}
        }
    },
    "wed": {
        "title": "Среда",
        "items": {
            "wed_1": {"name": "Борщ с говядиной", "desc": "Классический наваристый борщ, подается со сметаной.", "price": 35000, "image": "https://images.unsplash.com/photo-1547592166-23ac45744acd?w=600"},
            "wed_2": {"name": "Мясо по-французски", "desc": "Запеченная говядина под сырной корочкой с томатами.", "price": 48000, "image": "https://images.unsplash.com/photo-1544025162-d76694265947?w=600"}
        }
    },
    "thu": {
        "title": "Четверг",
        "items": {
            "thu_1": {"name": "Уха из лосося", "desc": "Ароматная рыбная уха со свежей зеленью.", "price": 38000, "image": "https://images.unsplash.com/photo-1547592166-23ac45744acd?w=600"},
            "thu_2": {"name": "Рыбное филе с рисом", "desc": "Нежное филе белой рыбы на пару с овощами и рисом.", "price": 42000, "image": "https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?w=600"}
        }
    },
    "fri": {
        "title": "Пятница",
        "items": {
            "fri_1": {"name": "Лагман уйгурский", "desc": "Тянутая вручную лапша с мясом и овощным соусом сай.", "price": 42000, "image": "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?w=600"},
            "fri_2": {"name": "Люля-кебаб с гарниром", "desc": "Сочный кебаб из рубленой говядины с маринованным луком.", "price": 44000, "image": "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?w=600"}
        }
    },
    "sat": {
        "title": "Суббота",
        "items": {
            "sat_1": {"name": "Солянка мясная", "desc": "Густой суп с копченостями, маслинами и лимоном.", "price": 39000, "image": "https://images.unsplash.com/photo-1547592166-23ac45744acd?w=600"},
            "sat_2": {"name": "Бефстроганов с гречкой", "desc": "Полоски нежной говядины в сливочном соусе.", "price": 46000, "image": "https://images.unsplash.com/photo-1544025162-d76694265947?w=600"}
        }
    },
    "sun": {
        "title": "Воскресенье",
        "items": {
            "sun_1": {"name": "Сырный крем-суп", "desc": "Бархатистый суп с кусочками курочки и гренками.", "price": 34000, "image": "https://images.unsplash.com/photo-1547592166-23ac45744acd?w=600"},
            "sun_2": {"name": "Куриный рулет с сыром", "desc": "Запеченное филе с сыром моцарелла и зеленью.", "price": 42000, "image": "https://images.unsplash.com/photo-1598515214211-89d3c73ae83b?w=600"}
        }
    },

    # 2. ЗАВТРАКИ И СНЕКИ
    "breakfast": {
        "title": "Завтраки и снеки",
        "items": {
            "br_1": {"name": "Овсяная каша с ягодами", "desc": "Каша на молоке со свежими ягодами и натуральным медом.", "price": 20000, "image": "https://images.unsplash.com/photo-1584776296944-ab6fb57b0bdd?w=600"},
            "br_2": {"name": "Сырники со сметаной", "desc": "Домашние нежные сырники из фермерского творога.", "price": 25000, "image": "https://images.unsplash.com/photo-1589301760014-d929f3979dbc?w=600"},
            "br_3": {"name": "Клаб-сэндвич с курицей", "desc": "Тосты гриль с филе птицы, сыром чеддер и томатами.", "price": 30000, "image": "https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=600"}
        }
    },

    # 3. НАПИТКИ
    "drinks_hot": {
        "title": "Горячие напитки",
        "items": {
            "dr_h1": {"name": "Американо / Капучино", "desc": "Свежесваренный кофе из зерен 100% арабики (250 мл).", "price": 20000, "image": "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=600"},
            "dr_h2": {"name": "Чай Имбирь-Лимон", "desc": "Согревающий натуральный чай с медом и мятой.", "price": 18000, "image": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?w=600"}
        }
    },
    "drinks_cold": {
        "title": "Холодные напитки",
        "items": {
            "dr_c1": {"name": "Домашний лимонад", "desc": "Освежающий лимонад Цитрус-Мята со льдом (400 мл).", "price": 25000, "image": "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=600"},
            "dr_c2": {"name": "Свежевыжатый апельсиновый сок", "desc": "100% натуральный цитрусовый фреш (250 мл).", "price": 30000, "image": "https://images.unsplash.com/photo-1613478223719-2ab802602423?w=600"}
        }
    }
}

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_user_storage(user_id: int):
    if user_id not in users_data:
        users_data[user_id] = {"cart": {}, "history": []}
    return users_data[user_id]

def find_item(item_id: str):
    for cat_data in MENU.values():
        if item_id in cat_data["items"]:
            return cat_data["items"][item_id]
    return None

def get_cart_total(user_id: int):
    storage = get_user_storage(user_id)
    cart = storage["cart"]
    total = 0
    items_count = 0
    for i_id, count in cart.items():
        item = find_item(i_id)
        if item:
            total += item["price"] * count
            items_count += count
    return total, items_count

# ==================== КЛАВИАТУРЫ ====================

def kb_main(user_id: int):
    _, count = get_cart_total(user_id)
    cart_btn_text = f"🛍 Корзина ({count})" if count > 0 else "🛍 Корзина"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Меню по дням", callback_data="view_days")],
        [InlineKeyboardButton(text="🍳 Завтраки и снеки", callback_data="cat_breakfast"),
         InlineKeyboardButton(text="☕ Напитки", callback_data="view_drinks")],
        [InlineKeyboardButton(text=cart_btn_text, callback_data="view_cart"),
         InlineKeyboardButton(text="📜 История", callback_data="view_history")]
    ])

def kb_days():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Понедельник", callback_data="cat_mon"),
         InlineKeyboardButton(text="Вторник", callback_data="cat_tue")],
        [InlineKeyboardButton(text="Среда", callback_data="cat_wed"),
         InlineKeyboardButton(text="Четверг", callback_data="cat_thu")],
        [InlineKeyboardButton(text="Пятница", callback_data="cat_fri"),
         InlineKeyboardButton(text="Суббота", callback_data="cat_sat")],
        [InlineKeyboardButton(text="Воскресенье", callback_data="cat_sun")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="to_main")]
    ])

def kb_drinks():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Горячие напитки", callback_data="cat_drinks_hot"),
         InlineKeyboardButton(text="🧊 Холодные напитки", callback_data="cat_drinks_cold")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="to_main")]
    ])

# ==================== ОБРАБОТЧИКИ (HANDLERS) ====================

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    get_user_storage(user_id)
    text = (
        "👋 <b>Добро пожаловать в сервис заказа питания!</b>\n\n"
        "Выберите интересующий раздел меню ниже 👇"
    )
    await message.answer(text, reply_markup=kb_main(user_id), parse_mode="HTML")

@dp.callback_query(F.data == "to_main")
async def cb_to_main(call: types.CallbackQuery):
    user_id = call.from_user.id
    text = "👋 <b>Главное меню:</b>\n\nВыберите нужный раздел 👇"
    try:
        await call.message.edit_text(text, reply_markup=kb_main(user_id), parse_mode="HTML")
    except Exception:
        await call.message.answer(text, reply_markup=kb_main(user_id), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "view_days")
async def cb_view_days(call: types.CallbackQuery):
    await call.message.edit_text("📅 <b>Выберите день недели:</b>", reply_markup=kb_days(), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "view_drinks")
async def cb_view_drinks(call: types.CallbackQuery):
    await call.message.edit_text("☕ <b>Выберите категорию напитков:</b>", reply_markup=kb_drinks(), parse_mode="HTML")
    await call.answer()

# Просмотр категории (отправка карточек с фото)
@dp.callback_query(F.data.startswith("cat_"))
async def cb_show_category(call: types.CallbackQuery):
    cat_id = call.data.replace("cat_", "")
    cat = MENU.get(cat_id)
    if not cat:
        await call.answer("Категория не найдена.")
        return

    await call.message.answer(f"🍽 <b>Раздел: {cat['title']}</b>", parse_mode="HTML")
    user_id = call.from_user.id
    cart = get_user_storage(user_id)["cart"]

    for item_id, item in cat["items"].items():
        in_cart = cart.get(item_id, 0)
        btn_add_text = f"➕ В корзину ({in_cart})" if in_cart > 0 else "➕ В корзину"

        item_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➖", callback_data=f"del_{item_id}"),
             InlineKeyboardButton(text=btn_add_text, callback_data=f"add_{item_id}")],
            [InlineKeyboardButton(text="🛍 Перейти в корзину", callback_data="view_cart")]
        ])

        caption = (
            f"<b>{item['name']}</b>\n\n"
            f"<i>{item['desc']}</i>\n\n"
            f"💰 <b>Цена:</b> {item['price']:,} сум".replace(",", " ")
        )

        try:
            await call.message.answer_photo(photo=item["image"], caption=caption, reply_markup=item_kb, parse_mode="HTML")
        except Exception:
            await call.message.answer(caption, reply_markup=item_kb, parse_mode="HTML")

    await call.answer()

# Добавление позиции
@dp.callback_query(F.data.startswith("add_"))
async def cb_add_item(call: types.CallbackQuery):
    item_id = call.data.replace("add_", "")
    item = find_item(item_id)
    if not item:
        await call.answer()
        return

    user_id = call.from_user.id
    cart = get_user_storage(user_id)["cart"]
    cart[item_id] = cart.get(item_id, 0) + 1
    count = cart[item_id]

    await call.answer(f"Добавлено: {item['name']} (x{count})")

    # Обновляем кнопку на карточке
    new_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➖", callback_data=f"del_{item_id}"),
         InlineKeyboardButton(text=f"➕ В корзину ({count})", callback_data=f"add_{item_id}")],
        [InlineKeyboardButton(text="🛍 Перейти в корзину", callback_data="view_cart")]
    ])
    try:
        await call.message.edit_reply_markup(reply_markup=new_kb)
    except Exception:
        pass

# Удаление позиции
@dp.callback_query(F.data.startswith("del_"))
async def cb_del_item(call: types.CallbackQuery):
    item_id = call.data.replace("del_", "")
    item = find_item(item_id)
    if not item:
        await call.answer()
        return

    user_id = call.from_user.id
    cart = get_user_storage(user_id)["cart"]

    if item_id in cart and cart[item_id] > 0:
        cart[item_id] -= 1
        if cart[item_id] == 0:
            del cart[item_id]
        count = cart.get(item_id, 0)
        await call.answer(f"Удалено: {item['name']}")

        btn_add = f"➕ В корзину ({count})" if count > 0 else "➕ В корзину"
        new_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➖", callback_data=f"del_{item_id}"),
             InlineKeyboardButton(text=btn_add, callback_data=f"add_{item_id}")],
            [InlineKeyboardButton(text="🛍 Перейти в корзину", callback_data="view_cart")]
        ])
        try:
            await call.message.edit_reply_markup(reply_markup=new_kb)
        except Exception:
            pass
    else:
        await call.answer("Позиции нет в корзине")

# Просмотр корзины
@dp.callback_query(F.data == "view_cart")
async def cb_view_cart(call: types.CallbackQuery):
    user_id = call.from_user.id
    cart = get_user_storage(user_id)["cart"]

    if not cart:
        await call.message.answer(
            "🛍 <b>Ваша корзина пуста.</b>\nВыберите позиции из меню!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="to_main")]
            ]),
            parse_mode="HTML"
        )
        await call.answer()
        return

    lines = []
    total = 0
    for item_id, count in cart.items():
        item = find_item(item_id)
        if item:
            subtotal = item["price"] * count
            total += subtotal
            lines.append(f"• <b>{item['name']}</b> x{count} = {subtotal:,} сум".replace(",", " "))

    cart_text = (
        "🛍 <b>ВАШ ЗАКАЗ:</b>\n\n" +
        "\n".join(lines) +
        f"\n\n💰 <b>Итого к оплате:</b> {total:,} сум\n".replace(",", " ") +
        "📍 <b>Выдача:</b> 4 этаж (12:30–14:00)"
    )

    cart_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить заказ", callback_data="checkout")],
        [InlineKeyboardButton(text="🗑 Очистить", callback_data="clear_cart"),
         InlineKeyboardButton(text="⬅️ Меню", callback_data="to_main")]
    ])

    await call.message.answer(cart_text, reply_markup=cart_kb, parse_mode="HTML")
    await call.answer()

# Очистка корзины
@dp.callback_query(F.data == "clear_cart")
async def cb_clear_cart(call: types.CallbackQuery):
    user_id = call.from_user.id
    get_user_storage(user_id)["cart"].clear()
    await call.message.answer("🗑 Корзина очищена.", reply_markup=kb_main(user_id))
    await call.answer()

# Оформление заказа и выдача счёта Click
@dp.callback_query(F.data == "checkout")
async def cb_checkout(call: types.CallbackQuery):
    user_id = call.from_user.id
    total, count = get_cart_total(user_id)

    if count == 0:
        await call.answer("Корзина пуста!")
        return

    click_url = f"https://my.click.uz/clickpass/{CLICK_PASS_ID}?amount={total}"
    ussd_code = f"*880*{CLICK_PASS_ID}*{total}#"

    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить через Click Pass", url=click_url)],
        [InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data="confirm_paid")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="view_cart")]
    ])

    pay_text = (
        f"💳 <b>Счёт на сумму {total:,} сум сформирован!</b>\n\n".replace(",", " ") +
        "<b>Способы оплаты:</b>\n"
        "1️⃣ Нажмите <b>«Оплатить через Click Pass»</b> для перехода в приложение.\n\n"
        "2️⃣ Либо наберите USSD-команду:\n"
        f"<code>{ussd_code}</code>\n\n"
        "После совершения оплаты нажмите кнопку <b>«Я оплатил(а)»</b> ниже 👇"
    )

    await call.message.answer(pay_text, reply_markup=pay_kb, parse_mode="HTML")
    await call.answer()

# Подтверждение оплаты
@dp.callback_query(F.data == "confirm_paid")
async def cb_confirm_paid(call: types.CallbackQuery):
    user_id = call.from_user.id
    storage = get_user_storage(user_id)
    cart = storage["cart"]

    if not cart:
        await call.answer("Заказ уже оформлен или корзина пуста.")
        return

    total, _ = get_cart_total(user_id)
    items_summary = []
    for item_id, count in cart.items():
        item = find_item(item_id)
        if item:
            items_summary.append(f"{item['name']} x{count}")

    items_str = ", ".join(items_summary)
    date_str = datetime.now().strftime("%d.%m %H:%M")
    storage["history"].append(f"{date_str} — {items_str} ({total:,} сум)".replace(",", " "))
    storage["cart"].clear()

    order_num = 2300 + len(storage["history"])

    success_text = (
        f"✅ <b>Заказ №{order_num} успешно принят!</b>\n\n"
        f"<b>Состав:</b>\n• {items_str}\n"
        f"<b>Сумма:</b> {total:,} сум\n\n".replace(",", " ") +
        "📍 <b>Выдача:</b> 4 этаж, 12:30–14:00\nПриятного аппетита!"
    )
    await call.message.answer(success_text, reply_markup=kb_main(user_id), parse_mode="HTML")

    # Уведомление администратору
    if ADMIN_ID and ADMIN_ID.isdigit():
        try:
            admin_msg = (
                f"🚨 <b>НОВЫЙ ЗАКАЗ №{order_num}</b>\n"
                f"👤 Клиент: @{call.from_user.username or 'ID ' + str(user_id)}\n"
                f"💰 Сумма: {total:,} сум\n".replace(",", " ") +
                f"📋 Состав: {items_str}"
            )
            await bot.send_message(chat_id=int(ADMIN_ID), text=admin_msg, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение админу: {e}")

    await call.answer()

# Просмотр истории
@dp.callback_query(F.data == "view_history")
async def cb_view_history(call: types.CallbackQuery):
    user_id = call.from_user.id
    history = get_user_storage(user_id)["history"]

    if not history:
        await call.message.answer("📜 История заказов пуста.", reply_markup=kb_main(user_id))
    else:
        text = "📜 <b>Ваша история заказов:</b>\n\n" + "\n".join([f"• {h}" for h in history])
        await call.message.answer(text, reply_markup=kb_main(user_id), parse_mode="HTML")
    await call.answer()

# Команда публикации меню в канал
@dp.message(Command("post"))
async def cmd_post_to_channel(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("У вас нет прав для публикации.")
        return

    days_map = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
    today_key = days_map.get(datetime.now().weekday(), "mon")
    day_menu = MENU[today_key]

    bot_info = await bot.get_me()

    lines = []
    for item in day_menu["items"].values():
        lines.append(f"• <b>{item['name']}</b> — {item['price']:,} сум\n  <i>{item['desc']}</i>".replace(",", " "))

    post_caption = (
        f"🍽 <b>МЕНЮ НА СЕГОДНЯ ({day_menu['title'].upper()})</b>\n\n" +
        "\n\n".join(lines) +
        "\n\n⏰ <b>Приём заказов:</b> до 11:00\n"
        "📍 <b>Выдача:</b> 4 этаж (12:30–14:00)\n\n"
        "👇 <i>Сделайте заказ в боте прямо сейчас:</i>"
    )

    channel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥗 Оформить заказ", url=f"https://t.me/{bot_info.username}")]
    ])

    try:
        # Картинка первого блюда как баннер
        first_img = list(day_menu["items"].values())[0]["image"]
        await bot.send_photo(chat_id=CHANNEL_ID, photo=first_img, caption=post_caption, reply_markup=channel_kb, parse_mode="HTML")
        await message.answer("✅ Меню успешно опубликовано в канале!")
    except Exception as e:
        await message.answer(f"❌ Ошибка публикации: {e}\nУбедитесь, что бот назначен администратором канала.")

# ==================== ЗАПУСК ====================

async def main():
    if BOT_TOKEN == "ВАШ_ТОКЕН_ОТ_BOTFATHER" or not BOT_TOKEN:
        print("❌ Укажите токен бота в переменной BOT_TOKEN!")
        return

    await bot.set_my_commands([
        BotCommand(command="start", description="🔄 Главное меню"),
        BotCommand(command="post", description="📢 Опубликовать меню в канал (Админ)")
    ])

    print(">>> Бот успешно запущен и ожидает сообщений... <<<")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
