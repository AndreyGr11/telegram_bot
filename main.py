import asyncio
import aiosqlite
import aiohttp
import async_timeout
import logging
import html
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters.command import Command
from aiogram import F
from aiogram.exceptions import TelegramBadRequest

load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
CRYPTOBOT_API_TOKEN = os.getenv("CRYPTOBOT_API_TOKEN")
CRYPTOBOT_API_URL = 'https://pay.crypt.bot/api'
PRIVATE_CHANNEL_LINK = os.getenv("PRIVATE_CHANNEL_LINK")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
DB_PATH = os.getenv("DB_PATH", "subscriptions.db")

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Настроим логгирование в консоль и в файл одновременно
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

main_buttons = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Купить приватку", callback_data="buy")],
    [InlineKeyboardButton(text="Проверить подписку", callback_data="check_subscription")],
    [InlineKeyboardButton(text="Служба поддержки", callback_data="support")]
])

tariff_buttons = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Неделя - 499 рублей", callback_data="tariff_week")],
    [InlineKeyboardButton(text="Месяц - 699 рублей", callback_data="tariff_month")],
    [InlineKeyboardButton(text="Год - 1299 рублей", callback_data="tariff_year")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])

payment_buttons = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="По номеру банк.карты - не работает", callback_data="pay_По номеру банковской карты")],
    [InlineKeyboardButton(text="Криптовалюта", callback_data="pay_Криптовалюта")],
    [InlineKeyboardButton(text="ЮMoney (Я.Деньги) - не работает", callback_data="pay_ЮMoney (Я.Деньги)")],
    [InlineKeyboardButton(text="Через Tribute (RUB, USD, EUR)", callback_data="pay_Через Tribute")],
    [InlineKeyboardButton(text="Через Cryptobot", callback_data="pay_Cryptobot")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_tariffs")]
])

payment_confirm_buttons = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="Оплатил ✅", callback_data="paid_confirm"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_payment_methods")
    ],
    [
        InlineKeyboardButton(text="🔁 Проверить оплату ещё раз", callback_data="paid_check_again")
    ]
])

payment_details = {
    "По номеру банковской карты": (
        "Реквизиты для оплаты:\n\n"
        "Номер карты Сбербанка: отсутствует\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "Владелец: Отсутствует\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "Банк: Сбербанк\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "Указывать комментарий к платежу не нужно!"
    ),

    "Криптовалюта": (
        "1. Произведите оплату на один из следующих кошельков:\n\n"
        "<b>USDT TRC-20</b>:\n<code>TGwEy2u4qMDPWs9pGjbmmHfL41AXDaffLs</code>\n\n"
        "<b>USDT BEP-20 (BNB Smart Chain)</b>:\n<code>0x036a1Bd6213ccc1f0893CeD6306e8430F5618d44</code>\n\n"
        "<b>USDT (TON)</b>:\n<code>UQA-j-ixpSuyrY_cdmymJDg_rnir5mc_1zeu4qjAzJPZBQL0</code>\n\n"
        "<b>USDT ERC-20 (Ethereum)</b>:\n<code>0x036a1Bd6213ccc1f0893CeD6306e8430F5618d44</code>\n\n"
        "2. После оплаты отправьте боту <b>хеш транзакции</b>.\n\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "<b>⚠️ Внимание:</b> Убедитесь, что вы скопировали адрес полностью и правильно.\n"
        "Сумма оплаты должна быть не меньше стоимости выбранного тарифа."
    ),

    "ЮMoney (Я.Деньги)": (
        "Реквизиты для оплаты:\n\n"
        "💳 Номер счёта ЮMoney (Я.Деньги): Отсутствует\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "Заполняйте номер счёта внимательно!"
    ),

    "Через Tribute": (
        "<b>⚠️ Важно:</b> данный метод оплаты может временно не работать из-за неполадок на серверах Telegram.\n\n"
        "<b>📸 После оплаты</b> отправьте фото или скриншот квитанции:\n"
        "— из банковского приложения, или\n"
        "— из приложения <a href='https://t.me/tribute'>Tribute</a>\n\n"
        "На квитанции должны быть чётко видны:\n"
        "• дата\n"
        "• время\n"
        "• сумма платежа\n\n"
        "<b>🔗 Ссылка для оплаты через Tribute:</b>\n"
        "<a href='https://t.me/tribute/app?startapp=dsqJ'>Открыть Tribute</a>"
    )
}

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER PRIMARY KEY,
                tariff TEXT,
                method TEXT,
                payment_id TEXT,
                paid INTEGER
            )
        """)
        await db.commit()

async def set_subscription(user_id, tariff, method=None, payment_id=None, paid=False):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO subscriptions(user_id, tariff, method, payment_id, paid)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                tariff=excluded.tariff,
                method=excluded.method,
                payment_id=excluded.payment_id,
                paid=excluded.paid
        """, (user_id, tariff, method, payment_id, int(paid)))
        await db.commit()

