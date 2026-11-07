import asyncio
import time
import os
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Твій адміністративний Telegram ID
ADMIN_ID = 8904909598

# Словники для станів
user_states = {}        # Для анонімних діалогів
admin_broadcast = set() # Множина для адмінів, які зараз вводять текст розсилки


# ─── 0. РОБОТА З БАЗОЮ ДАНИХ (SQLite) ──────────────────────────────────
DB_PATH = "bot_database.db"

def init_db():
    """Створення таблиць при запуску бота, якщо вони ще не існують."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at INTEGER
        )
    """)
    
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

def get_recent_users(limit=5):
    """Отримує список останніх зареєстрованих користувачів."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, first_name, created_at FROM users ORDER BY created_at DESC LIMIT ?", (limit,))
    users = cursor.fetchall()
    conn.close()
    return users

def get_all_user_ids():
    """Отримує список усіх ID користувачів для розсилки."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users


# ─── 1. КОМАНДА /start ──────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    
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


# ─── 4. АДМІН-ПАНЕЛЬ (/admin або /stats) ────────────────────────────────
@dp.message(Command("admin", "stats"))
async def cmd_admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас немає доступу до цієї команди.")
        return

    total_users, total_stars = get_stats()
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📊 Загальна статистика", callback_data="admin_stats")],
        [types.InlineKeyboardButton(text="👥 Останні користувачі", callback_data="admin_users")],
        [types.InlineKeyboardButton(text="📢 Зробити розсилку", callback_data="admin_broadcast")]
    ])

    await message.answer(
        f"👑 <b>Панель адміністратора</b>\n\n"
        f"👥 Загалом користувачів: <b>{total_users}</b>\n"
        f"⭐️ Зароблено зірок: <b>{total_stars} ⭐️</b>\n\n"
        f"Обери потрібний розділ нижче:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# ─── ОБРОБНИК КНОПОК АДМІН-ПАНЕЛІ ────────────────────────────────────────
@dp.callback_query(lambda c: c.data.startswith("admin_"))
async def process_admin_callbacks(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Немає прав!", show_alert=True)
        return

    action = callback_query.data

    if action == "admin_stats":
        total_users, total_stars = get_stats()
        back_kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 Назад до меню", callback_data="admin_menu")]
        ])
        await callback_query.message.edit_text(
            f"📊 <b>Детальна статистика:</b>\n\n"
            f"👥 Усього користувачів у базі: <b>{total_users}</b>\n"
            f"⭐️ Зароблено зірок (XTR): <b>{total_stars} ⭐️</b>",
            reply_markup=back_kb,
            parse_mode="HTML"
        )
        await callback_query.answer()

    elif action == "admin_users":
        recent = get_recent_users(5)
        users_text = ""
        for u in recent:
            uid, uname, fname, cat = u
            username_str = f"@{uname}" if uname else "немає"
            users_text += f"• <b>{fname}</b> ({username_str}) — <code>{uid}</code>\n"
        
        if not users_text:
            users_text = "Поки що немає зареєстрованих користувачів."

        back_kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 Назад до меню", callback_data="admin_menu")]
        ])
        await callback_query.message.edit_text(
            f"👥 <b>Останні 5 користувачів:</b>\n\n{users_text}",
            reply_markup=back_kb,
            parse_mode="HTML"
        )
        await callback_query.answer()

    elif action == "admin_broadcast":
        admin_broadcast.add(ADMIN_ID)
        back_kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Скасувати", callback_data="admin_menu")]
        ])
        await callback_query.message.edit_text(
            "📢 <b>Режим розсилки</b>\n\n"
            "Надішли мені наступним повідомленням текст (або фото з текстом), який хочеш розіслати всім користувачам бота.",
            reply_markup=back_kb,
            parse_mode="HTML"
        )
        await callback_query.answer()

    elif action == "admin_menu":
        admin_broadcast.discard(ADMIN_ID)
        total_users, total_stars = get_stats()
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="📊 Загальна статистика", callback_data="admin_stats")],
            [types.InlineKeyboardButton(text="👥 Останні користувачі", callback_data="admin_users")],
            [types.InlineKeyboardButton(text="📢 Зробити розсилку", callback_data="admin_broadcast")]
        ])
        await callback_query.message.edit_text(
            f"👑 <b>Панель адміністратора</b>\n\n"
            f"👥 Загалом користувачів: <b>{total_users}</b>\n"
            f"⭐️ Зароблено зірок: <b>{total_stars} ⭐️</b>\n\n"
            f"Обери потрібний розділ нижче:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback_query.answer()


# ─── 5. УСПІШНА ОПЛАТА ──────────────────────────────────────────────────
@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
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

    # Перевірка: чи робить адмін розсилку прямо зараз
    if user_id == ADMIN_ID and user_id in admin_broadcast:
        admin_broadcast.discard(ADMIN_ID)
        user_ids = get_all_user_ids()
        
        sent_count = 0
        await message.answer(f"🚀 Починаю розсилку для {len(user_ids)} користувачів...")
        
        for uid in user_ids:
            try:
                await bot.send_message(uid, text)
                sent_count += 1
                await asyncio.sleep(0.05) # Невелика затримка проти обмежень Telegram
            except Exception:
                pass
                
        await message.answer(f"✅ <b>Розсилку завершено!</b>\nУспішно надіслано: {sent_count}/{len(user_ids)}", parse_mode="HTML")
        return

    # Звичайне анонімне повідомлення
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


# ─── 8. ВЕБ-СЕРВЕР ДЛЯ ПІНГІВ (щоб Render не спав) ─────────────────────────
async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


# ─── 9. ГОЛОВНИЙ ЗАПУСК ──────────────────────────────────────────────────
async def main():
    init_db()
    print("Бот запущено, базу даних та адмін-панель підключено!")
    
    # Запускаємо веб-сервер для пінгів у фоні
    await start_web_server()
    
    # Запускаємо бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
