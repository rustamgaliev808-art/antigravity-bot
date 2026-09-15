"""Employee, owner and kitchen screens. No new orders are created here."""
import logging
from contextlib import closing
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from order_lifecycle import ActionError, PAYMENT_LABELS


def launch(runtime):
    if runtime.MINIAPP_URL.startswith("https://"):
        return InlineKeyboardButton("🍽 Открыть меню", web_app=WebAppInfo(url=runtime.MINIAPP_URL))
    return InlineKeyboardButton("🍽 Открыть меню", callback_data="app_unconfigured")


def home(runtime):
    return InlineKeyboardMarkup([[launch(runtime)], [InlineKeyboardButton("📋 Мои заказы", callback_data="my_orders")], [InlineKeyboardButton("Помощь", callback_data="help")]])


def staff(runtime, user_id):
    return user_id > 0 and user_id in ({runtime.ADMIN_ID} | set(runtime.KITCHEN_IDS))


def card(runtime, row):
    refund = "\nНужен ручной возврат денег владельцем; возврат ещё не подтверждён." if row["status"] == "cancelled" and row["payment_status"] in {"confirmed", "review", "legacy_unknown"} else ""
    return (f"Заказ #{row['order_id']}\n{row['items']}\n"
            f"Дата: {row['pickup_date'] or row['created_at'][:10]} · {row['pickup_time']}\n"
            f"{row.get('comment') or 'Без комментария'}\n"
            f"Сумма: {runtime.fmt(row['total'])} сум\n"
            f"Оплата: {PAYMENT_LABELS.get(row['payment_status'], 'Нужна проверка')}\n"
            f"Приготовление: {runtime.ORDER_STATUSES.get('new' if row['status'] == 'paid' else row['status'], row['status'])}{refund}")


def controls(runtime, row, actor):
    buttons = []
    if actor == runtime.ADMIN_ID:
        if row["payment_status"] != "confirmed" and row["status"] != "cancelled":
            buttons.append([InlineKeyboardButton("Подтвердить оплату", callback_data=f"payment_confirm:{row['order_id']}")])
        if row["status"] not in {"cancelled", "delivered"}:
            buttons.append([InlineKeyboardButton("Отменить", callback_data=f"setstatus_{row['order_id']}_cancelled")])
    if staff(runtime, actor) and row["payment_status"] == "confirmed":
        next_step = {"new": ("cooking", "Начать готовить"), "paid": ("cooking", "Начать готовить"), "cooking": ("ready", "Готов"), "ready": ("delivered", "Выдать")}.get(row["status"])
        if next_step:
            buttons.append([InlineKeyboardButton(next_step[1], callback_data=f"setstatus_{row['order_id']}_{next_step[0]}")])
    return InlineKeyboardMarkup(buttons) if buttons else None


async def send_customer(runtime, bot, row):
    row = dict(row)
    text = card(runtime, row)
    buttons = []
    if row["status"] not in {"cancelled", "delivered"} and row["payment_status"] != "confirmed":
        buttons = [[InlineKeyboardButton("Оплатить через Click", url=runtime.get_click_payment_url(row["total"]))],
                   [InlineKeyboardButton("Я оплатил — отправить на проверку", callback_data=f"payment_report:{row['order_id']}")]]
    buttons.append([InlineKeyboardButton("Повторить подтверждение", callback_data=f"resend:{row['order_id']}")])
    markup = InlineKeyboardMarkup(buttons)
    # Keep the complete composition in a message, not a truncated photo caption.
    await bot.send_message(chat_id=row["user_id"], text=text, reply_markup=markup)
    if row["payment_status"] == "confirmed" and row["status"] not in {"cancelled", "delivered"}:
        info = await bot.get_me()
        link = runtime.get_pickup_link(info.username, row["qr_token"])
        try:
            await bot.send_photo(chat_id=row["user_id"], photo=runtime.build_qr_image(link), caption=f"QR заказа #{row['order_id']}. Покажите сотруднику, когда заказ будет готов.")
        except Exception:
            await bot.send_message(chat_id=row["user_id"], text=f"QR-ссылка заказа #{row['order_id']}: {link}")


async def notify(runtime, bot, order_id, owner_notice=False):
    row = runtime.get_order(order_id)
    if not row:
        return
    try:
        await send_customer(runtime, bot, row)
    except Exception as error:
        logging.warning("customer_notification_failed order_id=%s type=%s", order_id, type(error).__name__)
    if owner_notice and runtime.ADMIN_ID:
        try:
            await bot.send_message(chat_id=runtime.ADMIN_ID, text=card(runtime, row), reply_markup=controls(runtime, row, runtime.ADMIN_ID))
        except Exception as error:
            logging.warning("owner_notification_failed order_id=%s type=%s", order_id, type(error).__name__)


async def list_orders(runtime, message, actor, kind):
    with closing(runtime._conn()) as conn:
        if kind == "mine":
            rows = conn.execute("SELECT * FROM orders WHERE user_id=? ORDER BY order_id DESC LIMIT 30", (actor,)).fetchall()
        elif kind == "payment":
            rows = conn.execute("SELECT * FROM orders WHERE payment_status IN ('review','legacy_unknown') AND status!='cancelled' ORDER BY order_id LIMIT 50").fetchall()
        elif kind == "kitchen":
            rows = conn.execute("SELECT * FROM orders WHERE payment_status='confirmed' AND status NOT IN ('cancelled','delivered') ORDER BY pickup_date,pickup_time,order_id LIMIT 50").fetchall()
        else:
            rows = conn.execute("SELECT * FROM orders WHERE status NOT IN ('cancelled','delivered') ORDER BY pickup_date,pickup_time,order_id LIMIT 50").fetchall()
    if not rows:
        await message.reply_text("В этом списке пока нет заказов.")
    for row in rows:
        row = dict(row)
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("Показать подтверждение / QR", callback_data=f"resend:{row['order_id']}")]]) if kind == "mine" else controls(runtime, row, actor)
        await message.reply_text(card(runtime, row), reply_markup=markup)