async def get_subscription(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT tariff, method, payment_id, paid FROM subscriptions WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return {"tariff": row[0], "method": row[1], "payment_id": row[2], "paid": bool(row[3])} if row else None

async def update_payment_status(user_id, paid):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE subscriptions SET paid = ? WHERE user_id = ?", (int(paid), user_id))
        await db.commit()

async def create_cryptobot_payment(amount_usd, user_id, user_name):
    url = f"{CRYPTOBOT_API_URL}/createInvoice"
    payload = {
        "asset": "USDT",
        "amount": amount_usd,
        "description": f"Платёж от {user_name or user_id}",
        "hidden_message": "Спасибо за оплату!",
        "paid_btn_name": "openBot",
        "paid_btn_url": "https://t.me/Camsslivbot"
    }
    headers = {
        "Crypto-Pay-API-Token": CRYPTOBOT_API_TOKEN,
        "Content-Type": "application/json"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with async_timeout.timeout(10):
                resp = await session.post(url, json=payload, headers=headers)
                data = await resp.json()
                if data.get("ok") and data.get("result"):
                    invoice = data["result"]
                    return invoice["invoice_id"], invoice["pay_url"]
    except Exception as e:
        logging.error(f"[DB] Ошибка получения подписки для {user_id}: {e}")
    return None, None

def get_user_mention(user: types.User) -> str:
    return f"@{user.username}" if user.username else f"[Пользователь](tg://user?id={user.id})"

async def check_cryptobot_payment(invoice_id):
    url = f"{CRYPTOBOT_API_URL}/getInvoices"
    payload = {"invoice_ids": [invoice_id]}
    headers = {
        "Crypto-Pay-API-Token": CRYPTOBOT_API_TOKEN,
        "Content-Type": "application/json"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with async_timeout.timeout(10):
                resp = await session.post(url, json=payload, headers=headers)
                data = await resp.json()
                if data.get("ok") and data.get("result"):
                    return data["result"][0]["status"] == "paid"
    except Exception as e:
        logging.error(f"Ошибка проверки оплаты: {e}")
    return False

@dp.message(Command("start"))
async def start_handler(msg: types.Message):
    user = msg.from_user
    mention = get_user_mention(user)
    logging.info(f"[START] Пользователь {user.id} ({mention}) начал работу с ботом.")
    await msg.answer("👋 Привет! Добро пожаловать в наш бот! Здесь ты можешь купить доступ в приватный канал.")
    await msg.answer("Жми кнопку ниже, чтобы начать:", reply_markup=main_buttons)
    await bot.send_message(ADMIN_CHAT_ID, f"📥 Пользователь {mention} зашел в бота.")

@dp.callback_query(F.data == "buy")
async def buy_callback(cb: types.CallbackQuery):
    try:
        await cb.message.edit_text("Выберите тариф:", reply_markup=tariff_buttons)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await cb.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(cb: types.CallbackQuery):
    try:
        await cb.message.edit_text("Привет! Купи доступ в приватный канал 👇", reply_markup=main_buttons)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await cb.answer()

@dp.callback_query(F.data == "back_to_tariffs")
async def back_to_tariffs(cb: types.CallbackQuery):
    try:
        await cb.message.edit_text("Выберите тариф:", reply_markup=tariff_buttons)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await cb.answer()

@dp.callback_query(F.data == "back_to_payment_methods")
async def back_to_payment_methods(cb: types.CallbackQuery):
    sub = await get_subscription(cb.from_user.id)
    if not sub or not sub.get("tariff"):
        await cb.answer("Сначала выберите тариф", show_alert=True)
        return

    display_tariff_map = {"week": "Неделя", "month": "Месяц", "year": "Год"}
    price_map = {"week": "499₽", "month": "699₽", "year": "1299₽"}
    display_tariff = display_tariff_map.get(sub['tariff'], "Неизвестно")
    price = price_map.get(sub['tariff'], "Неизвестно")

    try:
        await cb.message.edit_text(
            f"📦 Вы выбрали тариф: <b>{display_tariff}</b> — <b>{price}</b>\n\nВыберите метод оплаты:",
            reply_markup=payment_buttons,
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        # Обработка случая, когда текст не изменился
        if "message is not modified" not in str(e):
            raise

    await cb.answer()

@dp.callback_query(F.data == "paid_check_again")
async def check_again_callback(cb: types.CallbackQuery):
    sub = await get_subscription(cb.from_user.id)
    if not sub or not sub.get("payment_id"):
        await cb.answer("Нет ожидающей оплаты.", show_alert=True)
        return

    if await check_cryptobot_payment(sub["payment_id"]):
        logging.info(f"[CHECK] Оплата подтверждена для пользователя {cb.from_user.id}")
        await update_payment_status(cb.from_user.id, True)
        await cb.message.edit_text(f"✅ Оплата подтверждена!\nСсылка: {PRIVATE_CHANNEL_LINK}")
        await bot.send_message(ADMIN_CHAT_ID, f"💳 Оплата: {cb.from_user.id} — {sub['tariff']}")
    else:
        logging.info(f"[CHECK] Оплата НЕ подтверждена для пользователя {cb.from_user.id}")
        await cb.answer("Оплата пока не подтверждена.", show_alert=True)

@dp.message(Command("check"))
async def check_payment_command(msg: types.Message):
    sub = await get_subscription(msg.from_user.id)
    if not sub or not sub.get("payment_id"):
        await msg.answer("Нет ожидающей оплаты.")
        return

    if await check_cryptobot_payment(sub["payment_id"]):
        await update_payment_status(msg.from_user.id, True)
        await msg.answer(f"✅ Оплата подтверждена!\nСсылка: {PRIVATE_CHANNEL_LINK}")
        await bot.send_message(ADMIN_CHAT_ID, f"💳 Оплата: {msg.from_user.id} — {sub['tariff']}")
    else:
        await msg.answer("Оплата пока не подтверждена.")

@dp.callback_query(F.data == "support")
async def support(cb: types.CallbackQuery):
    support_back = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]]
    )
    await cb.message.edit_text("❓ В случае, если у вас возникли вопросы с оплатой, активацией подписки, неактивными ссылками и другие вопросы, пожалуйста, обратитесь в службу поддержки:\n\nhttps://t.me/DorianLaren", reply_markup=support_back)
    await cb.answer()

@dp.callback_query(F.data == "check_subscription")
async def check_subscription(cb: types.CallbackQuery):
    support_back = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]]
    )
    sub = await get_subscription(cb.from_user.id)
    text = f"✅ Подписка активна! Ссылка: {PRIVATE_CHANNEL_LINK}" if sub and sub['paid'] else "❌ Подписка не найдена."
    await cb.message.edit_text(text, reply_markup=support_back)
    await cb.answer()

