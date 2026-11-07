import asyncio
import time
import os
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Твій адміністративний Telegram ID
ADMIN_ID = 8904909598

# Словник для тимчасового відстеження активного діалогу (кому пишемо анонімку)
user_states = {}


# ─── 0. РОБОТА З БАЗОЮ ДАНИХ (SQLite) ──────────────────────────────────
DB_PATH = "bot_database.db"

def init_db():
    """Створення таблиць при запуску бота, якщо вони ще не існують."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Таблиця користувачів
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at INTEGER
        )
    """)
    
    # Таблиця успішних платежів Stars
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            timestamp INTEGER
        )
    """)
    
    conn.commit()
    conn.close()

def register_user(user_id: int, username: str, first_name: str):
    """Додає користувача в БД, якщо його там ще немає."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name, created_at) VALUES (?, ?, ?, ?)",
        (user_id, username, first_name, int(time.time()))
    )
    conn.commit()
    conn.close()

def log_payment(user_id: int, amount: int):
    """Записує успішний платіж в БД."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO payments (user_id, amount, timestamp) VALUES (?, ?, ?)",
        (user_id, amount, int(time.time()))
    )
    conn.commit()
    conn.close()

def get_stats():
    """Отримує загальну кількість користувачів та зароблених зірок."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(amount) FROM payments")
    total_stars = cursor.fetchone()[0] or 0
    
    conn.close()
    return total_users, total_stars


# ─── 1. КОМАНДА /start ──────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    
    # Зберігаємо користувача у базі даних
    register_user(user_id, username, first_name)
    
    args = message.text.split()
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
            "🤫 <b>Ти в режимі анонімного надсилання!</b>\n\n"
            "Напиши нижче у чат все, що хочеш сказати, і воно миттєво прилетить одержувачу.",
            parse_mode="HTML"
        )
        return

    personal_link = f"https://t.me/{bot_username}?start={user_id}"
    await message.answer(
        f"🤫 <b>Твій анонімний кабінет активовано!</b>\n\n"
        f"Твоє персональне посилання для отримання запитань:\n"
        f"<code>{personal_link}</code>\n\n"
        f"Скопіюй його та додай у свій профіль або Telegram Stories!",
        parse_mode="HTML"
    )


# ─── 2. КОМАНДА /link ───────────────────────────────────────────────────
@dp.message(Command("link"))
async def cmd_link(message: types.Message):
    user_id = message.from_user.id
    register_user(user_id, message.from_user.username or "", message.from_user.first_name or "")
    
    bot_info = await bot.get_me()
    personal_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    await message.answer(
        f"🔗 <b>Твоє персональне посилання:</b>\n"
        f"<code>{personal_link}</code>\n\n"
        f"Поділися ним у соцмережах, щоб отримувати анонімні повідомлення!",
        parse_mode="HTML"
    )


# ─── 3. КОМАНДА /help ───────────────────────────────────────────────────
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 <b>Як користуватися ботом:</b>\n\n"
        "1️⃣ Натисни /link, щоб отримати своє унікальне посилання.\n"
        "2️⃣ Опублікуй його у своєму профілі чи історіях.\n"
        "3️⃣ Коли хтось напише тобі через це посилання, ти отримаєш повідомлення з кнопкою «Дізнатися відправника (100 ⭐️)».\n\n"
        "🔒 Усі повідомлення до моменту купівлі підказки залишаються повністю анонімними!",
        parse_mode="HTML"
    )


# ─── 4. КОМАНДА /stats (Тільки для адміністратора) ───────────────────────
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас немає доступу до цієї команди.")
        return

    total_users, total_stars = get_stats()
    await message.answer(
        f"📊 <b>Статистика бота:</b>\n\n"
        f"👥 Загалом користувачів: <b>{total_users}</b>\n"
        f"⭐️ Зароблено зірок: <b>{total_stars} ⭐️</b>",
        parse_mode="HTML"
    )


# ─── 5. УСПІШНА ОПЛАТА ──────────────────────────────────────────────────
@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    # Записуємо платіж (100 зірок) у базу даних
    log_payment(message.from_user.id, 100)
    
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
                f"🎉 <b>Оплата пройшла успішно!</b>\n\n"
                f"Це повідомлення тобі надіслав:\n"
                f"👤 Ім'я: <b>{sender_name}</b>\n"
                f"🔗 Юзернейм: <b>{sender_username}</b>\n"
                f"🆔 ID: <code>{sender_id}</code>",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Помилка отримання профілю: {e}")
            await message.answer(
                f"🎉 <b>Оплата успішна!</b>\n\n"
                f"Але не вдалося отримати профіль відправника.\n"
                f"Його ID: <code>{sender_id}</code>",
                parse_mode="HTML"
            )
    else:
        await message.answer("🎉 Успішно! Зірки зараховано на баланс бота, але не вдалося зчитати дані відправника з чека.")


# ─── 6. ОБРОБНИК ПОВІДОМЛЕНЬ ─────────────────────────────────────────────
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
                text=f"📥 <b>Тобі прийшло нове анонімне повідомлення:</b>\n\n"
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


# ─── 7. ІНВОЙС ТА PRE-CHECKOUT ───────────────────────────────────────────
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

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


# ─── 8. ГОЛОВНИЙ ЗАПУСК ──────────────────────────────────────────────────
async def main():
    init_db()  # Ініціалізація SQLite при запуску
    print("Бот запущено, базу даних підключено!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
