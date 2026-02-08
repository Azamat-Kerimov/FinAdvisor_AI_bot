# Упрощенный Telegram Bot - только подписка и запуск Mini App
# v_01.28.26 - Рефакторинг: бот только для подписки и WebApp

import logging
import os
import sys
import asyncio
import asyncpg
from datetime import datetime, timedelta, date
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, LabeledPrice, ErrorEvent

# Загружаем .env из папки, где лежит bot.py (не зависит от текущей директории)
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_env_path)

BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
WEB_APP_URL = (os.getenv("WEB_APP_URL") or "https://finadvisor-ai.ru").strip()
PAYMENT_PROVIDER_TOKEN = (os.getenv("PAYMENT_PROVIDER_TOKEN") or "").strip()

DB_NAME = (os.getenv("DB_NAME") or "").strip()
DB_USER = (os.getenv("DB_USER") or "").strip()
DB_PASSWORD = os.getenv("DB_PASSWORD")  # может быть пустым в dev
DB_HOST = (os.getenv("DB_HOST") or "").strip()
DB_PORT = (os.getenv("DB_PORT") or "5432").strip()

APP_ENV = (os.getenv("APP_ENV") or "").strip().lower()


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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)

# При старте всегда выводим, к какой БД подключаемся (чтобы не перепутать тест и прод)
print(f"БД: {DB_NAME} @ {DB_HOST}:{DB_PORT}", flush=True)
if APP_ENV == "test":
    print("Режим: ТЕСТ (APP_ENV=test)", flush=True)

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


def _display_name(from_user: types.User) -> Optional[str]:
    """Имя для БД: @username или first_name + last_name."""
    if from_user.username:
        return from_user.username.strip()
    first = (from_user.first_name or '').strip()
    last = (from_user.last_name or '').strip()
    return (' '.join((first, last)).strip() or None) if (first or last) else None


async def get_or_create_user(tg_id: int, username: Optional[str] = None, display_name: Optional[str] = None) -> tuple[int, bool]:
    """Получить или создать пользователя с 2 бесплатными месяцами
    
    Args:
        tg_id: Telegram user ID
        username: Telegram @username (optional)
        display_name: Имя для отображения, если username пустой (first_name + last_name)
    
    Returns:
        tuple[int, bool]: (user_id, is_new_user)
    """
    name_to_save = username or display_name
    async with db.acquire() as conn:
        row = await conn.fetchrow("SELECT id, premium_until, username FROM users WHERE tg_id=$1", tg_id)
        if not row:
            # Новый пользователь - даем 2 бесплатных месяца
            free_months_until = datetime.now() + timedelta(days=60)
            await conn.execute(
                "INSERT INTO users (tg_id, username, created_at, premium_until) VALUES ($1, $2, NOW(), $3)",
                tg_id, name_to_save, free_months_until
            )
            row = await conn.fetchrow("SELECT id, premium_until FROM users WHERE tg_id=$1", tg_id)
            return row['id'], True  # Возвращаем True если новый пользователь
        # Если пользователь существует, но username пустой, а передан новый - обновляем
        if name_to_save and (not row['username'] or row['username'] != name_to_save):
            await conn.execute(
                "UPDATE users SET username=$1 WHERE tg_id=$2",
                name_to_save, tg_id
            )
        return row['id'], False  # Существующий пользователь


def format_premium_status(premium_until: Optional[datetime]) -> str:
    """Форматировать статус пакета VIP"""
    if premium_until and premium_until > datetime.now():
        return f"✅ Пакет VIP активен до {premium_until.strftime('%d.%m.%Y')}"
    return "❌ Пакет VIP не оформлен"


def get_main_keyboard(has_premium: bool = False) -> InlineKeyboardMarkup:
    """Главное меню: WebApp и кнопка пакета VIP всегда доступны."""
    buttons = [
        [InlineKeyboardButton(
            text="🚀 Открыть FinAdvisor",
            web_app=WebAppInfo(url=WEB_APP_URL)
        )],
        [InlineKeyboardButton(
            text="💳 Продлить пакет VIP" if has_premium else "💳 Оформить пакет VIP",
            callback_data="subscribe_from_main"
        )]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    """Команда /start - создает пользователя и показывает статус"""
    try:
        user_id, is_new_user = await get_or_create_user(
            m.from_user.id, m.from_user.username, _display_name(m.from_user)
        )
        async with db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT premium_until FROM users WHERE id=$1", user_id
            )
            premium_until = row["premium_until"] if row else None
        status_text = format_premium_status(premium_until)
        has_premium = premium_until and premium_until > datetime.now()
        message_text = (
            f"Привет, {m.from_user.first_name or 'пользователь'}! 👋\n\n"
            f"Я FinAdvisor — твой персональный финансовый помощник.\n\n"
        )
        if is_new_user and premium_until:
            message_text += (
                "🎁 **Подарок для новых пользователей!**\n"
                "Вы получили 2 бесплатных месяца пакета VIP!\n\n"
            )
        message_text += f"📊 Статус: {status_text}\n\n"
        if premium_until and premium_until > datetime.now():
            days_left = (premium_until - datetime.now()).days
            message_text += f"⏰ Пакет VIP истекает через {days_left} дн.\n\n"
        if not has_premium and PAYMENT_PROVIDER_TOKEN:
            message_text += "💳 Оформите пакет VIP для расширенных возможностей. Приложение бесплатно: 1 консультация ИИ в месяц.\n\n"
        message_text += "Нажми кнопку ниже, чтобы открыть приложение:"
        await m.answer(
            message_text,
            reply_markup=get_main_keyboard(has_premium=has_premium),
            parse_mode="Markdown",
        )
    except Exception as e:
        logging.exception("cmd_start failed for tg_id=%s: %s", m.from_user.id, e)
        await m.answer(
            "Привет! 👋 Что-то пошло не так на сервере. Попробуйте написать /start через минуту или откройте приложение по кнопке ниже.",
            reply_markup=get_main_keyboard(has_premium=False),
        )