@dp.callback_query(F.data.startswith("tariff_"))
async def choose_tariff(cb: types.CallbackQuery):
    tariff = cb.data.split("_", 1)[1]
    logging.info(f"[TARIFF] Пользователь {cb.from_user.id} выбрал тариф: {tariff}")
    display_tariff_map = {"week": "Неделя", "month": "Месяц", "year": "Год"}
    price_map = {"week": "499₽", "month": "699₽", "year": "1299"}
    display_tariff = display_tariff_map.get(tariff, "Неизвестно")
    price = price_map.get(tariff, "Неизвестно")

    await set_subscription(cb.from_user.id, tariff, method=None, payment_id=None, paid=False)
    try:
        await cb.message.edit_text(
            f"📦 Вы выбрали тариф: <b>{display_tariff}</b> — <b>{price}</b>\n\nВыберите метод оплаты:",
            reply_markup=payment_buttons,
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await cb.answer()

@dp.callback_query(F.data.startswith("pay_"))
async def choose_payment(cb: types.CallbackQuery):
    method = cb.data.split("_", 1)[1]
    logging.info(f"[PAYMENT] Пользователь {cb.from_user.id} выбрал способ оплаты: {method}")
    user_id = cb.from_user.id
    sub = await get_subscription(user_id)
    if not sub or not sub.get("tariff"):
        await cb.answer("Сначала выберите тариф", show_alert=True)
        return

    display_tariff_map = {"week": "Неделя", "month": "Месяц", "year": "Год"}
    price_map = {"week": "499₽", "month": "699₽", "year": "1299₽"}
    usd_price_map = {"week": "6$", "month": "8.5$", "year": "15$"}

    display_tariff = display_tariff_map.get(sub['tariff'], "Неизвестно")
    price = price_map.get(sub['tariff'], "Неизвестно")
    usd_price = usd_price_map.get(sub['tariff'], "6$")

    details = payment_details.get(method)

    if method == "Cryptobot":
        usd_amount_value = {"week": 6, "month": 8.5, "year": 15}.get(sub['tariff'], 6)
        pid, url = await create_cryptobot_payment(usd_amount_value, user_id, cb.from_user.username)
        if pid and url:
            logging.info(f"[CRYPTOBOT] Создан инвойс {pid} для пользователя {user_id}")
            await set_subscription(user_id, sub['tariff'], method, pid, False)
            asyncio.create_task(schedule_payment_reminder(user_id, 600))  # 600 секунд = 10 минут

            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить через Cryptobot", url=url)],
                *payment_confirm_buttons.inline_keyboard
            ])

            await cb.message.edit_text(
                f"📦 Тариф: <b>{display_tariff}</b> — <b>{price}</b> / <b>{usd_price}</b>\n"
                f"💳 Метод оплаты: <b>Cryptobot</b>\n"
                f"👤 Ваш ID: <code>{user_id}</code>\n\n"
                f"Чтобы оплатить — нажмите кнопку ниже 👇\n\n"
                f"После оплаты нажмите 'Оплатил ✅'.",
                reply_markup=markup,
                parse_mode="HTML"
            )
        else:
            logging.info(f"[CRYPTOBOT] Создан инвойс {pid} для пользователя {user_id}")
            await cb.answer("Ошибка связи с Cryptobot. Попробуйте позже.", show_alert=True)
        return  # ВАЖНО: чтобы не продолжать ниже

    # Другие методы оплаты
    if not details:
        await cb.message.edit_text("Информация по методу оплаты временно недоступна.")
        await cb.answer()
        return

    extra_price_note = f" / <b>{usd_price}</b>" if method == "Криптовалюта" else ""
    await set_subscription(user_id, sub['tariff'], method, payment_id=None, paid=False)

    if method == "Криптовалюта":
        markup = payment_confirm_buttons
    elif method == "Через Tribute":
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Открыть оплату в Tribute", url="https://t.me/tribute/app?startapp=dsqJ")],
            *payment_confirm_buttons.inline_keyboard
        ])
    else:
        markup = payment_confirm_buttons

    final_text = (
        f"📆 Тариф: <b>{display_tariff}</b> — <b>{price}</b>{extra_price_note}\n"
        f"💳 Метод оплаты: <b>{method}</b>\n"
        f"👤 Ваш ID: <code>{user_id}</code>\n\n"
        f"{details}"
    )

    if method != "Через Tribute":
        final_text += "\n\nПосле оплаты нажмите 'Оплатил ✅'."

    await cb.message.edit_text(final_text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "paid_confirm")
