import asyncio
import time
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery

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
    
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    
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

# 2. Команда /link (Отримати своє посилання)
@dp.message(Command("link"))
async def cmd_link(message: types.Message):
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    personal_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    await message.answer(
        f"🔗 **Твоє персональне посилання:**\n"
        f"<code>{personal_link}</code>\n\n"
        f"Поділися ним у соцмережах, щоб отримувати анонімні повідомлення!",
        parse_mode="HTML"
    )

# 3. Команда /help (Допомога та правила)
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 **Як користуватися ботом:**\n\n"
        "1️⃣ Натисни /link, щоб отримати своє унікальне посилання.\n"
        "2️⃣ Опублікуй його у своєму профілі чи історіях.\n"
        "3️⃣ Коли хтось напише тобі через це посилання, ти отримаєш повідомлення з кнопкою «Дізнатися відправника (100 ⭐️)».\n\n"
        "🔒 Усі повідомлення до моменту купівлі підказки залишаються повністю анонімними!",
        parse_mode="HTML"
    )

# 4. Успішна оплата
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

# 5. Обробник надсилання анонімки
@dp.message()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    if user_id in user_states:
        target_id = user_states[user_id]
        
        payment_key = f"reveal_{user_id}_{int(time.time())}"
        
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
        bot_info = await bot.get_me()
        personal_link = f"https://t.me/{bot_info.username}?start={user_id}"
        await message.answer(
            f"Привіт! Скористайся командою /link, щоб отримати своє анонімне посилання, або /help для довідки.",
            parse_mode="HTML"
        )

# 6. Натискання на кнопку купівлі -> виставлення рахунку в Stars
@dp.callback_query(lambda c: c.data.startswith("reveal_"))
async def process_buy_hint(callback_query: types.CallbackQuery):
    payment_key = callback_query.data
    prices = [LabeledPrice(label="Розкрити відправника", amount=100)]
    
    await bot.send_invoice(
        chat_id=callback_query.from_user.id,
        title="🕵️ Хто надіслав анонімку?",
        description="Купи підказку за 100 зірок, щоб дізнатися ім'я та юзернейм того, хто написав це повідомлення.",
        payload=payment_key,
        currency="XTR",
        prices=prices
    )
    await callback_query.answer()

# 7. Попереднє підтвердження платежу
@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

async def main():
    print("Бот запущено і повністю готовий до роботи!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
