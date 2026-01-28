# Упрощенный Telegram Bot - только подписка и запуск Mini App
# v_01.28.26 - Рефакторинг: бот только для подписки и WebApp

import os
import asyncio
import asyncpg
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, LabeledPrice

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://finadvisor-ai.ru")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "")

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

# Тарифы подписки
SUBSCRIPTION_PLANS = {
    "month": {
        "title": "Подписка на месяц",
        "description": "Полный доступ к FinAdvisor на 30 дней",
        "price": 29900,  # в копейках (299 руб)
        "days": 30
    },
    "year": {
        "title": "Подписка на год",
        "description": "Полный доступ к FinAdvisor на 365 дней (экономия 20%)",
        "price": 299000,  # в копейках (2990 руб)
        "days": 365
    }
}

# Глобальные настройки
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

db: Optional[asyncpg.pool.Pool] = None


async def create_db_pool():
    """Создать пул подключений к БД"""
    return await asyncpg.create_pool(
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME,
        host=DB_HOST, port=DB_PORT, min_size=1, max_size=6
    )


async def get_or_create_user(tg_id: int) -> tuple[int, bool]:
    """Получить или создать пользователя с 2 бесплатными месяцами
    
    Returns:
        tuple[int, bool]: (user_id, is_new_user)
    """
    async with db.acquire() as conn:
        row = await conn.fetchrow("SELECT id, premium_until FROM users WHERE tg_id=$1", tg_id)
        if not row:
            # Новый пользователь - даем 2 бесплатных месяца
            free_months_until = datetime.now() + timedelta(days=60)
            await conn.execute(
                "INSERT INTO users (tg_id, username, created_at, premium_until) VALUES ($1, $2, NOW(), $3)",
                tg_id, None, free_months_until
            )
            row = await conn.fetchrow("SELECT id, premium_until FROM users WHERE tg_id=$1", tg_id)
            return row['id'], True  # Возвращаем True если новый пользователь
        return row['id'], False  # Существующий пользователь


def format_premium_status(premium_until: Optional[datetime]) -> str:
    """Форматировать статус подписки"""
    if premium_until and premium_until > datetime.now():
        return f"✅ Активна до {premium_until.strftime('%d.%m.%Y')}"
    return "❌ Неактивна"


def get_main_keyboard(has_premium: bool = False) -> InlineKeyboardMarkup:
    """Главное меню с кнопкой WebApp и оплатой"""
    buttons = [
        [InlineKeyboardButton(
            text="🚀 Открыть FinAdvisor",
            web_app=WebAppInfo(url=WEB_APP_URL)
        )]
    ]
    
    # Если нет подписки и платежи настроены, добавляем кнопку оплаты
    if not has_premium and PAYMENT_PROVIDER_TOKEN:
        buttons.append([
            InlineKeyboardButton(text="💳 Оформить подписку", callback_data="subscribe_from_main")
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    """Команда /start - создает пользователя и показывает статус"""
    user_id, is_new_user = await get_or_create_user(m.from_user.id)
    
    # Получаем статус подписки
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT premium_until FROM users WHERE id=$1", user_id
        )
        premium_until = row['premium_until'] if row else None
    
    status_text = format_premium_status(premium_until)
    has_premium = premium_until and premium_until > datetime.now()
    
    message_text = (
        f"Привет, {m.from_user.first_name or 'пользователь'}! 👋\n\n"
        f"Я FinAdvisor — твой персональный финансовый помощник.\n\n"
    )
    
    # Если новый пользователь, показываем подарок
    if is_new_user and premium_until:
        message_text += (
            f"🎁 **Подарок для новых пользователей!**\n"
            f"Вы получили 2 бесплатных месяца подписки!\n\n"
        )
    
    message_text += f"📊 Статус подписки: {status_text}\n\n"
    
    if premium_until and premium_until > datetime.now():
        days_left = (premium_until - datetime.now()).days
        message_text += f"⏰ Подписка истекает через {days_left} дн.\n\n"
    
    if not has_premium and PAYMENT_PROVIDER_TOKEN:
        message_text += "💳 Оформите подписку, чтобы продлить доступ ко всем функциям.\n\n"
    
    message_text += "Нажми кнопку ниже, чтобы открыть приложение:"
    
    await m.answer(
        message_text,
        reply_markup=get_main_keyboard(has_premium=has_premium),
        parse_mode="Markdown"
    )


@dp.message(Command("subscribe"))
async def cmd_subscribe(m: types.Message):
    """Команда /subscribe - выбор тарифа и оплата"""
    if not PAYMENT_PROVIDER_TOKEN:
        await m.answer(
            "💳 Оплата подписки\n\n"
            "⚠️ Платежи временно недоступны.\n"
            "Обратитесь к администратору для активации.",
            reply_markup=get_main_keyboard()
        )
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Месяц — 299 ₽", callback_data="pay_month"),
            InlineKeyboardButton(text="📆 Год — 2990 ₽", callback_data="pay_year")
        ],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ])
    
    await m.answer(
        "💳 Оплата подписки\n\n"
        "Выберите тариф:\n"
        "• 📅 Месяц — 299 ₽ (30 дней)\n"
        "• 📆 Год — 2990 ₽ (365 дней, экономия 20%)\n\n"
        "После оплаты вы получите полный доступ ко всем функциям FinAdvisor.",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "back_to_main")