async def confirm_payment(cb: types.CallbackQuery):
    sub = await get_subscription(cb.from_user.id)
    if not sub or not sub.get("payment_id"):
        await cb.answer("Оплата не найдена", show_alert=True)
        return

    if await check_cryptobot_payment(sub["payment_id"]):
        await update_payment_status(cb.from_user.id, True)
        await cb.message.edit_text(f"✅ Оплата подтверждена!\nСсылка: {PRIVATE_CHANNEL_LINK}")
        await bot.send_message(ADMIN_CHAT_ID, f"💳 Оплата: {cb.from_user.id} — {sub['tariff']}")
    else:
        await cb.answer("Оплата ещё не подтверждена. Попробуйте позже.", show_alert=True)

@dp.message()
async def fallback_message(msg: types.Message):
    await msg.answer("Пожалуйста, используйте кнопки ниже или введите /start.")

@dp.callback_query()
async def fallback_callback(cb: types.CallbackQuery):
    logging.warning(f"[UNKNOWN CALLBACK] {cb.data} от пользователя {cb.from_user.id}")
    await cb.answer("Эта кнопка пока не работает или устарела.", show_alert=True)

async def schedule_payment_reminder(user_id: int, delay: int):
    await asyncio.sleep(delay)
    sub = await get_subscription(user_id)

    if sub and not sub["paid"]:
        try:
            await bot.send_message(
                user_id,
                "💡 Напоминаем: вы начали оплату, но ещё не нажали кнопку 'Оплатил ✅'.\n"
                "Если уже оплатили — нажмите кнопку подтверждения. Если нет — завершите оплату через доступные способы.",
            )
            logging.info(f"[REMINDER] Напоминание отправлено пользователю {user_id}")
        except Exception as e:
            logging.error(f"[REMINDER] Ошибка при отправке напоминания: {e}")

async def main():
    await init_db()
    logging.info("✅ Бот успешно запущен и готов к работе.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