@dp.message(Command("subscribe"))
async def cmd_subscribe(m: types.Message):
    """Команда /subscribe - выбор тарифа и оплата"""
    if not PAYMENT_PROVIDER_TOKEN:
        await m.answer(
            "💳 Оплата пакета VIP\n\n"
            "⚠️ Платежи временно недоступны.\n"
            "Обратитесь к администратору для активации.",
            reply_markup=get_main_keyboard(),
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
        "💳 Оплата пакета VIP\n\n"
        "Выберите тариф:\n"
        "• 📅 Месяц — 299 ₽ (30 дней)\n"
        "• 📆 Год — 2990 ₽ (365 дней, экономия 20%)\n\n"
        "Приложение бесплатно: 1 консультация ИИ в месяц. Пакет VIP: 5 консультаций в месяц и приоритетная генерация.",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "back_to_main")
async def back_to_main(c: types.CallbackQuery):
    """Вернуться в главное меню"""
    user_id, _ = await get_or_create_user(
        c.from_user.id, c.from_user.username, _display_name(c.from_user)
    )
    
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
        f"📊 Статус: {status_text}\n\n"
    )
    
    if not has_premium and PAYMENT_PROVIDER_TOKEN:
        message_text += "💳 Оформите пакет VIP для расширенных возможностей. Бесплатно: 1 консультация ИИ в месяц.\n\n"
    
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
        u = pre_checkout_query.from_user
        user_id, _ = await get_or_create_user(u.id, u.username, _display_name(u))
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
    user_id, _ = await get_or_create_user(
        m.from_user.id, m.from_user.username, _display_name(m.from_user)
    )
    
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
        f"📊 Статус: {status_text}\n\n"
        f"Спасибо за пакет VIP! Теперь у вас 5 консультаций ИИ в месяц и приоритетная генерация.",
        reply_markup=get_main_keyboard()
    )


@dp.message(Command("status"))
async def cmd_status(m: types.Message):
    """Команда /status - показать статус пакета VIP"""
    user_id, _ = await get_or_create_user(
        m.from_user.id, m.from_user.username, _display_name(m.from_user)
    )
    
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT premium_until FROM users WHERE id=$1", user_id
        )
        premium_until = row['premium_until'] if row else None
    
    status_text = format_premium_status(premium_until)
    has_premium = premium_until and premium_until > datetime.now()
    
    await m.answer(
        f"📊 Статус\n\n{status_text}",
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


# Ежемесячный отчёт: 1-го числа за предыдущий месяц
MONTH_NAMES = (
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"
)


async def send_monthly_reports():
    """Месячный отчёт за предыдущий месяц: статистика расходов и рекомендация или уведомление обновить данные."""
    if not db:
        return
    today = date.today()
    first_this_month = today.replace(day=1)
    last_prev = first_this_month - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    period_start = datetime.combine(first_prev, datetime.min.time())
    period_end = datetime.combine(last_prev, datetime.max.time())
    month_label = f"{MONTH_NAMES[first_prev.month - 1]} {first_prev.year}"

    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT u.tg_id, u.id FROM users u WHERE u.tg_id IS NOT NULL"
        )
        for row in rows:
            tg_id = row["tg_id"]
            user_id = row["id"]
            try:
                tx_rows = await conn.fetch(
                    """
                    SELECT c.name AS category, SUM(ABS(t.amount)) AS total
                    FROM transactions t
                    JOIN categories c ON c.id = t.category_id
                    WHERE t.user_id = $1 AND t.amount < 0
                      AND t.created_at >= $2 AND t.created_at <= $3
                    GROUP BY c.name ORDER BY total DESC LIMIT 5
                    """,
                    user_id, period_start, period_end
                )
                total = sum(float(r["total"]) for r in tx_rows)
                if not tx_rows or total <= 0:
                    text = (
                        f"📊 Месячный отчёт FinAdvisor за {month_label}\n\n"
                        "За выбранный месяц операций не найдено. Обновите данные в приложении — так отчёты будут полезнее.\n\n"
                        "Бесплатно: 1 консультация ИИ в месяц в приложении."
                    )
                else:
                    top = ", ".join(
                        f"{r['category']}: {int(float(r['total'])):,} ₽".replace(",", " ")
                        for r in tx_rows[:3]
                    )
                    text = (
                        f"📊 Месячный отчёт FinAdvisor за {month_label}\n\n"
                        f"Расходы: {int(total):,} ₽\n".replace(",", " ")
                        + (f"Топ категорий: {top}\n\n" if top else "\n")
                        + "Бесплатно: 1 консультация ИИ в месяц в приложении."
                    )
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚀 Открыть FinAdvisor", web_app=WebAppInfo(url=WEB_APP_URL))],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
                ])
                await bot.send_message(tg_id, text, reply_markup=kb)
            except Exception as e:
                print(f"Monthly report to {tg_id}: {e}", file=sys.stderr, flush=True)
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
                    + f"Сумма долгов: {int(total_debt):,} ₽\n".replace(",", " ")
                    + f"Ежемесячные платежи: {int(total_monthly):,} ₽\n\n".replace(",", " ")
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
    scheduler.add_job(send_monthly_reports, "cron", day=1, hour=10, minute=0)
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