async def back_to_main(c: types.CallbackQuery):
    """Вернуться в главное меню"""
    user_id, _ = await get_or_create_user(c.from_user.id)
    
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT premium_until FROM users WHERE id=$1", user_id
        )
        premium_until = row['premium_until'] if row else None
    
    status_text = format_premium_status(premium_until)
    has_premium = premium_until and premium_until > datetime.now()
    
    message_text = (
        f"Привет, {c.from_user.first_name or 'пользователь'}! 👋\n\n"
        f"Я FinAdvisor — твой персональный финансовый помощник.\n\n"
        f"📊 Статус подписки: {status_text}\n\n"
    )
    
    if not has_premium and PAYMENT_PROVIDER_TOKEN:
        message_text += "💳 Оформите подписку, чтобы получить полный доступ ко всем функциям.\n\n"
    
    message_text += "Нажми кнопку ниже, чтобы открыть приложение:"
    
    await c.message.edit_text(
        message_text,
        reply_markup=get_main_keyboard(has_premium=has_premium)
    )
    await c.answer()


@dp.callback_query(F.data == "subscribe_from_main")
async def subscribe_from_main(c: types.CallbackQuery):
    """Переход к оплате из главного меню"""
    if not PAYMENT_PROVIDER_TOKEN:
        await c.answer("Платежи временно недоступны", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Месяц — 299 ₽", callback_data="pay_month"),
            InlineKeyboardButton(text="📆 Год — 2990 ₽", callback_data="pay_year")
        ],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ])
    
    await c.message.edit_text(
        "💳 Оплата подписки\n\n"
        "Выберите тариф:\n"
        "• 📅 Месяц — 299 ₽ (30 дней)\n"
        "• 📆 Год — 2990 ₽ (365 дней, экономия 20%)\n\n"
        "После оплаты вы получите полный доступ ко всем функциям FinAdvisor.",
        reply_markup=keyboard
    )
    await c.answer()


