elif data == "confirm":
        await query.answer()
        
        amount = order['total']
        click_pass_id = "052528"
        
        # USSD-код для набора вручную
        ussd_code = f"*880*{click_pass_id}*{amount}#"
        
        # Ссылка для автоматического открытия приложения Click
        click_url = f"https://my.click.uz/clickpass/{click_pass_id}?amount={amount}"

        keyboard = [
            [InlineKeyboardButton("💳 Оплатить в Click", url=click_url)],
            [InlineKeyboardButton("✅ Я оплатил(а)", callback_data="paid")]
        ]
        
        text = (
            f"💳 <b>Счёт на {amount:,} сум сформирован!</b>\n\n".replace(",", " ") +
            "<b>Выберите удобный способ оплаты:</b>\n\n"
            "1️⃣ Нажмите кнопку <b>«Оплатить в Click»</b> ниже для перехода в приложение.\n\n"
            "2️⃣ Или скопируйте USSD-код (нажмите на него):"
            f"\n<code>{ussd_code}</code>\n\n"
            "После проведения платежа нажмите кнопку <b>«Я оплатил(а)»</b>."
        )
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
