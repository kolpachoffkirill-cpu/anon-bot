import asyncio
import time
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery

# Твій токен від BotFather
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Словник для відстеження, кому користувач пише анонімку
user_states = {}

# 1. Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    args = message.text.split()
    user_id = message.from_user.id
    bot_username = "super_anon_q_a_bot"  # наприклад: my_anon_bot
    
    if len(args) > 1:
        target_id = args[1]
        
        if str(user_id) == str(target_id):
            await message.answer("⚠️ Ти не можеш надіслати анонімне повідомлення самому собі!\n\nОсь твоє посилання для інших:")
            personal_link = f"https://t.me/{bot_username}?start={user_id}"
            await message.answer(f"<code>{personal_link}</code>", parse_mode="HTML")
            return
            
        user_states[user_id] = target_id
        await message.answer(
            "🤫 **Ти в режимі анонімного надсилання!**\n\n"
            "Напиши нижче у чат все, що хочеш сказати, і воно миттєво прилетить одержувачу.",
            parse_mode="HTML"
        )
        return

    personal_link = f"https://t.me/{bot_username}?start={user_id}"
    await message.answer(
        f"🤫 **Твій анонімний кабінет активовано!**\n\n"
        f"Твоє персональне посилання для отримання запитань:\n"
        f"<code>{personal_link}</code>\n\n"
        f"Скопіюй його та додай у свій профіль або Telegram Stories!",
        parse_mode="HTML"
    )

# 2. Успішна оплата (ВАЖЛИВО: цей обробник тепер стоїть ВИЩЕ за загальний @dp.message())
@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    payment_payload = message.successful_payment.invoice_payload
    
    sender_id = None
    try:
        parts = payment_payload.split("_")
        if len(parts) >= 2:
            sender_id = parts[1]
    except Exception:
        pass
    
    if sender_id:
        try:
            sender_info = await bot.get_chat(sender_id)
            sender_name = sender_info.first_name
            sender_username = f"@{sender_info.username}" if sender_info.username else "відсутній"
            
            await message.answer(
                f"🎉 **Оплата пройшла успішно!**\n\n"
                f"Це повідомлення тобі надіслав:\n"
                f"👤 Ім'я: **{sender_name}**\n"
                f"🔗 Юзернейм: **{sender_username}**\n"
                f"🆔 ID: `{sender_id}`",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Помилка отримання профілю: {e}")
            await message.answer(
                f"🎉 **Оплата успішна!**\n\n"
                f"Але не вдалося отримати профіль відправника.\n"
                f"Його ID: `{sender_id}`",
                parse_mode="HTML"
            )
    else:
        await message.answer("🎉 Успішно! Зірки зараховано на баланс бота, але не вдалося зчитати дані відправника з чека.")

# 3. Обробник надсилання анонімки (загальний текстовий обробник)
@dp.message()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    if user_id in user_states:
        target_id = user_states[user_id]
        
        # Зашиваємо ID відправника прямо у payload: reveal_ID_ЧАС
        payment_key = f"reveal_{user_id}_{int(time.time())}"
        
        # Кнопка для купівлі підказки (100 зірка для тесту)
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🕵️ Дізнатися відправника (100 ⭐️)", callback_data=payment_key)]
        ])
        
        try:
            await bot.send_message(
                chat_id=target_id,
                text=f"📥 **Тобі прийшло нове анонімне повідомлення:**\n\n"
                     f"«{text}»\n\n"
                     f"─────────────\n"
                     f"Хочеш дізнатися, хто це написав?",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await message.answer("✅ Твоє анонімне повідомлення успішно надіслано!")
        except Exception:
            await message.answer("❌ Не вдалося надіслати повідомлення (можливо, одержувач заблокував бота).")
            
        del user_states[user_id]
    else:
        await message.answer("Привіт! Скористайся своїм посиланням із команди /start, щоб отримувати анонімні запитання.")

# 4. Натискання на кнопку купівлі -> виставлення рахунку в Stars (1 зірка)
@dp.callback_query(lambda c: c.data.startswith("reveal_"))
async def process_buy_hint(callback_query: types.CallbackQuery):
    payment_key = callback_query.data
    prices = [LabeledPrice(label="Розкрити відправника", amount=1)]
    
    await bot.send_invoice(
        chat_id=callback_query.from_user.id,
        title="🕵️ Хто надіслав анонімку?",
        description="Купи підказку за 1 зірку, щоб дізнатися ім'я та юзернейм того, хто написав це повідомлення.",
        payload=payment_key,
        currency="XTR",
        prices=prices
    )
    await callback_query.answer()

# 5. Попереднє підтвердження платежу
@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

async def main():
    print("Бот запущено і готовий приймати платежі!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