@dp.callback_query(F.data.startswith("pay_"))
async def process_payment(c: types.CallbackQuery):
    """Обработка выбора тарифа и отправка инвойса"""
    plan_type = c.data.replace("pay_", "")
    
    if plan_type not in SUBSCRIPTION_PLANS:
        await c.answer("Неверный тариф", show_alert=True)
        return
    
    plan = SUBSCRIPTION_PLANS[plan_type]
    
    if not PAYMENT_PROVIDER_TOKEN:
        await c.answer("Платежи временно недоступны", show_alert=True)
        return
    
    try:
        await bot.send_invoice(
            chat_id=c.message.chat.id,
            title=plan["title"],
            description=plan["description"],
            payload=f"subscription_{plan_type}_{c.from_user.id}",
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="RUB",
            prices=[LabeledPrice(label=plan["title"], amount=plan["price"])],
            start_parameter=f"subscription_{plan_type}",
            photo_url=None,
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            send_phone_number_to_provider=False,
            send_email_to_provider=False,
            is_flexible=False
        )
        await c.answer()
    except Exception as e:
        print(f"Error sending invoice: {e}")
        await c.answer("Ошибка при создании платежа. Попробуйте позже.", show_alert=True)


@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: types.PreCheckoutQuery):
    """Обработка запроса перед оплатой"""
    # Проверяем payload
    payload = pre_checkout_query.invoice_payload
    
    if not payload.startswith("subscription_"):
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Неверный тип платежа"
        )
        return
    
        # Проверяем, что пользователь существует
    try:
        user_id, _ = await get_or_create_user(pre_checkout_query.from_user.id)
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    except Exception as e:
        print(f"Error in pre_checkout: {e}")
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Ошибка обработки платежа. Попробуйте позже."
        )


@dp.message(F.content_type == "successful_payment")
async def successful_payment_handler(m: types.Message):
    """Обработка успешной оплаты"""
    payment = m.successful_payment
    payload = payment.invoice_payload
    
    if not payload.startswith("subscription_"):
        await m.answer("Ошибка: неверный тип платежа")
        return
    
    # Парсим payload: subscription_{plan_type}_{user_id}
    parts = payload.split("_")
    if len(parts) < 3:
        await m.answer("Ошибка: неверный формат платежа")
        return
    
    plan_type = parts[1]
    
    if plan_type not in SUBSCRIPTION_PLANS:
        await m.answer("Ошибка: неверный тариф")
        return
    
    plan = SUBSCRIPTION_PLANS[plan_type]
    user_id, _ = await get_or_create_user(m.from_user.id)
    
    # Получаем текущую дату окончания подписки
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT premium_until FROM users WHERE id=$1", user_id
        )
        current_premium_until = row['premium_until'] if row and row['premium_until'] else datetime.now()
        
        # Если подписка еще активна, продлеваем от текущей даты
        # Если истекла, начинаем с сегодня
        if current_premium_until > datetime.now():
            new_premium_until = current_premium_until + timedelta(days=plan["days"])
        else:
            new_premium_until = datetime.now() + timedelta(days=plan["days"])
        
        # Обновляем подписку
        await conn.execute(
            "UPDATE users SET premium_until=$1 WHERE id=$2",
            new_premium_until, user_id
        )
    
    status_text = format_premium_status(new_premium_until)
    
    await m.answer(
        f"✅ Оплата успешно обработана!\n\n"
        f"📊 Статус подписки: {status_text}\n\n"
        f"Спасибо за подписку! Теперь у вас есть полный доступ ко всем функциям FinAdvisor.",
        reply_markup=get_main_keyboard()
    )


@dp.message(Command("status"))
async def cmd_status(m: types.Message):
    """Команда /status - показать статус подписки"""
    user_id, _ = await get_or_create_user(m.from_user.id)
    
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT premium_until FROM users WHERE id=$1", user_id
        )
        premium_until = row['premium_until'] if row else None
    
    status_text = format_premium_status(premium_until)
    has_premium = premium_until and premium_until > datetime.now()
    
    await m.answer(
        f"📊 Статус подписки\n\n{status_text}",
        reply_markup=get_main_keyboard(has_premium=has_premium)
    )


async def on_startup():
    """Инициализация при запуске"""
    global db
    db = await create_db_pool()
    print("DB connected. Bot ready.")


async def on_shutdown():
    """Очистка при остановке"""
    global db
    if db:
        await db.close()
    print("Bot stopped.")


if __name__ == "__main__":
    try:
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        asyncio.run(dp.start_polling(bot))
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down")
