# Упрощенный Telegram Bot - только подписка и запуск Mini App
# v_01.28.26 - Рефакторинг: бот только для подписки и WebApp

import os
import sys
import asyncio
import asyncpg
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, LabeledPrice, ErrorEvent

load_dotenv()

BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
WEB_APP_URL = (os.getenv("WEB_APP_URL") or "https://finadvisor-ai.ru").strip()
PAYMENT_PROVIDER_TOKEN = (os.getenv("PAYMENT_PROVIDER_TOKEN") or "").strip()

DB_NAME = (os.getenv("DB_NAME") or "").strip()
DB_USER = (os.getenv("DB_USER") or "").strip()
DB_PASSWORD = os.getenv("DB_PASSWORD")  # может быть пустым в dev
DB_HOST = (os.getenv("DB_HOST") or "").strip()
DB_PORT = (os.getenv("DB_PORT") or "5432").strip()


def _check_env():
    """Проверка обязательных переменных окружения. Выход с сообщением при ошибке."""
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not DB_NAME:
        missing.append("DB_NAME")
    if not DB_USER:
        missing.append("DB_USER")
    if DB_PASSWORD is None:
        missing.append("DB_PASSWORD")
    if not DB_HOST:
        missing.append("DB_HOST")
    if not DB_PORT:
        missing.append("DB_PORT")
    if missing:
        msg = f"Ошибка: в .env не заданы переменные: {', '.join(missing)}. Проверьте .env (формат: KEY=value без пробелов вокруг =)."
        print(msg, file=sys.stderr, flush=True)
        sys.exit(1)


_check_env()

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
    
    # Если платежи настроены: без подписки — «Оформить», с подпиской — «Продлить»
    if PAYMENT_PROVIDER_TOKEN:
        if has_premium:
            buttons.append([
                InlineKeyboardButton(text="💳 Продлить подписку", callback_data="subscribe_from_main")
            ])
        else:
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


@dp.error()
async def global_error_handler(event: ErrorEvent):
    """Глобальный обработчик ошибок: логируем и отвечаем пользователю."""
    print(f"Bot error: {event.exception}", flush=True)
    try:
        update = event.update
        if update.message:
            await update.message.answer(
                "Произошла ошибка. Попробуйте позже или напишите /start."
            )
        elif update.callback_query:
            await update.callback_query.answer("Ошибка. Попробуйте позже.", show_alert=True)
    except Exception:
        pass


# Ценность 1 и 4: еженедельный отчёт и напоминание, алерты по долгам
async def send_weekly_reports():
    """Еженедельный отчёт: потрачено за 7 дней, топ категорий + кнопка «Открыть FinAdvisor»."""
    if not db:
        return
    week_ago = datetime.now() - timedelta(days=7)
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT u.tg_id, u.id
            FROM users u
            WHERE u.premium_until > NOW()
            AND u.tg_id IS NOT NULL
            """
        )
        for row in rows:
            tg_id = row["tg_id"]
            user_id = row["id"]
            try:
                tx_rows = await conn.fetch(
                    """
                    SELECT category, SUM(ABS(amount)) as total
                    FROM transactions
                    WHERE user_id=$1 AND amount < 0 AND created_at >= $2
                    GROUP BY category ORDER BY total DESC LIMIT 5
                    """,
                    user_id, week_ago
                )
                total = sum(float(r["total"]) for r in tx_rows)
                top = ", ".join(f"{r['category']}: {int(float(r['total'])):,} ₽".replace(",", " ") for r in tx_rows[:3])
                text = (
                    "📊 Недельный отчёт FinAdvisor\n\n"
                    f"За последние 7 дней потрачено: {int(total):,} ₽\n".replace(",", " ")
                    + (f"Топ: {top}\n\n" if top else "\n")
                    + "Откройте приложение для деталей."
                )
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚀 Открыть FinAdvisor", web_app=WebAppInfo(url=WEB_APP_URL))]
                ])
                await bot.send_message(tg_id, text, reply_markup=kb)
            except Exception as e:
                print(f"Weekly report to {tg_id}: {e}")
            await asyncio.sleep(0.05)


async def send_weekly_reminder():
    """Напоминание: добавить операции за неделю."""
    if not db:
        return
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT tg_id FROM users WHERE premium_until > NOW() AND tg_id IS NOT NULL"
        )
        for row in rows:
            try:
                await bot.send_message(
                    row["tg_id"],
                    "⏰ Напоминание FinAdvisor\n\nДобавьте операции за неделю — так отчёты будут точнее.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🚀 Открыть FinAdvisor", web_app=WebAppInfo(url=WEB_APP_URL))]
                    ]),
                )
            except Exception as e:
                print(f"Weekly reminder to {row['tg_id']}: {e}")
            await asyncio.sleep(0.05)


async def send_debt_reminder():
    """Ценность 4: напоминание о долгах — сумма долгов и ежемесячные платежи."""
    if not db:
        return
    async with db.acquire() as conn:
        users_with_liabs = await conn.fetch(
            """
            SELECT u.tg_id, u.id
            FROM users u
            WHERE u.premium_until > NOW() AND u.tg_id IS NOT NULL
            AND EXISTS (SELECT 1 FROM liabilities l WHERE l.user_id = u.id)
            """
        )
        for row in users_with_liabs:
            user_id = row["id"]
            tg_id = row["tg_id"]
            try:
                liabs = await conn.fetch(
                    """
                    SELECT l.title, v.amount, v.monthly_payment
                    FROM liabilities l
                    JOIN LATERAL (
                        SELECT amount, monthly_payment FROM liability_values
                        WHERE liability_id = l.id ORDER BY created_at DESC LIMIT 1
                    ) v ON TRUE
                    WHERE l.user_id = $1
                    """,
                    user_id
                )
                total_debt = sum(float(r["amount"] or 0) for r in liabs)
                total_monthly = sum(float(r["monthly_payment"] or 0) for r in liabs)
                if total_debt <= 0:
                    continue
                text = (
                    "📋 FinAdvisor: напоминание о долгах\n\n"
                    f"Сумма долгов: {int(total_debt):,} ₽\n".replace(",", " ")
                    f"Ежемесячные платежи: {int(total_monthly):,} ₽\n\n".replace(",", " ")
                    + "Откройте приложение, чтобы видеть детали."
                )
                await bot.send_message(
                    tg_id, text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🚀 Открыть FinAdvisor", web_app=WebAppInfo(url=WEB_APP_URL))]
                    ]),
                )
            except Exception as e:
                print(f"Debt reminder to {tg_id}: {e}")
            await asyncio.sleep(0.05)


scheduler = AsyncIOScheduler()


async def on_startup():
    """Инициализация при запуске"""
    global db
    try:
        db = await create_db_pool()
    except Exception as e:
        msg = f"Ошибка подключения к БД: {e}. Проверьте DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD и что PostgreSQL запущен."
        print(msg, file=sys.stderr, flush=True)
        sys.exit(1)
    scheduler.add_job(send_weekly_reports, "cron", day_of_week="mon", hour=10, minute=0)
    scheduler.add_job(send_weekly_reminder, "cron", day_of_week="thu", hour=12, minute=0)
    scheduler.add_job(send_debt_reminder, "cron", day_of_week="sun", hour=18, minute=0)
    scheduler.start()
    print("DB connected. Scheduler started. Bot ready.")


async def on_shutdown():
    """Очистка при остановке"""
    scheduler.shutdown(wait=False)
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
        print("Shutting down", flush=True)
    except Exception as e:
        import traceback
        print(f"Бот упал: {e}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