async def start(runtime, update, context):
    actor = update.effective_user.id
    arg = context.args[0] if context.args else ""
    if arg.startswith("pickup_"):
        if not staff(runtime, actor):
            await update.message.reply_text("QR-карточка доступна только сотруднику выдачи.")
            return
        with closing(runtime._conn()) as conn:
            row = conn.execute("SELECT * FROM orders WHERE qr_token=?", (arg[7:],)).fetchone()
        if not row:
            await update.message.reply_text("Заказ не найден.")
            return
        row = dict(row)
        await update.message.reply_text(card(runtime, row), reply_markup=controls(runtime, row, actor))
        return
    if arg == "register" and not runtime.get_user(actor):
        await update.message.reply_text("Для первого заказа поделитесь своим номером штатной кнопкой Telegram. Корзина сохранена в Mini App.", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Поделиться номером", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True))
        return
    await update.message.reply_text("Меню можно смотреть без регистрации. Соберите заказ в Mini App.", reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text("Click Lunch · выдача на 4 этаже, кухня", reply_markup=home(runtime))


async def help_message(runtime, message):
    support = f"\nПоддержка: {runtime.SUPPORT_CONTACT}" if runtime.SUPPORT_CONTACT else "\nЕсли нужна помощь, обратитесь к сотруднику в месте выдачи."
    await message.reply_text("Откройте меню, выберите блюда, дату и время. Перед первым заказом поделитесь своим номером в личном чате с ботом. Оплатите по ссылке Click и нажмите «Я оплатил». Владелец проверит деньги; после подтверждения бот пришлёт QR. Дождитесь статуса «Готов» и покажите QR сотруднику на 4 этаже, кухня. Сканирование только открывает карточку; сотрудник отдельно нажимает «Выдать»." + support, reply_markup=home(runtime))


async def kitchen(runtime, update, context):
    if not staff(runtime, update.effective_user.id):
        await update.message.reply_text("Доступ закрыт.")
        return
    await update.message.reply_text("Кухня · только подтверждённая оплата", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Заказы по времени", callback_data="kitchen_orders")], [InlineKeyboardButton("Сводка на сегодня", callback_data="kitchen_summary")]]))


async def callback(runtime, update, context):
    q, actor = update.callback_query, update.effective_user.id
    data = q.data or ""
    try:
        if data in {"home", "app_unconfigured", "help", "my_orders", "profile"}:
            await q.answer()
            if data == "help":
                await help_message(runtime, q.message)
            elif data in {"my_orders", "profile"}:
                await list_orders(runtime, q.message, actor, "mine")
            else:
                await q.message.reply_text("Откройте меню по новой кнопке. Если кнопка недоступна, владелец ещё не настроил HTTPS-адрес.", reply_markup=home(runtime))
            return True
        if data in {"adm_orders", "adm_payments", "kitchen_orders", "kitchen_summary", "adm_kitchen"}:
            if not staff(runtime, actor) or (data in {"adm_orders", "adm_payments"} and actor != runtime.ADMIN_ID):
                raise ActionError("Доступ закрыт.")
            await q.answer()
            if data in {"kitchen_summary", "adm_kitchen"}:
                lines = [f"{name}: {qty}" for _, name, qty in runtime.get_kitchen_summary()]
                await q.message.reply_text("Оплаченные блюда на сегодня:\n" + ("\n".join(lines) or "Пока нет заказов."))
            else:
                await list_orders(runtime, q.message, actor, {"adm_orders": "active", "adm_payments": "payment", "kitchen_orders": "kitchen"}[data])
            return True
        if data.startswith(("resend:", "payment_report:", "payment_confirm:", "setstatus_")):
            if data.startswith("setstatus_"):
                _, identifier, status = data.split("_", 2)
            else:
                identifier = data.split(":", 1)[1]
                status = None
            row = runtime.get_order(int(identifier))
            if not row:
                raise ActionError("Заказ не найден.")
            if data.startswith("resend:"):
                if row["user_id"] != actor:
                    raise ActionError("Заказ не найден.")
                await q.answer()
                await send_customer(runtime, context.bot, row)
                return True
            if data.startswith("payment_report:"):
                changed = runtime.report_payment(row["order_id"], actor)
            elif data.startswith("payment_confirm:"):
                changed = runtime.confirm_payment(row["order_id"], actor)
            else:
                changed = runtime.set_order_status(row["order_id"], status, actor)
            await q.answer("Сохранено" if changed else "Уже выполнено")
            current = runtime.get_order(row["order_id"])
            await q.message.reply_text(card(runtime, current), reply_markup=controls(runtime, current, actor))
            if changed:
                await notify(runtime, context.bot, row["order_id"], True)
            return True
        # Only the owner's existing admin tools continue to the old handler.
        if data.startswith("adm_"):
            return False
        if data == "ignore":
            await q.answer()
            return True
        await q.answer()
        await q.message.reply_text("Эти кнопки оформления устарели. Новые заказы собираются только в Mini App. Существующий заказ можно открыть в «Мои заказы».", reply_markup=home(runtime))
        return True
    except (ActionError, ValueError) as error:
        await q.answer(str(error) if isinstance(error, ActionError) else "Некорректная кнопка.", show_alert=True)
        return True
